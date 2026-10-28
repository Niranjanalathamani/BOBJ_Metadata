"""
modules/report_details.py
--------------------------
Builds the report list grouped folder-wise or type-wise for the Report Details page.
Evaluates WebI reports folder by folder with caching and multi-threaded Raylight extraction.
"""

from collections import defaultdict
from modules import metadata
from modules.path import build_folder_map, get_report_folder_path
from utils.infostore import run_paginated_cmsquery


# Kinds fetched through the generic CMS query.
_CMS_KIND_TO_GROUP = {
    "CrystalReport": "Crystal Reports",
    "Analysis": "Analysis Reports",
    "Dashboard": "Dashboards",
    "Lumira": "Lumira Documents",
}

# Display order for type-based grouping
_GROUP_ORDER = [
    "Web Intelligence",
    "Crystal Reports",
    "Analysis Reports",
    "Dashboards",
    "Lumira Documents",
]


def get_non_webi_reports_list(session, folder_map) -> list[dict]:
    """Fetch Crystal / Analysis / Dashboard / Lumira reports via CMS query."""
    kinds = ", ".join(f"'{k}'" for k in _CMS_KIND_TO_GROUP)

    query = f"""
    SELECT
        SI_ID,
        SI_NAME,
        SI_KIND,
        SI_PARENTID
    FROM CI_INFOOBJECTS
    WHERE SI_KIND IN ({kinds})
      AND SI_INSTANCE = 0
    ORDER BY SI_PARENTID, SI_NAME
    """

    try:
        entries = run_paginated_cmsquery(session, query)
    except Exception as ex:
        print(f"[REPORT_DETAILS] Failed to query non-WebI reports: {ex}")
        entries = []

    reports = []
    for e in entries:
        kind = e.get("SI_KIND")
        group_name = _CMS_KIND_TO_GROUP.get(kind, kind)
        folder_path = get_report_folder_path(e, folder_map)

        reports.append({
            "id": e.get("SI_ID"),
            "name": e.get("SI_NAME"),
            "kind": group_name,
            "folder_path": folder_path,
            "dimensions": [],
            "measures": [],
            "filters": [],
            "variables": {},
            "dataproviders": [],
            "visualizations": {},
            "sql": [],
        })

    return reports


def get_report_list(session, folder_path: str | None = None, force: bool = False, group_by: str = "folder") -> dict:
    """
    Evaluates report inventory folder by folder.
    
    Parameters:
      - session: Active BOBJSession.
      - folder_path: Optional single folder to evaluate (e.g. "/Public Folders/Finance").
      - force: If True, bypasses cache and re-crawls folder by folder.
      - group_by: "folder" (default) or "type".
    
    Returns:
      A dictionary mapping folder paths (or report types) to list of report dictionaries.
    """
    folder_map = build_folder_map(session)
    webi_by_folder = metadata.get_metadata_by_folder(
        session,
        folder_map=folder_map,
        target_folder_path=folder_path,
        force=force
    )
    collection_meta = webi_by_folder.pop("_collection_meta", None)
    non_webi_reports = get_non_webi_reports_list(session, folder_map)

    if group_by == "folder":
        result = defaultdict(list)

        # 1. Attach evaluated WebI reports by folder
        for f_path, reports in webi_by_folder.items():
            if f_path == "_collection_meta" or not isinstance(reports, list):
                continue
            if folder_path and f_path != folder_path:
                continue
            result[f_path].extend(reports)

        # 2. Attach non-WebI reports to their respective folders
        for rep in non_webi_reports:
            f_path = rep.get("folder_path") or "/"
            if folder_path and f_path != folder_path:
                continue
            result[f_path].append(rep)

        # Sort folder names alphabetically, and reports inside each folder by name
        sorted_result = {}
        for f_path in sorted(result.keys()):
            sorted_result[f_path] = sorted(result[f_path], key=lambda r: (r.get("name") or "").lower())

        return sorted_result

    else:
        # Legacy grouping by report type
        flat_webi = []
        for f_path, reps in webi_by_folder.items():
            if f_path == "_collection_meta" or not isinstance(reps, list):
                continue
            flat_webi.extend(reps)

        grouped_non_webi = defaultdict(list)
        for rep in non_webi_reports:
            group_name = rep.get("kind", "Other")
            grouped_non_webi[group_name].append(rep)

        result = {"Web Intelligence": flat_webi}
        for group in _GROUP_ORDER[1:]:
            result[group] = grouped_non_webi.get(group, [])

        for k, v in grouped_non_webi.items():
            if k not in result:
                result[k] = v

        if collection_meta:
            result["_collection_meta"] = collection_meta

        return result
