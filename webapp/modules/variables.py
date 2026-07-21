# """
# modules/variables.py
# --------------------
# Fetches variables and formulas for Web Intelligence reports via Raylight REST API.
# """

# import requests
# from config import BOBJ_BASE_URL


# def fetch_variables(session, report_id):
#     """
#     Fetch all variables and their definitions (formulas) for a report.

#     Returns a dict mapping {variable_name: definition_formula}
#     Example:
#       {
#         "Total Profit": "=[Revenue] - [Cost]",
#         "User Flag": "=If([Status]=\"Active\"; 1; 0)"
#       }
#     """
#     if not report_id:
#         return {}

#     variables_url = f"{BOBJ_BASE_URL}/raylight/v1/documents/{report_id}/variables"

#     try:
#         response = requests.get(
#             variables_url,
#             headers=session.headers(),
#             timeout=15
#         )
#         if response.status_code != 200:
#             return {}

#         data = response.json()
#         variable_list = (
#             data
#             .get("variables", {})
#             .get("variable", [])
#         )

#         if isinstance(variable_list, dict):
#             variable_list = [variable_list]

#         variables = {}

#         for variable in variable_list:
#             variable_id = variable.get("id")
#             variable_name = variable.get("name")

#             if not variable_id or not variable_name:
#                 continue

#             details_url = (
#                 f"{BOBJ_BASE_URL}/raylight/v1/documents/"
#                 f"{report_id}/variables/{variable_id}"
#             )

#             try:
#                 details_res = requests.get(
#                     details_url,
#                     headers=session.headers(),
#                     timeout=15
#                 )
#                 if details_res.status_code == 200:
#                     details = details_res.json()
#                     definition = (
#                         details
#                         .get("variable", {})
#                         .get("definition", "")
#                     )
#                     variables[variable_name] = definition
#                 else:
#                     variables[variable_name] = ""
#             except Exception as ex:
#                 print(f"[VARIABLES] Failed fetching details for var {variable_id} in report {report_id}: {ex}")
#                 variables[variable_name] = ""

#         return variables

#     except Exception as ex:
#         print(f"[VARIABLES] Failed fetching variables for report {report_id}: {ex}")
#         return {}
