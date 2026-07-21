"""
schedules.py
--------------------
Fetches scheduled report instance counts from BOBJ.
"""

from utils.infostore import get_cms_count, run_cmsquery, run_paginated_cmsquery
from utils.raylight import get_raylight


def get_schedule_summary(session) -> dict:
    """
    Returns the total number of scheduled report instances.
    Using the count query:
      SELECT COUNT(SI_ID) FROM CI_INFOOBJECTS WHERE SI_INSTANCE = 1
    (Where status = 1 is success, and status = 3 is failure).
    """
    total_query = "SELECT COUNT(SI_ID) FROM CI_INFOOBJECTS WHERE SI_INSTANCE = 1"
    success_query = "SELECT COUNT(SI_ID) FROM CI_INFOOBJECTS WHERE SI_INSTANCE = 1 AND SI_SCHEDULE_STATUS = 1"
    failure_query = "SELECT COUNT(SI_ID) FROM CI_INFOOBJECTS WHERE SI_INSTANCE = 1 AND SI_SCHEDULE_STATUS = 3"

    total = get_cms_count(session, total_query)
    success = get_cms_count(session, success_query)
    failure = get_cms_count(session, failure_query)

    return {"total": total, "success": success, "failure": failure}


def get_event_counts(session) -> dict:
    """
    Groups events into File Based, Custom, and Scheduled Events.
    Using the query:
      SELECT SI_ID, SI_NAME, SI_EVENT_TYPE FROM CI_SYSTEMOBJECTS WHERE SI_KIND='Event'
    """
    try:
        query = "SELECT SI_ID, SI_NAME, SI_EVENT_TYPE FROM CI_SYSTEMOBJECTS WHERE SI_KIND='Event'"
        entries = run_paginated_cmsquery(session, query)

        file_count = 0
        sched_count = 0
        custom_count = 0

        for e in entries:
            # SI_EVENT_TYPE is usually nested or direct:
            # 0 = File Based, 1 = Scheduled Event, 2 = Custom Event
            evt_type = e.get("SI_EVENT_TYPE")
            if isinstance(evt_type, dict):
                evt_type = evt_type.get("value")

            if str(evt_type) == "0":
                file_count += 1
            elif str(evt_type) == "1":
                sched_count += 1
            elif str(evt_type) == "2":
                custom_count += 1
            else:
                # Fallback check based on name
                name = (e.get("SI_NAME") or "").lower()
                if "file" in name:
                    file_count += 1
                elif "custom" in name:
                    custom_count += 1
                else:
                    sched_count += 1

        return {
            "File Based": file_count,
            "Custom Events": custom_count,
            "Scheduled Events": sched_count
        }
    except Exception as exc:
        print(f"Failed to get Event counts from CMS: {exc}")
        return {"File Based": 0, "Custom Events": 0, "Scheduled Events": 0}


# ---------------------------------------------------------------------------
# Schedule Destination Extraction for Web Intelligence Documents
# ---------------------------------------------------------------------------

def get_all_webi_document_ids(session, limit=100) -> list[int]:
    """Retrieve all Web Intelligence document IDs via Raylight API.
    Uses pagination with the provided limit; returns a flat list of integer IDs.
    """
    offset = 0
    ids: list[int] = []
    while True:
        path = f"/documents?offset={offset}&limit={limit}"
        try:
            data = get_raylight(session, path)
        except Exception as exc:
            print(f"[WARN] get_raylight failed for {path}: {exc}")
            break

        # Normally: {"documents": {"document": [...]}}
        # Some BOBJ versions/edge cases return the list directly under
        # "document" without the outer "documents" wrapper, or return a
        # single dict instead of a list when there's only one document.
        container = data.get("documents", data)
        docs = container.get("document", [])
        if isinstance(docs, dict):
            docs = [docs]
        if not docs:
            if offset == 0:
                print(f"[DEBUG] No documents found. Raw response: {str(data)[:600]}")
            break

        for doc in docs:
            # Expect 'id' field; some BOBJ versions return it as a string.
            doc_id = doc.get("id")
            if doc_id is None:
                continue
            try:
                ids.append(int(doc_id))
            except (TypeError, ValueError):
                print(f"[WARN] Could not parse document id: {doc_id!r}")

        if len(docs) < limit:
            break
        offset += limit

    print(f"[DEBUG] Found {len(ids)} WebI document id(s): {ids[:20]}{' ...' if len(ids) > 20 else ''}")
    return ids


def get_schedules_for_document(session, document_id: int) -> list[dict]:
    """Return schedule entries for a given document."""
    path = f"/documents/{document_id}/schedules"
    try:
        data = get_raylight(session, path)
    except Exception as exc:
        print(f"[WARN] get_raylight failed for {path}: {exc}")
        return []

    container = data.get("schedules", data)
    raw = container.get("schedule", [])
    # API may return a single dict instead of a list when there is only one schedule
    if isinstance(raw, dict):
        raw = [raw]
    result = raw if isinstance(raw, list) else []
    if not result:
        print(f"[DEBUG] No schedules for document {document_id}. Raw response: {str(data)[:400]}")
    return result


