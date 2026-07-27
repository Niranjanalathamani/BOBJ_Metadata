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