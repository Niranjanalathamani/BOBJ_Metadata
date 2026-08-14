"""
schedules.py
--------------------
Fetches scheduled report instance counts from BOBJ.
"""

from utils.infostore import get_cms_count, run_cmsquery, run_paginated_cmsquery
from utils.raylight import get_raylight


from utils.infostore import get_cms_count


def get_schedule_summary(session):
    """
    Returns the schedule summary for the dashboard.
    """

    total = get_cms_count(
        session,
        """
        SELECT COUNT(SI_ID)
        FROM CI_INFOOBJECTS
        WHERE SI_INSTANCE = 1 AND
        SI_SCHEDULE_STATUS IN (1, 3, 9)
        """
    )

    success = get_cms_count(
        session,
        """
        SELECT COUNT(SI_ID)
        FROM CI_INFOOBJECTS
        WHERE SI_INSTANCE=1
        AND SI_SCHEDULE_STATUS=1
        """
    )

    failed = get_cms_count(
        session,
        """
        SELECT COUNT(SI_ID)
        FROM CI_INFOOBJECTS
        WHERE SI_INSTANCE=1
        AND SI_SCHEDULE_STATUS=3
        """
    )

    recurring = get_cms_count(
        session,
        """
        SELECT COUNT(SI_ID)
        FROM CI_INFOOBJECTS
        WHERE SI_INSTANCE=1
        AND SI_SCHEDULE_STATUS=9
        """
    )

    return {

        "total": total,
        "success": success,
        "failed": failed,
        "recurring": recurring

    }

def get_event_counts(session):

        query = """
        SELECT
            SI_ID,
            SI_NAME,
            SI_SPECIFIC_KIND
        FROM CI_SYSTEMOBJECTS
        WHERE SI_KIND='Event'
        """

        entries = run_paginated_cmsquery(session, query)

        counts = {
            "Custom Events": 0,
            "File Events": 0,
            "Schedule Events": 0,
            "Monitoring Events": 0,
            "Other": 0
        }

        for e in entries:

            kind = str(e.get("SI_SPECIFIC_KIND", "")).lower()

            if "customevent" in kind:
                counts["Custom Events"] += 1

            elif "fileevent" in kind:
                counts["File Events"] += 1

            elif "scheduleevent" in kind:
                counts["Schedule Events"] += 1

            elif "monitoringevent" in kind:
                counts["Monitoring Events"] += 1

            else:
                counts["Other"] += 1
                print(f"Unknown Event Type : {kind}")

        print("Event Counts:", counts)

        return counts
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


def get_schedule_detail(session, document_id: int, schedule_id: int) -> dict:
    """Fetch detailed information for a specific schedule."""
    path = f"/documents/{document_id}/schedules/{schedule_id}"
    return get_raylight(session, path)


