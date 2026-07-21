"""
modules/connections.py
----------------------
Fetches Data Connections from the BusinessObjects CMS.

Unlike the previous implementation, this uses the CMS Query API instead
of Raylight, so it works in:

- Crystal Reports only environments
- Web Intelligence environments
- Mixed environments
"""

from utils.infostore import run_cmsquery
from collections import Counter

def get_connections(session) -> list[dict]:
    """ 
    Returns all CMS Data Connections.
    """

    query = """
    SELECT
        SI_NAME,
        SI_CONNECTION_DATABASE,
        SI_CONNECTION_IS_OLAP,
        SI_CREATION_TIME,
        SI_PARENTID
    FROM CI_APPOBJECTS
    WHERE SI_SPECIFIC_KIND='CCIS.DataConnection'
    """

    try:

        result = run_cmsquery(session, query)

        entries = result.get("entries", [])

        if isinstance(entries, dict):
            entries = [entries]

        connections = []

        for entry in entries:

            is_olap = entry.get("SI_CONNECTION_IS_OLAP")

            if isinstance(is_olap, str):
                is_olap = is_olap.lower() in ("true", "1", "yes")

            connections.append({
                "Name": entry.get("SI_NAME", ""),
                "Database": entry.get("SI_CONNECTION_DATABASE", ""),
                "Kind": "OLAP" if is_olap else "Relational",
                "Created": entry.get("SI_CREATION_TIME"),
                "ParentID": entry.get("SI_PARENTID")
            })

        print(f"Found {len(connections)} CMS Data Connection(s).")

        return connections

    except Exception as exc:
        print(f"Failed to retrieve CMS Data Connections: {exc}")
        return []

def normalize_database_name(db: str) -> str:
    """
    Normalize database names so similar technologies are grouped together.
    """

    if not db:
        return "Unknown"

    db = db.strip()
    upper = db.upper()

    if "ORACLE" in upper:
        return "Oracle"

    if "SQL SERVER" in upper or "MICROSOFT SQL" in upper:
        return "SQL Server"

    if "MYSQL" in upper:
        return "MySQL"

    if "POSTGRES" in upper:
        return "PostgreSQL"

    if "DB2" in upper:
        return "IBM DB2"

    if "SYBASE" in upper:
        return "SAP ASE"

    if "HANA" in upper:
        return "SAP HANA"

    if "BIGQUERY" in upper:
        return "Google BigQuery"

    if "SNOWFLAKE" in upper:
        return "Snowflake"

    if "JDBC" in upper:
        return "Generic JDBC"

    if "ODBC" in upper:
        return "ODBC"

    if "XML" in upper:
        return "XML Files"

    return db


def split_by_datasource_type(connections: list[dict]) -> dict:

    relational_counter = Counter()
    olap_counter = Counter()

    for conn in connections:

        db = normalize_database_name(conn.get("Database"))

        if conn.get("Kind") == "Relational":
            relational_counter[db] += 1

        elif conn.get("Kind") == "OLAP":
            olap_counter[db] += 1

    return {

        "relational": {
            "count": sum(relational_counter.values()),
            "details": dict(sorted(relational_counter.items()))
        },

        "olap": {
            "count": sum(olap_counter.values()),
            "details": dict(sorted(olap_counter.items()))
        }

    }