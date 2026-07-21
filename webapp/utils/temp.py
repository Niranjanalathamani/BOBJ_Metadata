# import sys
# import os

# # MUST be at the top BEFORE importing modules from parent webapp folder
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# from utils.login import login
# from utils.api_client import APIClient
# import config

# token = login()

# client = APIClient(
#     config.BOBJ_BASE_URL,
#     token
# )

# response = client.get(
#     f"{config.BOBJ_BASE_URL}/raylight/v1/documents?offset=0&limit=2"
# )

# print(response)