def _classify_destination(detail: dict) -> str:
    """Inspect schedule detail and return a high-level destination type.

    BOBJ Raylight schedule detail response structure mirrors the XML schema
    used to CREATE schedules (POST /documents/{id}/schedules), where the
    <destination> element's children are named after the actual delivery
    mechanism, e.g.:

        <destination keepInstanceInHistory="true">
            <mail>...</mail>          <-- NOTE: "mail", not "email"
        </destination>

        <destination>
            <inbox/>
        </destination>

        <destination>
            <ftp>...</ftp>            <-- or <sftp>
        </destination>

        <destination>
            <unmanagedDisk>...</unmanagedDisk>   <-- or <managedDisk>/<fileSystem>
        </destination>

    When BOBJ serializes this to JSON, the same child element names carry
    over as dict keys, e.g.:
        {
          "schedule": {
            "destination": {
              "keepInstanceInHistory": true,
              "mail": { ... }
            }
          }
        }

    The previous version of this function only looked for a key literally
    named "email", which never matches BOBJ's actual "mail" key — causing
    every schedule to fall through to "Other"/"Not configured". This version
    recognizes all the real BOBJ destination element names.
    """
    # Unwrap the top-level "schedule" key if present
    schedule_obj = detail.get("schedule", detail)

    # Primary: check structured 'destinations' / 'destination' block
    destinations = schedule_obj.get("destinations") or schedule_obj.get("destination")
    if isinstance(destinations, dict):
        dest_keys = {k.lower() for k in destinations.keys()}
        if "mail" in dest_keys or "email" in dest_keys or "smtp" in dest_keys:
            return "Email"
        if "ftp" in dest_keys or "sftp" in dest_keys:
            return "FTP"
        if dest_keys & {
            "manageddisk", "unmanageddisk", "disk", "filesystem",
            "file_system", "diskunmanaged", "diskmanaged",
        }:
            return "File System"
        if "inbox" in dest_keys or "biinbox" in dest_keys:
            return "BI Inbox"

    # Secondary: recursively scan all keys/values for known destination hints
    def scan(obj, depth=0):
        if depth > 6:
            return None
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                if kl in ("mail", "email", "smtp"):
                    return "Email"
                if kl in ("ftp", "sftp"):
                    return "FTP"
                if kl in (
                    "manageddisk", "unmanageddisk", "disk", "filesystem",
                    "file_system", "diskunmanaged", "diskmanaged",
                ):
                    return "File System"
                if kl in ("inbox", "biinbox", "bi_inbox"):
                    return "BI Inbox"
                result = scan(v, depth + 1)
                if result:
                    return result
        elif isinstance(obj, str):
            tl = obj.lower()
            if "mail" in tl:  # catches "email" and "mail" alike
                return "Email"
            if "ftp" in tl or "sftp" in tl:
                return "FTP"
            if "filesystem" in tl or "manageddisk" in tl or "file system" in tl or "disk" in tl:
                return "File System"
            if "inbox" in tl:
                return "BI Inbox"
        return None

    found = scan(schedule_obj)
    if found:
        return found

    # Debug: log the raw detail so we can identify the real structure
    import json as _json
    print(f"[DEBUG] Unknown destination structure: {_json.dumps(detail, default=str)[:600]}")
    return "Other"


def get_schedule_destination_counts(session):

    query = """
    SELECT
        SI_ID,
        SI_NAME,
        SI_SCHEDULEINFO.SI_DESTINATIONS
    FROM CI_INFOOBJECTS
    WHERE SI_INSTANCE = 1
    AND SI_SCHEDULE_STATUS IN (1, 3, 9)
    """

    entries = run_paginated_cmsquery(session, query)

    if not entries:
        print("No schedule instances returned.")
        return {
            "Email": 0,
            "BI Inbox": 0,
            "File System": 0,
            "FTP": 0,
            "SFTP": 0,
            "Other": 0
        }

    print("First Entry:")
    print(entries[0])

    counts = {
        "Email": 0,
        "BI Inbox": 0,
        "File System": 0,
        "FTP": 0,
        "SFTP": 0,
        "Other": 0
    }

    print(f"Instances retrieved : {len(entries)}")

    for entry in entries:

        # Your BI2025/standard BOBJ returns SI_SCHEDULEINFO
        schedule_info = entry.get("SI_SCHEDULEINFO") or entry.get("SCHEDULING_INFO") or {}

        destinations = schedule_info.get("SI_DESTINATIONS")

        if not destinations:
            counts["Other"] += 1
            continue

        total = destinations.get("SI_TOTAL", 0)
        if total == 0:
            counts["Other"] += 1
            continue

        for i in range(1, total + 1):

            dest = destinations.get(str(i), {})
            progid = str(dest.get("SI_PROGID", "")).lower()

            # Check if 'inbox' is present anywhere in the destination parameters
            has_inbox_hint = any(
                "inbox" in str(k).lower() or "inbox" in str(v).lower()
                for k, v in dest.items()
            )

            # Email
            if "smtp" in progid:
                counts["Email"] += 1

            # BI Inbox
            elif "inbox" in progid or has_inbox_hint:
                counts["BI Inbox"] += 1

            # File System
            elif (
                "filesystem" in progid
                or "diskunmanaged" in progid
                or "diskmanaged" in progid
                or "file" in progid
            ):
                counts["File System"] += 1

            # SFTP
            elif "sftp" in progid:
                counts["SFTP"] += 1

            # FTP
            elif "ftp" in progid:
                counts["FTP"] += 1

            # Unknown
            else:
                print("Unknown Destination:", progid)
                counts["Other"] += 1

    print("Destination Counts:", counts)

    return counts