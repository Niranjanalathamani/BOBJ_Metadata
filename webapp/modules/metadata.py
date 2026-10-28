"""
modules/metadata.py
-------------------
Fetches OData $metadata (dimensions & measures) and Raylight details for Web Intelligence
documents on the BI platform folder by folder.

Flow:
  1. CMS query → list of WebI docs with SI_ID, SI_NAME, SI_CUID, SI_PARENTID
  2. Map documents by folder path
  3. Process folder by folder:
     - For each folder, evaluate reports (metadata, filters, variables, dataproviders, visualizations, SQL)
     - Multi-threaded worker pool within each folder for speed
     - Persist progress incrementally to cache
  4. Return a dict { folder_path: [report, ...] }
"""

import requests
import xml.etree.ElementTree as ET
import os
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import BOBJ_BASE_URL
from utils.infostore import run_paginated_cmsquery
from modules.dataprovider import fetch_dataproviders, fetch_query_plans_sql
from modules.variables import fetch_variables
from modules.path import build_folder_map, get_report_folder_path
from modules.visualizations import fetch_visualization_counts
from modules.datafilters import fetch_doc_filters

# ============================================
# CRAWL PROGRESS & TIMING TRACKING
# ============================================

_progress_lock = threading.Lock()
_crawl_start_time: float | None = None
_last_duration: float | None = None
_last_collected_at: str | None = None

_progress = {
    "current": 0,
    "total": 0,
    "percent": 0,
    "status": "idle",
    "current_folder": "",
    "folder_index": 0,
    "total_folders": 0,
    "current_report": "",
    "elapsed_seconds": 0.0,
    "avg_seconds_per_report": 0.0,
    "message": "",
    "last_duration": None,
    "last_collected_at": None,
}

def get_progress():
    with _progress_lock:
        data = dict(_progress)
        if _crawl_start_time and _progress["status"] == "running":
            elapsed = round(time.time() - _crawl_start_time, 1)
            data["elapsed_seconds"] = elapsed
            if _progress["current"] > 0:
                data["avg_seconds_per_report"] = round(elapsed / _progress["current"], 2)
        elif _last_duration is not None:
            data["elapsed_seconds"] = _last_duration
            if _progress["total"] > 0:
                data["avg_seconds_per_report"] = round(_last_duration / _progress["total"], 2)
        data["last_duration"] = _last_duration
        data["last_collected_at"] = _last_collected_at
        return data

def set_progress(current, total, status, current_folder="", folder_index=0, total_folders=0, current_report="", message=""):
    with _progress_lock:
        _progress["current"] = current
        _progress["total"] = total
        _progress["percent"] = int((current / total * 100)) if total > 0 else 0
        _progress["status"] = status
        _progress["current_folder"] = current_folder
        _progress["folder_index"] = folder_index
        _progress["total_folders"] = total_folders
        if current_report:
            _progress["current_report"] = current_report
        if _crawl_start_time and status == "running":
            elapsed = round(time.time() - _crawl_start_time, 1)
            _progress["elapsed_seconds"] = elapsed
            if current > 0:
                _progress["avg_seconds_per_report"] = round(elapsed / current, 2)
        _progress["message"] = message or f"Loading report details & metadata... ({current}/{total} reports)"


# ============================================
# CACHE HELPERS
# ============================================
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports_cache.json")

def load_cached_reports():
    """Load previously evaluated folder reports from disk cache if available."""
    global _last_duration, _last_collected_at
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    meta = data.get("_collection_meta", {})
                    if meta:
                        _last_duration = meta.get("duration_seconds")
                        _last_collected_at = meta.get("collected_at")
                    return data
        except Exception as e:
            print(f"[CACHE] Error loading cache: {e}")
    return None

