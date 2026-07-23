"""
modules/metadata.py
-------------------
Fetches OData $metadata (dimensions & measures) for every Web Intelligence
document on the BI platform.

Flow:
  1. CMS query → list of WebI docs with SI_ID, SI_NAME, SI_CUID
  2. For each CUID → GET .../raylight/v1/documents/cuid_<CUID>/datamodel/data.svc/$metadata
  3. Parse the XML → extract dimension names and measure names
  4. Return a list of dicts, one per report

Only metadata is fetched here — no variables, filters, dataproviders, or
similarity logic.
"""

import requests
import xml.etree.ElementTree as ET

from config import BOBJ_BASE_URL
from utils.infostore import run_paginated_cmsquery
# from modules.dataprovider import fetch_dataproviders
# from modules.variables import fetch_variables


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

    The XML contains <Property> elements with an SAP extension attribute
    ``sap:aggregation-role``.  If its value is "measure" → measure,
    otherwise → dimension.
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
            # Decode the hex-encoded spaces that BOBJ sometimes injects
            name = name.replace("_x0020", " ")

        if not name:
            continue

        # Check for the SAP aggregation-role attribute (namespace-qualified)
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
    SELECT SI_ID, SI_KIND, SI_NAME, SI_CUID
    FROM CI_INFOOBJECTS
    WHERE SI_KIND = 'Webi'
      AND SI_INSTANCE = 0 
    ORDER BY SI_NAME
    """

    entries = run_paginated_cmsquery(session, query)

    # Deduplicate by SI_ID (just in case)
    seen = set()
    docs = []

    for e in entries:
        doc_id = e.get("SI_ID")
        if doc_id in seen:
            continue
        seen.add(doc_id)

        docs.append({
            "id":   doc_id,
            "name": e.get("SI_NAME"),
            "cuid": e.get("SI_CUID"),
        })

    return docs


from modules.datafilters import fetch_doc_filters


# ============================================
# GET ALL METADATA (MAIN ENTRY POINT)
# ============================================

def get_all_metadata(session):
    """
    Loop through every WebI document on the platform, fetch its
    $metadata (dimensions & measures) and datafilters, and return a list of dicts:

        [
            {
                "id":         "12345",
                "name":       "Sales Report",
                "cuid":       "AVEwPE0l...",
                "dimensions": ["Country", "Product", ...],
                "measures":   ["Revenue", "Quantity", ...],
                "filters":    ["[Product Category] InList (Home Theater)"]
            },
            ...
        ]
    """

    documents = fetch_webi_documents(session)

    print(f"[METADATA] Found {len(documents)} WebI documents. "
          f"Fetching metadata and filters for each...")

    results = []

    for idx, doc in enumerate(documents, start=1):

        cuid = doc.get("cuid")
        doc_id = doc.get("id")

        print(f"[METADATA] ({idx}/{len(documents)}) "
              f"{doc['name']} (cuid={cuid}, id={doc_id})")

        dims, measures = fetch_dimensions_measures(session, cuid)
        filters = fetch_doc_filters(session, doc_id)

        results.append({
            "id":            doc_id,
            "name":          doc["name"],
            "cuid":          cuid,
            "dimensions":    dims,
            "measures":      measures,
            "filters":       filters,
        })

    print(f"[METADATA] Done — collected metadata and filters for "
          f"{len(results)} documents.")

    return results
