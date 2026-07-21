# """
# modules/dataprovider.py
# -----------------------
# Fetches Data Providers for every Web Intelligence document.

# Flow:
#   1. CMS query → list of WebI docs with SI_ID, SI_NAME
#   2. For each SI_ID → GET /raylight/v1/documents/{SI_ID}/dataproviders
#   3. Parse JSON
#   4. Return one list entry per report
# """

# import requests

# from config import BOBJ_BASE_URL
# from utils.infostore import run_paginated_cmsquery


# def dataprovider_url(doc_id):
#     return f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/dataproviders"


# def fetch_dataproviders(session, doc_id):

#     url = dataprovider_url(doc_id)

#     headers = {
#         "X-SAP-LogonToken": session.token,
#         "Accept": "application/json"
#     }

#     try:

#         response = requests.get(
#             url,
#             headers=headers,
#             timeout=30
#         )

#         response.raise_for_status()

#         data = response.json()

#         providers = []

#         dp_root = data.get("dataproviders", {})

#         if isinstance(dp_root, dict):
#             raw_list = dp_root.get("dataprovider", [])
#         elif isinstance(dp_root, list):
#             raw_list = dp_root
#         else:
#             raw_list = []

#         if isinstance(raw_list, (dict, str)):
#             raw_list = [raw_list]

#         for dp in raw_list:
#             if isinstance(dp, dict):
#                 name = dp.get("name") or dp.get("id") or dp.get("dataSourceName")
#                 if name:
#                     providers.append(str(name))
#             elif isinstance(dp, str):
#                 providers.append(dp)

#         return sorted(set(providers))

#     except Exception as err:
#         print(f"[DATAPROVIDER] Failed for document {doc_id}: {err}")
#         return []


# def fetch_webi_documents(session):

#     query = """
#     SELECT SI_ID, SI_NAME
#     FROM CI_INFOOBJECTS
#     WHERE SI_KIND='Webi'
#       AND SI_INSTANCE=0
#     ORDER BY SI_NAME
#     """

#     entries = run_paginated_cmsquery(session, query)

#     docs = []
#     seen = set()

#     for e in entries:

#         doc_id = e.get("SI_ID")

#         if doc_id in seen:
#             continue

#         seen.add(doc_id)

#         docs.append({
#             "id": doc_id,
#             "name": e.get("SI_NAME")
#         })

#     return docs


# def get_all_dataproviders(session):

#     documents = fetch_webi_documents(session)

#     results = []

#     print(f"[DATAPROVIDER] Found {len(documents)} reports.")

#     for i, doc in enumerate(documents, start=1):

#         print(f"[{i}/{len(documents)}] {doc['name']}")

#         providers = fetch_dataproviders(
#             session,
#             doc["id"]
#         )

#         results.append({

#             "id": doc["id"],

#             "name": doc["name"],

#             "dataproviders": providers

#         })

#     return results