def save_cached_reports(data):
    """Save folder reports dictionary to disk cache."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[CACHE] Failed saving cache: {e}")


# ============================================
# NORMALIZE CUID
# ============================================

def normalize_cuid(cuid):
    """Ensure the CUID has the 'cuid_' prefix required by the Raylight URL."""
    if not cuid:
        raise ValueError("cuid is required")

    cuid = str(cuid).strip()
    if cuid.startswith("cuid_"):
        return cuid

    return f"cuid_{cuid}"


# ============================================
# METADATA URL
# ============================================

def metadata_url(cuid):
    """Build the OData $metadata URL for a given CUID."""
    cuid_segment = normalize_cuid(cuid)
    return (
        f"{BOBJ_BASE_URL}/raylight/v1/documents/"
        f"{cuid_segment}/datamodel/data.svc/$metadata"
    )


# ============================================
# FETCH METADATA XML
# ============================================

def fetch_metadata_xml(session, cuid):
    """
    GET the raw OData $metadata XML for a single document.
    Must specify Accept: application/xml because Raylight metadata endpoint
    only supports XML responses (returns HTTP 406 if application/json is sent).
    """
    url = metadata_url(cuid)
    headers = {
        "X-SAP-LogonToken": session.token,
        "Accept": "application/xml, text/xml",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    except requests.exceptions.RequestException as err:
        resp = getattr(err, "response", None)
        print(f"[METADATA] Failed fetching: {url}")
        if resp is not None:
            print(f"  Status: {resp.status_code}")
            print(f"  Body:   {resp.text[:300]}")
        else:
            print(f"  Error:  {err}")
        raise


# ============================================
# PARSE METADATA XML → DIMENSIONS & MEASURES
# ============================================

def parse_metadata(xml_text):
    """
    Parse an OData $metadata XML document and return
    (dimensions, measures) as two sorted, deduplicated lists of names.
    """
    dimensions = []
    measures = []

    root = ET.fromstring(xml_text)

    for element in root.iter():
        tag = element.tag.split("}")[-1]
        if tag != "Property":
            continue

        name = element.attrib.get("Name")
        if name:
            name = name.replace("_x0020", " ")

        if not name:
            continue

        aggregation = ""
        for key, value in element.attrib.items():
            if key.endswith("aggregation-role"):
                aggregation = value.lower()
                break

        if aggregation == "measure":
            measures.append(name)
        else:
            dimensions.append(name)

    return sorted(set(dimensions)), sorted(set(measures))


# ============================================
# FETCH DIMENSIONS & MEASURES (SAFE WRAPPER)
# ============================================

def fetch_dimensions_measures(session, cuid):
    """
    Fetch and parse the $metadata for one document.
    Returns (dimensions, measures) — empty lists on error so one bad
    document never crashes the entire loop.
    """
    try:
        xml = fetch_metadata_xml(session, cuid)
        return parse_metadata(xml)
    except Exception as ex:
        print(f"[METADATA] Skipping cuid={cuid}: {ex}")
        return [], []


# ============================================
# FETCH ALL WEBI DOCUMENTS (CMS QUERY)
# ============================================

def fetch_webi_documents(session):
    """
    Run a paginated CMS query to get every WebI document with its
    SI_ID, SI_NAME, and SI_CUID.
    """
    query = """
    SELECT SI_ID, SI_KIND, SI_NAME, SI_CUID, SI_PARENTID
    FROM CI_INFOOBJECTS
    WHERE SI_KIND = 'Webi'
      AND SI_INSTANCE = 0 
    ORDER BY SI_PARENTID, SI_NAME
    """

    entries = run_paginated_cmsquery(session, query)

    seen = set()
    docs = []

    for e in entries:
        doc_id = e.get("SI_ID")
        if doc_id in seen:
            continue
        seen.add(doc_id)

        docs.append({
            "id": doc_id,
            "name": e.get("SI_NAME"),
            "cuid": e.get("SI_CUID"),
            "SI_PARENTID": e.get("SI_PARENTID")
        })

    return docs


# ============================================
# EVALUATE SINGLE WEBI REPORT
# ============================================

def evaluate_single_webi_report(session, doc, folder_path):
    """
    Fetch all Raylight metadata for a single WebI document:
    dimensions, measures, filters, variables, dataproviders, visualizations, SQL.
    Records extraction duration in seconds for this individual report.
    """
    t_start = time.time()
    cuid = doc.get("cuid")
    doc_id = doc.get("id")

    try:
        dims, measures = fetch_dimensions_measures(session, cuid)
    except Exception:
        dims, measures = [], []

    try:
        filters = fetch_doc_filters(session, doc_id)
    except Exception:
        filters = []

    try:
        variables = fetch_variables(session, doc_id)
    except Exception:
        variables = {}

    try:
        dataproviders = fetch_dataproviders(session, doc_id)
    except Exception:
        dataproviders = []

    try:
        visualizations = fetch_visualization_counts(session, doc_id)
    except Exception:
        visualizations = {}

    try:
        sql_queries = fetch_query_plans_sql(session, doc_id)
    except Exception:
        sql_queries = []

    duration = round(time.time() - t_start, 2)

    return {
        "id": doc_id,
        "name": doc.get("name"),
        "cuid": cuid,
        "kind": "Web Intelligence",
        "folder_path": folder_path,
        "dimensions": dims,
        "measures": measures,
        "filters": filters,
        "variables": variables,
        "dataproviders": dataproviders,
        "visualizations": visualizations,
        "sql": sql_queries,
        "collection_time_seconds": duration,
    }


# ============================================
# GET METADATA BY FOLDER (FOLDER-WISE EVALUATION)
# ============================================

def get_metadata_by_folder(session, folder_map=None, target_folder_path=None, force=False, max_workers=5):
    """
    Evaluates WebI documents FOLDER BY FOLDER.
    - If target_folder_path is provided, evaluates and returns ONLY that folder.
    - Automatically persists completed folders to cache file.
    - Returns a dict: { folder_path: [report_data, ...] }
    """
    if folder_map is None:
        folder_map = build_folder_map(session)

    if not force:
        cached = load_cached_reports()
        if cached:
            if target_folder_path:
                if target_folder_path in cached:
                    print(f"[METADATA] Serving folder '{target_folder_path}' from cache ({len(cached[target_folder_path])} reports).")
                    return {target_folder_path: cached[target_folder_path]}
            else:
                print(f"[METADATA] Serving {len(cached)} folders from cache.")
                return cached

    documents = fetch_webi_documents(session)

    # Group documents by folder path
    docs_by_folder = {}
    for doc in documents:
        folder_path = get_report_folder_path(doc, folder_map)
        if target_folder_path and folder_path != target_folder_path:
            continue
        docs_by_folder.setdefault(folder_path, []).append(doc)

    sorted_folders = sorted(docs_by_folder.keys())
    total_folders = len(sorted_folders)
    total_to_evaluate = sum(len(d) for d in docs_by_folder.values())

    print(f"[METADATA] Evaluating {total_folders} folder(s), {total_to_evaluate} reports total.")

    results_to_save = load_cached_reports() or {}
    evaluated_results = {}

    for folder_idx, folder_path in enumerate(sorted_folders, start=1):
        folder_docs = docs_by_folder[folder_path]
        folder_doc_count = len(folder_docs)

        # Check if already in cache and not forced
        if not force and folder_path in results_to_save and len(results_to_save[folder_path]) == folder_doc_count:
            print(f"[METADATA] Folder '{folder_path}' already in cache. Using cached.")
            evaluated_results[folder_path] = results_to_save[folder_path]
            continue

        print(f"[METADATA] Evaluating Folder ({folder_idx}/{total_folders}): '{folder_path}' ({folder_doc_count} reports)...")

        folder_results = []
        if max_workers > 1 and folder_doc_count > 1:
            with ThreadPoolExecutor(max_workers=min(max_workers, folder_doc_count)) as executor:
                future_map = {
                    executor.submit(evaluate_single_webi_report, session, doc, folder_path): doc
                    for doc in folder_docs
                }
                for future in as_completed(future_map):
                    doc = future_map[future]
                    doc_name = doc.get("name") or "Unknown Report"
                    try:
                        rep = future.result()
                        folder_results.append(rep)
                    except Exception as ex:
                        print(f"[METADATA] Error evaluating {doc_name}: {ex}")
        else:
            for doc in folder_docs:
                doc_name = doc.get("name") or "Unknown Report"
                try:
                    rep = evaluate_single_webi_report(session, doc, folder_path)
                    folder_results.append(rep)
                except Exception as ex:
                    print(f"[METADATA] Error evaluating {doc_name}: {ex}")

        folder_results.sort(key=lambda r: (r.get("name") or "").lower())
        evaluated_results[folder_path] = folder_results
        results_to_save[folder_path] = folder_results
        save_cached_reports(results_to_save)

    print(f"[METADATA] Finished evaluation for {len(evaluated_results)} folder(s).")
    return evaluated_results


# ============================================
# GET ALL METADATA (LEGACY COMPATIBILITY)
# ============================================

def get_all_metadata(session, folder_map=None, force=False):
    """
    Main entry point for flat report list. Evaluates folder by folder
    and returns a combined list of all WebI documents.
    """
    by_folder = get_metadata_by_folder(session, folder_map=folder_map, force=force)
    flat_list = []
    for f_key, reps in by_folder.items():
        if f_key == "_collection_meta" or not isinstance(reps, list):
            continue
        flat_list.extend(reps)
    return flat_list
