"""
modules/visualizations.py
-------------------------
Fetches and counts Visualization and Table elements under the "Body" PageZone
(including those nested within Sections) for Web Intelligence documents via the
BOBJ Raylight REST API.
"""

import xml.etree.ElementTree as ET
import requests
from config import BOBJ_BASE_URL


def fetch_visualization_counts(session, doc_id) -> dict:
    """
    Fetch all report tabs for a document, and for each tab, fetch its elements
    and count the Visualization and XTable elements whose parentId traces back
    to the 'Body' PageZone.
    Returns a dictionary mapping report tab names to a dict of counts:
    { "Report Tab Name": {"visualizations": X, "tables": Y} }
    """
    if not doc_id:
        return {}

    reports_url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/reports"
    headers = {
        "X-SAP-LogonToken": session.token,
        "Accept": "application/json"
    }

    counts = {}
    try:
        res = requests.get(reports_url, headers=headers, timeout=15)
        if res.status_code != 200:
            return {}

        data = res.json()
        reports = data.get("reports", {}).get("report", [])
        if isinstance(reports, dict):
            reports = [reports]

        # Use Accept: application/xml for XML element fetching
        xml_headers = {
            "X-SAP-LogonToken": session.token,
            "Accept": "application/xml"
        }

        for rep in reports:
            rep_id = rep.get("id")
            rep_name = rep.get("name", f"Report {rep_id}")
            if rep_id is None:
                continue

            elements_url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/reports/{rep_id}/elements"
            try:
                elem_res = requests.get(elements_url, headers=xml_headers, timeout=15)
                if elem_res.status_code == 200:
                    xml_text = elem_res.text
                    root = ET.fromstring(xml_text)

                    # Build parent mapping & find the Body PageZone ID
                    parent_map = {}  # element_id -> parent_id
                    body_zone_id = None
                    elements_to_check = []

                    for elem in root.findall("element"):
                        elem_type = elem.attrib.get("type")
                        id_node = elem.find("id")
                        parent_node = elem.find("parentId")

                        elem_id = id_node.text if id_node is not None else None
                        parent_id = parent_node.text if parent_node is not None else None

                        if elem_id:
                            parent_map[elem_id] = parent_id

                        if elem_type == "PageZone":
                            name_node = elem.find("name")
                            if name_node is not None and name_node.text == "Body":
                                body_zone_id = elem_id
                        
                        elements_to_check.append({
                            "type": elem_type,
                            "id": elem_id
                        })

                    # Helper to check if an element traces back to the Body PageZone
                    def traces_to_body(elem_id):
                        if not body_zone_id or not elem_id:
                            return False
                        current = elem_id
                        visited = set()
                        while current in parent_map:
                            if current in visited:  # Prevent cycles
                                break
                            visited.add(current)
                            parent = parent_map[current]
                            if parent == body_zone_id:
                                return True
                            current = parent
                        return False

                    # Count Visualizations and Tables
                    vis_count = 0
                    table_count = 0

                    for item in elements_to_check:
                        elem_type = item["type"]
                        elem_id = item["id"]

                        if traces_to_body(elem_id):
                            if elem_type == "Visualization":
                                vis_count += 1
                            elif elem_type == "XTable" or (elem_type and "Table" in elem_type):
                                table_count += 1

                    counts[rep_name] = {
                        "visualizations": vis_count,
                        "tables": table_count
                    }
                else:
                    counts[rep_name] = {"visualizations": 0, "tables": 0}
            except Exception as ex:
                print(f"[VISUALIZATION] Failed fetching elements for doc {doc_id} report {rep_id}: {ex}")
                counts[rep_name] = {"visualizations": 0, "tables": 0}

    except Exception as ex:
        print(f"[VISUALIZATION] Failed fetching sub-reports for doc {doc_id}: {ex}")

    return counts
