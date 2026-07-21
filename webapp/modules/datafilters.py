"""
modules/datafilters.py
----------------------
Fetches and parses report datafilters (conditions, operators, and values)
for Web Intelligence documents via the BOBJ Raylight REST API.

Endpoint flow:
  1. GET /raylight/v1/documents/{doc_id}/reports
  2. For each sub-report -> GET /raylight/v1/documents/{doc_id}/reports/{report_sub_id}/datafilter
  3. Parse conditions, operators, and filter values
"""

import requests
from config import BOBJ_BASE_URL


def parse_condition_node(node):
    """
    Recursively extract condition strings from a datafilter node.
    Handles 'and', 'or', and 'condition' lists/dicts.
    """
    filters = []

    if not isinstance(node, dict):
        return filters

    # Handle logical operator containers ("and", "or")
    for logical_op in ["and", "or"]:
        if logical_op in node:
            child = node[logical_op]
            filters.extend(parse_condition_node(child))

    # Handle "condition" elements
    if "condition" in node:
        conds = node["condition"]
        if isinstance(conds, dict):
            conds = [conds]
        if isinstance(conds, list):
            for c in conds:
                if isinstance(c, dict):
                    if "@key" in c or "@operator" in c:
                        key = c.get("@key", "").strip()
                        operator = c.get("@operator", "").strip()
                        val_raw = c.get("value", [])

                        if isinstance(val_raw, list):
                            val_str = ", ".join(str(v) for v in val_raw)
                        elif val_raw is not None:
                            val_str = str(val_raw)
                        else:
                            val_str = ""

                        if key and operator:
                            if val_str:
                                filter_str = f"{key} {operator} ({val_str})"
                            else:
                                filter_str = f"{key} {operator}"
                            filters.append(filter_str)
                        elif key:
                            filters.append(key)
                    else:
                        filters.extend(parse_condition_node(c))

    return filters


def fetch_doc_filters(session, doc_id):
    """
    Fetch all datafilters for all sub-reports of a document.
    Returns a sorted list of unique filter condition strings.
    """
    if not doc_id:
        return []

    reports_url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/reports"
    headers = {
        "X-SAP-LogonToken": session.token,
        "Accept": "application/json"
    }

    try:
        res = requests.get(reports_url, headers=headers, timeout=15)
        if res.status_code != 200:
            return []

        data = res.json()
        reports = data.get("reports", {}).get("report", [])
        if isinstance(reports, dict):
            reports = [reports]

        all_filters = []

        for rep in reports:
            rep_id = rep.get("id")
            if rep_id is None:
                continue

            df_url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/reports/{rep_id}/datafilter"
            try:
                df_res = requests.get(df_url, headers=headers, timeout=15)
                if df_res.status_code == 200:
                    df_json = df_res.json()
                    df_root = df_json.get("datafilter", {})
                    extracted = parse_condition_node(df_root)
                    all_filters.extend(extracted)
            except Exception as ex:
                print(f"[DATAFILTER] Failed fetching filter for doc {doc_id} report {rep_id}: {ex}")

        return sorted(set(all_filters))

    except Exception as ex:
        print(f"[DATAFILTER] Failed fetching sub-reports for doc {doc_id}: {ex}")
        return []
