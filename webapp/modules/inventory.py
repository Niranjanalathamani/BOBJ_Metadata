"""
modules/inventory.py
Platform Inventory
"""

from collections import Counter
from datetime import datetime, timedelta

from utils.infostore import run_paginated_cmsquery


# ---------------------------------------------------------
# USERS
# ---------------------------------------------------------

def get_users(session):
    """
    Returns all CMS users.
    """

    query = """
    SELECT
        SI_ID,
        SI_NAME,
        SI_USERFULLNAME,
        SI_EMAIL_ADDRESS,
        SI_ALIASES,
        SI_LASTLOGONTIME,
        SI_DISABLED
    FROM CI_SYSTEMOBJECTS
    WHERE SI_KIND='User'
    ORDER BY SI_NAME
    """

    entries = run_paginated_cmsquery(session, query)

    users = []

    for e in entries:

        # print("--------------------------------")
        # print("NAME:", e.get("SI_NAME"))
        # print("ALIASES:", repr(e.get("SI_ALIASES")))
        # print("DISABLED:", repr(e.get("SI_DISABLED")))
        # print("LASTLOGIN:", repr(e.get("SI_LASTLOGONTIME")))

        aliases = e.get("SI_ALIASES", {})

        alias_text = ""
        disabled = False

        if isinstance(aliases, dict):

            total = aliases.get("SI_TOTAL", 0)

            for i in range(1, total + 1):

                alias = aliases.get(str(i), {})

                alias_name = alias.get("SI_NAME", "")
                alias_text += alias_name + ";"

                if alias.get("SI_DISABLED", False):
                    disabled = True

        users.append({

            "ID": e.get("SI_ID"),
            "Name": e.get("SI_NAME"),
            "FullName": e.get("SI_USERFULLNAME"),
            "Email": e.get("SI_EMAIL_ADDRESS"),
            "Aliases": alias_text,
            "Disabled": disabled,
            "LastLogin": e.get("SI_LASTLOGONTIME")

        })

    return users

# ---------------------------------------------------------
# USER SUMMARY
# ---------------------------------------------------------

def get_user_summary(session):

    users = get_users(session)

    summary = {

        "total": len(users),

        "enabled": 0,
        "disabled": 0,
        "recentLogin": 0,

        "enterprise": 0,
        "windows": 0,
        "ldap": 0,
        "sap": 0

    }

    cutoff = datetime.now() - timedelta(days=90)

    for user in users:

        #
        # Enabled / Disabled
        #

        if user["Disabled"]:
            summary["disabled"] += 1
        else:
            summary["enabled"] += 1

        #
        # Authentication
        #

        aliases = user["Aliases"].lower()

        if "secenterprise:" in aliases:
            summary["enterprise"] += 1

        if "secwinad:" in aliases:
            summary["windows"] += 1

        if "secldap:" in aliases:
            summary["ldap"] += 1

        if "secsapr3:" in aliases:
            summary["sap"] += 1

        #
        # Recent Login
        #

        last = user["LastLogin"]

        if last:

            try:

                if isinstance(last, datetime):

                    login = last

                else:

                    login = datetime.strptime(
                        last,
                        "%b %d, %Y, %I:%M %p"
                    )

                if login >= cutoff:
                    summary["recentLogin"] += 1

            except Exception:
                pass

    return summary


# ---------------------------------------------------------
# AUTHENTICATION TYPES
# ---------------------------------------------------------

# def get_auth_type_count(session):

#     s = get_user_summary(session)

#     details = {}

#     if s["enterprise"]:

#         details["Enterprise"] = s["enterprise"]

#     if s["windows"]:

#         details["Windows AD"] = s["windows"]

#     if s["ldap"]:

#         details["LDAP"] = s["ldap"]

#     if s["sap"]:

#         details["SAP"] = s["sap"]

#     return {

#         "count": len(details),

#         "details": details

#     }


# ---------------------------------------------------------
# RELATIONAL CONNECTIONS
# ---------------------------------------------------------

def get_relational_connections(session):

    query = """
    SELECT
        SI_CONNECTION_DATABASE,
        SI_CONNECTION_IS_OLAP
    FROM CI_APPOBJECTS
    WHERE SI_SPECIFIC_KIND='CCIS.DataConnection'
    """

    entries = run_paginated_cmsquery(session, query)

    counter = Counter()

    for e in entries:

        if e.get("SI_CONNECTION_IS_OLAP"):
            continue

        db = str(
            e.get("SI_CONNECTION_DATABASE", "Unknown")
        ).upper()

        if "ORACLE" in db:

            name = "Oracle"

        elif "SQL SERVER" in db or "MICROSOFT SQL" in db:

            name = "SQL Server"

        elif "XML" in db:

            name = "XML Files"

        elif "JDBC" in db:

            name = "Generic JDBC"

        elif "HANA" in db:

            name = "SAP HANA"

        elif "SNOWFLAKE" in db:

            name = "Snowflake"

        elif "POSTGRES" in db:

            name = "PostgreSQL"

        elif "MYSQL" in db:

            name = "MySQL"

        elif "BIGQUERY" in db:

            name = "Google BigQuery"

        else:

            name = db.title()

        counter[name] += 1

    return {

        "count": sum(counter.values()),

        "details": dict(
            sorted(counter.items(), key=lambda x: x[1], reverse=True)
        )

    }


# ---------------------------------------------------------
# PLACE HOLDERS
# ---------------------------------------------------------

def get_bi_version(session):

    return None


def get_license_information(session):

    query = """
    SELECT
        SI_LICENSE_COUNT,
        SI_LICENSE_TYPE,
        SI_EXPIRY_DATE
    FROM CI_SYSTEMOBJECTS
    WHERE SI_PROGID='CrystalEnterprise.LicenseKey'
    """

    entries = run_paginated_cmsquery(session, query)

    total_named = 0
    total_concurrent = 0
    expiry_dates = []

    for e in entries:

        count = int(e.get("SI_LICENSE_COUNT", 0))
        license_type = int(e.get("SI_LICENSE_TYPE", -1))

        # Your environment mapping
        if license_type == 0:
            total_named += count

        elif license_type == 1:
            total_concurrent += count

        expiry = e.get("SI_EXPIRY_DATE")

        if isinstance(expiry, datetime):
            # Ignore SAP permanent licenses (1999)
            if expiry.year > 2005:
                expiry_dates.append(expiry)

    if expiry_dates:
        earliest_expiry = min(expiry_dates).strftime("%d-%b-%Y")
    else:
        earliest_expiry = "Permanent"

    return {
        "totalKeys": len(entries),
        "named": total_named,
        "concurrent": total_concurrent,
        "expiry": earliest_expiry
    }