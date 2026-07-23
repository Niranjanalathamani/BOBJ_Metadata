"""
modules/report_details.py
--------------------------
Builds the grouped report list for the Report Details page.
Fetches non-WebI reports from CMS query and WebI reports using metadata.py.
"""

from collections import defaultdict
from modules import metadata
from utils.infostore import run_paginated_cmsquery


# Kinds fetched through the generic CMS query.
_CMS_KIND_TO_GROUP = {
    "CrystalReport": "Crystal Reports",
    "Analysis": "Analysis Reports",
    "Dashboard": "Dashboards",
    "Lumira": "Lumira Documents",
}

# Display order for the page.
_GROUP_ORDER = [
    "Web Intelligence",
    "Crystal Reports",
    "Analysis Reports",
    "Dashboards",
    "Lumira Documents",
]


def get_non_webi_reports(session) -> dict:
    """Fetch Crystal / Analysis / Dashboard / Lumira reports via CMS query."""

    kinds = ", ".join(f"'{k}'" for k in _CMS_KIND_TO_GROUP)

    query = f"""
    SELECT
    SI_ID,
    SI_NAME,
    SI_KIND
    FROM CI_INFOOBJECTS
    WHERE SI_KIND IN ({kinds})
    AND SI_INSTANCE = 0
    AND SI_ID IN (16115, 8012, 18494, 18622)
    ORDER BY SI_ID, SI_NAME
    """

    entries = run_paginated_cmsquery(session, query)

    grouped = defaultdict(list)

    for e in entries:
        kind = e.get("SI_KIND")
        group = _CMS_KIND_TO_GROUP.get(kind, kind)

        grouped[group].append({
            "id": e.get("SI_ID"),
            "name": e.get("SI_NAME"),
            "dimensions": [],
            "measures": [],
        })

    return grouped


def get_report_list(session) -> dict:
    """Combine CMS-backed non-WebI reports with WebI metadata."""

    non_webi = get_non_webi_reports(session)
    webi_reports = metadata.get_all_metadata(session)

    result = {"Web Intelligence": webi_reports}
    for group in _GROUP_ORDER[1:]:
        result[group] = non_webi.get(group, [])

    for k, v in non_webi.items():
        if k not in result:
            result[k] = v

    return result
