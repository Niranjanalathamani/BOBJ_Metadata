"""
folders.py

Utility functions for fetching folder information and
building complete BusinessObjects folder paths.
"""

from utils.infostore import run_paginated_cmsquery


def build_folder_map(session):
    """
    Fetch all folders and create a lookup dictionary.
    """

    query = """
    SELECT
        SI_ID,
        SI_NAME,
        SI_PARENTID
    FROM CI_INFOOBJECTS
    WHERE SI_KIND='Folder'
    """

    folders = run_paginated_cmsquery(session, query)

    folder_map = {}

    for folder in folders:

        folder_map[folder["SI_ID"]] = {
            "name": folder["SI_NAME"],
            "parent": folder["SI_PARENTID"]
        }

    print(f"[FOLDERS] Loaded {len(folder_map)} folders.")

    return folder_map


def get_folder_path(folder_id, folder_map):
    """
    Build the complete folder path from a folder id.
    """

    if not folder_id:
        return "/"

    path_parts = []

    current = folder_id

    while current in folder_map:

        folder = folder_map[current]

        path_parts.insert(0, folder["name"])

        parent = folder["parent"]

        if parent == current:
            break

        current = parent

    return "/" + "/".join(path_parts)


def get_report_folder_path(report, folder_map):
    """
    Return the folder path for a report dictionary.
    """

    return get_folder_path(
        report.get("SI_PARENTID"),
        folder_map
    )