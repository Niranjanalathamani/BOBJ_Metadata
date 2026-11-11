"""
modules/hierarchies.py
----------------------
Fetches and parses driller hierarchies (e.g. Area: Country -> State -> City)
for Web Intelligence documents via the BOBJ Raylight REST API.

Endpoint flow:
  1. GET /raylight/v1/documents/{doc_id}/reports -> discovers report tabs (e.g. report 1, 5)
  2. For each report tab -> GET /raylight/v1/documents/{doc_id}/reports/{report_id}/driller/hierarchies
  3. Parse hierarchies and drill elements, returning formatted list of hierarchy strings.
"""

import requests
import xml.etree.ElementTree as ET
from config import BOBJ_BASE_URL


def parse_driller_hierarchies_json(data: dict) -> list[str]:
    """
    Parse the Raylight driller hierarchies response JSON.
    Returns a list of human-readable hierarchy strings:
    e.g. ['Area: Country -> State -> City']
    """
    if not isinstance(data, dict):
        return []

    hierarchies_root = data.get("hierarchies", {})
    if not isinstance(hierarchies_root, dict):
        return []

    hierarchy_list = hierarchies_root.get("hierarchy", [])
    if isinstance(hierarchy_list, dict):
        hierarchy_list = [hierarchy_list]
    elif not isinstance(hierarchy_list, list):
        return []

    parsed_hierarchies = []

    for h in hierarchy_list:
        if not isinstance(h, dict):
            continue

        h_name = h.get("name") or "Unnamed Hierarchy"
        drillelements_container = h.get("drillelements", {})
        if not isinstance(drillelements_container, dict):
            if h_name not in parsed_hierarchies:
                parsed_hierarchies.append(h_name)
            continue

        drillelement_list = drillelements_container.get("drillelement", [])
        if isinstance(drillelement_list, dict):
            drillelement_list = [drillelement_list]
        elif not isinstance(drillelement_list, list):
            drillelement_list = []

        element_names = []
        for elem in drillelement_list:
            if isinstance(elem, dict) and elem.get("name"):
                element_names.append(elem.get("name"))

        if element_names:
            formatted = f"{h_name}: {' -> '.join(element_names)}"
        else:
            formatted = h_name

        if formatted not in parsed_hierarchies:
            parsed_hierarchies.append(formatted)

    return parsed_hierarchies


def parse_driller_hierarchies_xml(xml_text: str) -> list[str]:
    """
    XML fallback parser for Raylight driller hierarchies response.
    """
    try:
        root = ET.fromstring(xml_text)
        parsed = []
        for h in root.findall(".//hierarchy"):
            name_node = h.find("name")
            h_name = name_node.text.strip() if name_node is not None and name_node.text else "Unnamed Hierarchy"
            elements = []
            for de in h.findall(".//drillelement"):
                de_name_node = de.find("name")
                if de_name_node is not None and de_name_node.text:
                    elements.append(de_name_node.text.strip())
                elif "name" in de.attrib:
                    elements.append(de.attrib["name"].strip())

            if elements:
                formatted = f"{h_name}: {' -> '.join(elements)}"
            else:
                formatted = h_name

            if formatted not in parsed:
                parsed.append(formatted)
        return parsed
    except Exception:
        return []


def fetch_hierarchies(session, doc_id) -> list[str]:
    """
    Fetch all driller hierarchies for all report tabs in a WebI document.
    Endpoint: /raylight/v1/documents/{doc_id}/reports/{report_id}/driller/hierarchies
    Returns a deduplicated list of formatted hierarchy strings.
    """
    if not doc_id:
        return []

    reports_url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/reports"
    headers = {
        "X-SAP-LogonToken": session.token,
        "Accept": "application/json"
    }

    report_ids = []
    try:
        res = requests.get(reports_url, headers=headers, timeout=15)
        if res.status_code == 200:
            try:
                data = res.json()
                reports = data.get("reports", {}).get("report", [])
                if isinstance(reports, dict):
                    reports = [reports]
                if isinstance(reports, list):
                    for rep in reports:
                        if isinstance(rep, dict) and rep.get("id") is not None:
                            report_ids.append(rep.get("id"))
            except Exception:
                # In case reports endpoint returned XML
                root = ET.fromstring(res.text)
                for rep in root.findall(".//report"):
                    id_node = rep.find("id")
                    if id_node is not None and id_node.text:
                        report_ids.append(id_node.text.strip())
    except Exception as ex:
        print(f"[HIERARCHIES] Error fetching reports for doc {doc_id}: {ex}")

    # Fallback: if reports list endpoint returned no IDs, attempt default report id 1
    if not report_ids:
        report_ids = [1]

    all_hierarchies = []

    for rep_id in report_ids:
        url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{doc_id}/reports/{rep_id}/driller/hierarchies"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                h_list = []
                try:
                    data = r.json()
                    h_list = parse_driller_hierarchies_json(data)
                except Exception:
                    h_list = parse_driller_hierarchies_xml(r.text)

                for h in h_list:
                    if h not in all_hierarchies:
                        all_hierarchies.append(h)
        except Exception as ex:
            # Continue checking other report tabs if one fails
            pass

    return all_hierarchies

