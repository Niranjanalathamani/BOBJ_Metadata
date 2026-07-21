"""
modules/reports.py
------------------
Fetches report inventory counts from BOBJ CMS via cmsquery, with full
pagination so counts reflect the TRUE total, not just the first page
(BOBJ's REST API caps each page at 50 records server-side regardless of
the pagesize you request).
"""
from utils.infostore import run_paginated_cmsquery


def _fetch_by_kind(session, si_kind: str) -> list[dict]:
    """Run a paginated CMS query for a given SI_KIND and normalize results."""
    query = f"SELECT SI_ID, SI_NAME, SI_KIND FROM CI_INFOOBJECTS WHERE SI_KIND='{si_kind}' AND SI_INSTANCE = 0"
    docs = []
    try:
        entries = run_paginated_cmsquery(session, query)
        if isinstance(entries, dict):
            entries = [entries]
        for e in entries:
            docs.append({
                "ID": e.get("SI_ID") or e.get("id"),
                "Name": e.get("SI_NAME") or e.get("title"),
            })
    except Exception as exc:
        print(f"[WARN] Failed to get '{si_kind}' reports from CMS Query: {exc}")
    return docs


def get_webi_reports(session) -> list[dict]:
    """Fetch ALL Web Intelligence (Webi) reports (paginated, full total)."""
    docs = _fetch_by_kind(session, "Webi")
    return[
        {"id":d["ID"], "name":d["Name"]} 
        for d in docs
    ]


def get_crystal_reports(session) -> list[dict]:
    """Fetch ALL Crystal Reports (paginated, full total)."""
    docs = _fetch_by_kind(session, "CrystalReport")
    print(f"Crystal CMS query count = {len(docs)}")
    return docs


def get_analysis_reports(session) -> list[dict]:
    """
    TODO: confirm the SI_KIND value your CMS uses for Analysis / SAP Analysis
    for OLAP workspaces before wiring this up (varies by BI platform version).
    """
    return []


def get_dashboards(session) -> list[dict]:
    """
    TODO: confirm the SI_KIND value for Dashboards / Design Studio apps
    in your CMS (commonly something like "DesignStudio" or "Dashboard").
    """
    return []


def get_lumira_reports(session) -> list[dict]:
    """TODO: confirm the SI_KIND value for Lumira documents in your CMS."""
    return []