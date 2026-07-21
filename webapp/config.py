"""
config.py
---------
Server-side BOBJ connection settings. This file never leaves the backend —
the browser/frontend has no access to it and never sees these credentials.

For anything beyond local testing, pull these from environment variables
instead of hardcoding them here (e.g. os.environ["BOBJ_PASSWORD"]).
"""

import os

# BOBJ_BASE_URL = os.environ.get("BOBJ_BASE_URL", "http://CR25Reports.mambro.com:8080/biprws")
# BOBJ_USERNAME = os.environ.get("BOBJ_USERNAME", "dganas2")
# BOBJ_PASSWORD = os.environ.get("BOBJ_PASSWORD", "Incture123!")
# BOBJ_AUTH_TYPE = os.environ.get("BOBJ_AUTH_TYPE", "secEnterprise")  # secEnterprise | secLDAP | secWinAD | secSAPR3
BOBJ_BASE_URL = os.environ.get("BOBJ_BASE_URL", "http://103.67.236.46:8080/biprws")
BOBJ_USERNAME = os.environ.get("BOBJ_USERNAME", "niranjanaK")
BOBJ_PASSWORD = os.environ.get("BOBJ_PASSWORD", "Incture@2021")
BOBJ_AUTH_TYPE = os.environ.get("BOBJ_AUTH_TYPE", "secEnterprise")  # secEnterprise | secLDAP | secWinAD | secSAPR3
