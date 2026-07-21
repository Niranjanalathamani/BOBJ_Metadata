"""
modules/universes.py
--------------------
Fetches universe details from BOBJ CMC.
"""

from utils.infostore import get_by_type, run_paginated_cmsquery
from utils.raylight import get_raylight


def get_universes(session) -> tuple[list[dict], list[dict]]:
    """
    Returns all universes in the repository by querying the CMS via /biprws/v1/cmsquery.
    Returns:
        (processed_list, raw_list) — processed_list has ID/Name/Type dicts,
        raw_list is the combined CMS query results.
    """
    unx_query = "SELECT SI_ID, SI_NAME, SI_KIND FROM CI_APPOBJECTS WHERE SI_KIND='DSL.Universe'"
    unx_entries = run_paginated_cmsquery(session, unx_query)

    unv_query = "SELECT SI_ID, SI_NAME, SI_KIND FROM CI_APPOBJECTS WHERE SI_KIND='Universe'"
    unv_entries = run_paginated_cmsquery(session, unv_query)

    universes = []
    
    for u in unx_entries:
        universes.append({
            "ID": u.get("SI_ID"),
            "Name": u.get("SI_NAME"),
            "Type": "UNX"
        })
        
    for u in unv_entries:
        universes.append({
            "ID": u.get("SI_ID"),
            "Name": u.get("SI_NAME"),
            "Type": "UNV"
        })
        
    return universes, unx_entries + unv_entries


def _determine_type(universe_data: dict) -> str:
    """Placeholder implementation; types are determined from CMS queries.
    
    Returns an empty string because type is set directly in get_universes.
    """
    return ""
def count_source_split(raw_list: list[dict]) -> dict:
    """
    Splits universes into Single-sourced vs Multi-sourced (MSU).
    Operates on the already-fetched raw_list to avoid a duplicate API call.
    """
    multi = sum(1 for u in raw_list if (u.get("subType") or "").lower() == "multi-source")
    return {
        "single": len(raw_list) - multi,
        "multi": multi,
    }


def get_universe_source_split(session) -> dict:
    """
    Legacy helper — fetches universes itself. Prefer count_source_split(raw_list)
    when the raw list is already available.
    """
    data = get_raylight(session, "/universes")
    raw_list = data.get("universes", {}).get("universe", [])
    return count_source_split(raw_list)


def get_linked_universe_count(session) -> int | None:
    """
    TODO: Linked/derived universes (built on a kernel universe) are typically
    identified by a parent/kernel reference property on the universe object
    (e.g. SI_UNIVERSE_KERNEL or SI_PARENT_FOLDER for the linked structure).
    Confirm the exact property name against your CMS before wiring this up.
    """
    return None