# def get_schedule_detail(session, document_id: int, schedule_id: int) -> dict:
#     """Fetch detailed information for a specific schedule."""
#     path = f"/documents/{document_id}/schedules/{schedule_id}"
#     return get_raylight(session, path)


# def _classify_destination(detail: dict) -> str:
#     """Inspect schedule detail and return a high-level destination type.

#     BOBJ Raylight schedule detail response structure mirrors the XML schema
#     used to CREATE schedules (POST /documents/{id}/schedules), where the
#     <destination> element's children are named after the actual delivery
#     mechanism, e.g.:

#         <destination keepInstanceInHistory="true">
#             <mail>...</mail>          <-- NOTE: "mail", not "email"
#         </destination>

#         <destination>
#             <inbox/>
#         </destination>

#         <destination>
#             <ftp>...</ftp>            <-- or <sftp>
#         </destination>

#         <destination>
#             <unmanagedDisk>...</unmanagedDisk>   <-- or <managedDisk>/<fileSystem>
#         </destination>

#     When BOBJ serializes this to JSON, the same child element names carry
#     over as dict keys, e.g.:
#         {
#           "schedule": {
#             "destination": {
#               "keepInstanceInHistory": true,
#               "mail": { ... }
#             }
#           }
#         }

#     The previous version of this function only looked for a key literally
#     named "email", which never matches BOBJ's actual "mail" key — causing
#     every schedule to fall through to "Other"/"Not configured". This version
#     recognizes all the real BOBJ destination element names.
#     """
#     # Unwrap the top-level "schedule" key if present
#     schedule_obj = detail.get("schedule", detail)

#     # Primary: check structured 'destinations' / 'destination' block
#     destinations = schedule_obj.get("destinations") or schedule_obj.get("destination")
#     if isinstance(destinations, dict):
#         dest_keys = {k.lower() for k in destinations.keys()}
#         if "mail" in dest_keys or "email" in dest_keys or "smtp" in dest_keys:
#             return "Email"
#         if "ftp" in dest_keys or "sftp" in dest_keys:
#             return "FTP"
#         if dest_keys & {
#             "manageddisk", "unmanageddisk", "disk", "filesystem",
#             "file_system", "diskunmanaged", "diskmanaged",
#         }:
#             return "File System"
#         if "inbox" in dest_keys or "biinbox" in dest_keys:
#             return "BI Inbox"

#     # Secondary: recursively scan all keys/values for known destination hints
#     def scan(obj, depth=0):
#         if depth > 6:
#             return None
#         if isinstance(obj, dict):
#             for k, v in obj.items():
#                 kl = k.lower()
#                 if kl in ("mail", "email", "smtp"):
#                     return "Email"
#                 if kl in ("ftp", "sftp"):
#                     return "FTP"
#                 if kl in (
#                     "manageddisk", "unmanageddisk", "disk", "filesystem",
#                     "file_system", "diskunmanaged", "diskmanaged",
#                 ):
#                     return "File System"
#                 if kl in ("inbox", "biinbox", "bi_inbox"):
#                     return "BI Inbox"
#                 result = scan(v, depth + 1)
#                 if result:
#                     return result
#         elif isinstance(obj, str):
#             tl = obj.lower()
#             if "mail" in tl:  # catches "email" and "mail" alike
#                 return "Email"
#             if "ftp" in tl or "sftp" in tl:
#                 return "FTP"
#             if "filesystem" in tl or "manageddisk" in tl or "file system" in tl or "disk" in tl:
#                 return "File System"
#             if "inbox" in tl:
#                 return "BI Inbox"
#         return None

#     found = scan(schedule_obj)
#     if found:
#         return found

#     # Debug: log the raw detail so we can identify the real structure
#     import json as _json
#     print(f"[DEBUG] Unknown destination structure: {_json.dumps(detail, default=str)[:600]}")
#     return "Other"


# def get_schedule_destination_counts(session) -> dict:
#     """Aggregate destination types across all Web Intelligence document schedules.
#     Returns a mapping like {"Email": 12, "File System": 34, ...}.
#     """
#     counts: dict[str, int] = {}
#     doc_ids = get_all_webi_document_ids(session)

#     schedules_seen = 0
#     for doc_id in doc_ids:
#         sched_list = get_schedules_for_document(session, doc_id)
#         for sched in sched_list:
#             sched_id = sched.get("scheduleId") or sched.get("id")
#             if sched_id is None:
#                 print(f"[WARN] Schedule entry for doc {doc_id} has no id: {sched}")
#                 continue
#             try:
#                 sched_id = int(sched_id)
#             except Exception:
#                 print(f"[WARN] Could not parse schedule id {sched_id!r} for doc {doc_id}")
#                 continue
#             schedules_seen += 1
#             try:
#                 detail = get_schedule_detail(session, doc_id, sched_id)
#             except Exception as exc:
#                 print(f"[WARN] Could not fetch schedule {sched_id} for doc {doc_id}: {exc}")
#                 continue
#             dest_type = _classify_destination(detail)
#             counts[dest_type] = counts.get(dest_type, 0) + 1

#     print(f"[DEBUG] Processed {schedules_seen} schedule(s) across {len(doc_ids)} document(s). Destination counts: {counts}")
#     return counts