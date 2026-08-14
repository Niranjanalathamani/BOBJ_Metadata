"""
modules/dataprovider.py
-----------------------
Fetches Data Providers for Web Intelligence reports and extracts their data source type.
"""

import requests
from config import BOBJ_BASE_URL


def fetch_dataproviders(session, doc_id):
    """
    Fetch all data providers for a document and return their unique dataSourceType values.
    """
    if not doc_id:
        return []

    url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/dataproviders"
    headers = {
        "X-SAP-LogonToken": session.token,
        "Accept": "application/json"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )
        if response.status_code != 200:
            return []

        data = response.json()
        dp_root = data.get("dataproviders", {})
        if not dp_root:
            return []

        raw_list = dp_root.get("dataprovider", [])
        if isinstance(raw_list, dict):
            raw_list = [raw_list]
        elif not isinstance(raw_list, list):
            raw_list = []

        types = []
        for dp in raw_list:
            if isinstance(dp, dict):
                ds_type = dp.get("dataSourceType")
                if ds_type:
                    types.append(ds_type)
            elif isinstance(dp, str):
                types.append(dp)

        return sorted(list(set(types)))

    except Exception as err:
        print(f"[DATAPROVIDER] Failed for document {doc_id}: {err}")
        return []


def fetch_query_plans_sql(session, doc_id) -> list[str]:
    """
    Fetch all data providers for a document, then fetch the query plan SQL for each DP
    and extract all SQL statements.
    """
    import xml.etree.ElementTree as ET

    if not doc_id:
        return []

    url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/dataproviders"
    headers = {
        "X-SAP-LogonToken": session.token,
        "Accept": "application/json"
    }

    sql_statements = []
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return []

        data = response.json()
        dp_root = data.get("dataproviders", {})
        if not dp_root:
            return []

        raw_list = dp_root.get("dataprovider", [])
        if isinstance(raw_list, dict):
            raw_list = [raw_list]
        elif not isinstance(raw_list, list):
            raw_list = []

        xml_headers = {
            "X-SAP-LogonToken": session.token,
            "Accept": "application/xml"
        }

        for dp in raw_list:
            if not isinstance(dp, dict):
                continue
            dp_id = dp.get("id")
            if not dp_id:
                continue

            qp_url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/dataproviders/{dp_id}/queryplan"
            try:
                qp_res = requests.get(qp_url, headers=xml_headers, timeout=30)
                if qp_res.status_code == 200:
                    xml_text = qp_res.text
                    root = ET.fromstring(xml_text)
                    for statement in root.findall(".//statement"):
                        if statement.text:
                            sql_text = statement.text.strip()
                            if sql_text and sql_text != "...":
                                sql_statements.append(sql_text)
            except Exception as ex:
                print(f"[DATAPROVIDER] Failed to fetch queryplan for doc {doc_id} DP {dp_id}: {ex}")

        return sorted(list(set(sql_statements)))

    except Exception as err:
        print(f"[DATAPROVIDER] Failed to fetch queryplan DPs for document {doc_id}: {err}")
        return []