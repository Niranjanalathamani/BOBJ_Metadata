"""
modules/publications.py
-----------------------
Fetches publication details from BOBJ CMC.
"""

from utils.infostore import get_by_type


def get_publications(session) -> list[dict]:
    """Returns all publications in the repository."""
    entries = get_by_type(session, "Publication")
    return [{"ID": e.get("id") or e.get("SI_ID"), "Name": e.get("title") or e.get("SI_NAME")} for e in entries]


def get_destination_type_counts(session) -> dict:
    """
    TODO: Destination type (Email / FTP / File System / BI Inbox) lives on
    each publication's schedule info, not the top-level listing above.
    You'll likely need a detail call per publication (GET /infostore/{id})
    and read its delivery-rule property to tally counts per destination.
    """
    return {"Email": None, "FTP": None, "File System": None, "BI Inbox": None}
