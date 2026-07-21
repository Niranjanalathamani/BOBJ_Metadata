"""
webicrawl.py

Fetches Web Intelligence metadata for the Report Details page.

Displays

    Report Name
    Report ID
    Dimensions
    Measures
    Variable Name
    Variable Formula


Uses the same APIClient architecture as the similarity engine.
"""

from urllib import response
from itsdangerous import url_safe
from itsdangerous import url_safe
from itsdangerous import url_safe
from datetime import datetime
import threading
import xml.etree.ElementTree as ET
from utils.api_client import APIClient
from utils.infostore import run_paginated_cmsquery

from config import BOBJ_BASE_URL



# ==========================================================
# INTERNAL STATE
# ==========================================================

_lock = threading.Lock()

_state = {

    "status": "idle",

    "processed": 0,

    "total": 0,

    "rows": [],

    "last_updated": None,

    "error": None

}
def get_state():

    with _lock:

        return {

            "status": _state["status"],

            "processed": _state["processed"],

            "total": _state["total"],

            "row_count": len(_state["rows"]),

            "last_updated": _state["last_updated"],

            "error": _state["error"]

        }


def get_rows():

    with _lock:

        return list(_state["rows"])


def reset_crawl():

    with _lock:

        _state["status"] = "idle"

        _state["processed"] = 0

        _state["total"] = 0

        _state["rows"] = []

        _state["last_updated"] = None

        _state["error"] = None

def metadata_url(cuid):

    cuid = str(cuid)

    if not cuid.startswith("cuid_"):

        cuid = "cuid_" + cuid

    return (

        f"{BOBJ_BASE_URL}/raylight/v1/documents/"

        f"{cuid}"

        "/datamodel/data.svc/$metadata"

    )


def variables_url(document_id):

    return (

        f"{BOBJ_BASE_URL}/raylight/v1/documents/"

        f"{document_id}"

        "/variables"

    )


def variable_definition_url(

    document_id,

    variable_id

):

    return (

        f"{BOBJ_BASE_URL}/raylight/v1/documents/"

        f"{document_id}"

        f"/variables/{variable_id}"

    )



def fetch_reports(session):

    query = """
    SELECT SI_ID,
           SI_NAME,
           SI_CUID
    FROM CI_INFOOBJECTS
    WHERE SI_KIND='Webi'
      AND SI_INSTANCE=0
    ORDER BY SI_NAME
    """

    reports = run_paginated_cmsquery(
        session,
        query
    )

    rows = []

    seen = set()

    for report in reports:

        report_id = report.get("SI_ID")

        if report_id in seen:

            continue

        seen.add(report_id)

        rows.append({

            "id": report_id,

            "name": report.get("SI_NAME"),

            "cuid": report.get("SI_CUID")

        })

    return rows
def start_crawl(session):

    with _lock:

        _state["status"] = "running"
        _state["rows"] = []
        _state["processed"] = 0
        _state["error"] = None

    try:

        reports = fetch_reports(session)

        api_client = APIClient(session.token)

        _state["total"] = len(reports)

        rows = []

        for report in reports:

            rows.extend(
                build_report_rows(
                    api_client,
                    report
                )
            )

            _state["processed"] += 1

        _state["rows"] = rows
        _state["status"] = "done"
        _state["last_updated"] = datetime.now().isoformat()
        print("------------------------------------")
        print("Report:", report["name"])
        print("ID:", report["id"])
        print("CUID:", report["cuid"])

        return rows

    except Exception as ex:

        _state["status"] = "error"
        _state["error"] = str(ex)
        raise
# ==========================================================
# METADATA (Dimensions / Measures)
# ==========================================================

def fetch_metadata_xml(
    api_client,
    cuid
):
    url = metadata_url(cuid)

    print("Metadata URL")
    print(url)

    xml = api_client.get_text(url)

    print(xml[:300])

    return xml  
   


def parse_metadata(

    xml_text

):

    dimensions = []

    measures = []

    root = ET.fromstring(xml_text)

    for element in root.iter():
        tag = element.tag.split("}")[-1]

        if tag != "Property":

            continue

        name = element.attrib.get("Name")

        if name:

            name = name.replace(

            "_x0020",

            " "

    )

        if not name:

            continue

        aggregation = ""

        for key, value in element.attrib.items():

            if key.endswith("aggregation-role"):

                aggregation = value.lower()

                break

        if aggregation == "measure":

            measures.append(name)

        else:

            dimensions.append(name)
        print("Dimensions found:", len(dimensions))
        print("Measures found:", len(measures))

    return (

        sorted(set(dimensions)),

        sorted(set(measures))

    )
def fetch_dimensions_measures(

    api_client,

    cuid

):

    try:

        xml = fetch_metadata_xml(

            api_client,

            cuid

        )

        return parse_metadata(

            xml

        )

    except Exception as ex:

        print(

            f"Metadata Error ({cuid}) : {ex}"

        )

        return [], []
# ==========================================================
# VARIABLES
# ==========================================================

def fetch_variables(
    api_client,
    document_id
):
    url = variables_url(document_id)

    print("Variables URL")
    print(url)

    try:
        response = api_client.get(url)

        print(response)

        variables = (
        response
        .get("variables", {})
        .get("variable", [])
    )

        if isinstance(variables, dict):
            variables = [variables]

        return variables
    except Exception as ex:
        print(f"Variables Error ({document_id}): {ex}")
        return []
# ==========================================================
# VARIABLE FORMULA
# ==========================================================

def fetch_variable_formula(

    api_client,

    document_id,

    variable_id

):

    try:

        response = api_client.get(

            variable_definition_url(

                document_id,

                variable_id

            )

        )

        variable = response.get(

            "variable",

            {}

        )

        return variable.get(

            "definition",

            ""

        )

    except Exception as ex:

        print(

            f"Variable Formula Error ({document_id}) : {ex}"

        )

        return ""
# ==========================================================
# BUILD REPORT ROWS
# ==========================================================

def build_report_rows(

    api_client,

    report

):

    dimensions, measures = fetch_dimensions_measures(

        api_client,

        report["cuid"]

    )

    variables = fetch_variables(

        api_client,

        report["id"]

    )

    rows = []

    # ------------------------------------------------------

    # No Variables

    # ------------------------------------------------------

    if not variables:

        rows.append({

            "Report Name":

                report["name"],

            "Report ID":

                report["id"],

            "Dimensions":

                ", ".join(dimensions),

            "Measures":

                ", ".join(measures),

            "Source Universe/Connections":

                "",

            "Filters":

                "",

            "Prompts":

                "",

            "Variable Name":

                "",

            "Variable Formula":

                ""

        })

        return rows

    # ------------------------------------------------------

    # Variables exist

    # ------------------------------------------------------

    for variable in variables:

        variable_id = variable.get("id")

        formula = ""

        if variable_id:

            formula = fetch_variable_formula(

                api_client,

                report["id"],

                variable_id

            )

        rows.append({

            "Report Name":

                report["name"],

            "Report ID":

                report["id"],

            "Dimensions":

                ", ".join(dimensions),

            "Measures":

                ", ".join(measures),

            "Source Universe/Connections":

                "",

            "Filters":

                "",

            "Prompts":

                "",

            "Variable Name":

                variable.get(

                    "name",

                    ""

                ),

            "Variable Formula":

                formula

        })

    return rows