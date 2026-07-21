"""
modules/report_details.py
--------------------------
Builds the grouped report list for the Report Details page.

Crystal / Analysis / Dashboard / Lumira reports are pulled from the CMS via
a single paginated cmsquery.

Web Intelligence (Webi) reports are handled separately by
get_webi_report_list(). This environment currently has no Webi repository to
query, so that function is a PLACEHOLDER — it returns sample data shaped
exactly like the real thing so the "Web Intelligence" group renders
correctly in the UI. Once you have the real endpoint (likely Raylight
`/raylight/v1/documents`, or a CMS query with SI_KIND='Webi' same as the
others), swap out the body of get_webi_report_list() only — nothing else
needs to change.
"""

from flask import blueprints
from collections import defaultdict
from modules import reports

from utils.infostore import run_paginated_cmsquery


# Kinds fetched through the generic CMS query. Webi is deliberately excluded
# here — see get_webi_report_list() below.
_CMS_KIND_TO_GROUP = {
    "CrystalReport": "Crystal Reports",
    "Analysis": "Analysis Reports",
    "Dashboard": "Dashboards",
    "Lumira": "Lumira Documents",
}

# Display order for the page, regardless of what order data comes back in.
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
    WHERE SI_KIND IN ({kinds}) AND SI_INSTANCE = 0
    ORDER BY SI_KIND, SI_NAME
    """

    entries = run_paginated_cmsquery(session, query)

    grouped = defaultdict(list)

    for e in entries:
        kind = e.get("SI_KIND")
        group = _CMS_KIND_TO_GROUP.get(kind, kind)

        grouped[group].append({
            "id": e.get("SI_ID"),
            "name": e.get("SI_NAME"),
        })

    return grouped


def get_report_list(session) -> dict:
    """Combine CMS-backed reports with the Webi list from background crawl, in a fixed group order."""

    non_webi = get_non_webi_reports(session)
    
    from modules import webicrawl
    crawl_rows = webicrawl.get_rows()
    print("Rows from webicrawl: len(crawl_rows)")
    if crawl_rows:
        print(crawl_rows[0])

    report_map = {}

    for row in crawl_rows:

        rid = row.get("Report ID")

        if rid not in report_map:

            report_map[rid] = {

                "id": rid,
                "name": row.get("Report Name", ""),

                "Dimensions": row.get("Dimensions", ""),
                "Measures": row.get("Measures", ""),
                "Source Universe/Connections": row.get("Source Universe/Connections", ""),
                "Filters": row.get("Filters", ""),
                "Prompts": row.get("Prompts", ""),

                "Variable Name": [],
                "Variable Formula": []
            }

        if row.get("Variable Name"):
            report_map[rid]["Variable Name"].append(
                row["Variable Name"]
            )

        if row.get("Variable Formula"):
            report_map[rid]["Variable Formula"].append(
                row["Variable Formula"]
            )

    webi_reports = list(report_map.values())

    if not webi_reports:
        # If no detailed rows are available yet, start the crawl and then
        # re-read the freshly crawled rows so the UI gets full details.
        webicrawl.start_crawl(session)
        crawl_rows = webicrawl.get_rows()

        if crawl_rows:
            # Rebuild report_map from the freshly crawled data
            report_map = {}
            for row in crawl_rows:
                rid = row.get("Report ID")
                if rid not in report_map:
                    report_map[rid] = {
                        "id": rid,
                        "name": row.get("Report Name", ""),
                        "Dimensions": row.get("Dimensions", ""),
                        "Measures": row.get("Measures", ""),
                        "Source Universe/Connections": row.get("Source Universe/Connections", ""),
                        "Filters": row.get("Filters", ""),
                        "Prompts": row.get("Prompts", ""),
                        "Variable Name": [],
                        "Variable Formula": []
                    }
                if row.get("Variable Name"):
                    report_map[rid]["Variable Name"].append(row["Variable Name"])
                if row.get("Variable Formula"):
                    report_map[rid]["Variable Formula"].append(row["Variable Formula"])
            webi_reports = list(report_map.values())
        else:
            # Fallback: no crawl data at all, use basic id+name list
            webi_reports = reports.get_webi_reports(session) or []

    result = {"Web Intelligence": webi_reports}
    for group in _GROUP_ORDER[1:]:
        result[group] = non_webi.get(group, [])

    # Catch-all for any SI_KIND we didn't explicitly map, so nothing silently vanishes.
    for k, v in non_webi.items():
        if k not in result:
            result[k] = v

    return result
