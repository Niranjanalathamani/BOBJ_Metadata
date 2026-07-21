"""
app.py
------
Flask backend for the Assessment Details dashboard.

ALL BOBJ REST calls (login + data collection) happen HERE, on the server.
The browser never sees BOBJ credentials or a token — it only ever calls
this local server's own /api/* endpoints, which return plain JSON.

Run:
    pip install -r requirements.txt
    python app.py
Then open:
    http://localhost:5000
"""

from flask import Flask, jsonify, send_from_directory, request

import config
import atexit
from auth import BOBJSession
from modules import universes
from modules import connections
from modules import reports
from modules import publications
from modules import schedules
from modules import inventory
from modules import metadata
from modules import report_details

from threading import Lock
import io
from flask import send_file


app = Flask(__name__, static_folder="static", static_url_path="")

# Single shared session, held in server memory only.
_session: BOBJSession | None = None
_session_lock = Lock()

def get_session(force: bool = False) -> BOBJSession:
    global _session

    if force or _session is None or not _session.is_logged_in():

        with _session_lock:

            # Double-check after acquiring the lock
            if _session is None or not _session.is_logged_in():

                _session = BOBJSession(config.BOBJ_BASE_URL)

                _session.login(
                    config.BOBJ_USERNAME,
                    config.BOBJ_PASSWORD,
                    config.BOBJ_AUTH_TYPE
                )

    return _session


def error_response(exc: Exception, status: int = 502):
    return jsonify({"error": str(exc)}), status



@app.route("/reports")
def report_details_page():

    return send_from_directory(
        "static",
        "reports.html"
    )
# ── Static frontend ──────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/users")
def api_users():
    try:
        session = get_session()
        return jsonify(inventory.get_users(session))

    except Exception as exc:
        return error_response(exc)
        
# ── API: Auth ────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def api_login():
    """Create a new BOBJ session (Log On). Uses config values."""
    try:
        # Force login (creates new session if none)
        get_session()
        return jsonify({"message": "Logged in"})
    except Exception as exc:
        return error_response(exc)

@app.route("/api/logout", methods=["POST"])
def api_logout():
    global _session
    if _session:
        try:
            _session.logoff()
        except Exception:
            pass
        _session = None
    return jsonify({"message": "Logout successful"})


# ── API: Platform Overview ───────────────────────────────────────
@app.route("/api/platform")
def api_platform():
    try:
        session = get_session()

        #
        # User information (queried once)
        #
        user_summary = inventory.get_user_summary(session)

        auth_details = {}

        if user_summary["enterprise"] > 0:
            auth_details["Enterprise"] = user_summary["enterprise"]

        if user_summary["windows"] > 0:
            auth_details["Windows AD"] = user_summary["windows"]

        if user_summary["ldap"] > 0:
            auth_details["LDAP"] = user_summary["ldap"]

        if user_summary["sap"] > 0:
            auth_details["SAP"] = user_summary["sap"]

        #
        # Connections
        #
        all_connections = connections.get_connections(session)
        ds_split = connections.split_by_datasource_type(all_connections)

        return jsonify({

            "biVersion": inventory.get_bi_version(session),

            "relationalConnections": ds_split["relational"],

            "olapConnections": ds_split["olap"],

            "authTypes": {
                "count": len(auth_details),
                "details": auth_details
            },

            "totalUsers": {
                "count": user_summary["total"],
                "enabled": user_summary["enabled"],
                "disabled": user_summary["disabled"],
                "recentLogin": user_summary["recentLogin"]
            },

            "licenseKeys": inventory.get_license_information(session)

        })

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return error_response(exc)

#── API: Universe Inventory (DISABLED) ──────────────────────────
@app.route("/api/universes")
def api_universes():
    try:
        session = get_session()

        all_universes, raw_list = universes.get_universes(session)
        unv_count = sum(1 for u in all_universes if u["Type"] == "UNV")
        unx_count = sum(1 for u in all_universes if u["Type"] == "UNX")
        source_split = universes.count_source_split(raw_list)
        linked = universes.get_linked_universe_count(session)

        return jsonify({
            "total": len(all_universes),
            "byType": [
                {"label": "UNV", "value": unv_count},
                {"label": "UNX", "value": unx_count},
            ],
            "bySource": [
                {"label": "Single-sourced", "value": source_split["single"]},
                {"label": "Multi-sourced (MSU)", "value": source_split["multi"]},
            ],
            "linked": linked,
        })
    except Exception as exc:  # noqa: BLE001
        return error_response(exc)




# ── API: Reports Inventory ───────────────────────────────────────
@app.route("/api/reports") 
def api_reports():
    try:
        session = get_session()

        webi = reports.get_webi_reports(session)
        crystal = reports.get_crystal_reports(session)
        analysis = reports.get_analysis_reports(session)
        dashboards = reports.get_dashboards(session)
        lumira = reports.get_lumira_reports(session)

        pubs = publications.get_publications(session)
        pub_destinations = publications.get_destination_type_counts(session)
        sched_summary = schedules.get_schedule_summary(session)
        events = schedules.get_event_counts(session)
        try:
            schedule_destinations = schedules.get_schedule_destination_counts(session)
        except Exception as exc:
            print(f"[WARN] Failed to fetch schedule destinations: {exc}")
            schedule_destinations = {}

        # Ensure we always have the four standard destination types
        merged_destinations: dict[str, int | None] = {
            "Email": None,
            "FTP": None,
            "File System": None,
            "BI Inbox": None,
        }
        # Layer publication destinations on top
        for k, v in pub_destinations.items():
            if v is not None:
                merged_destinations[k] = (merged_destinations.get(k) or 0) + v
        # Layer schedule destinations on top
        for k, v in schedule_destinations.items():
            if v is not None:
                merged_destinations[k] = (merged_destinations.get(k) or 0) + v

        return jsonify({
            "types": [
                {"label": "Web Intelligence", "value": len(webi)},
                {"label": "Crystal Reports", "value": len(crystal)},
                {"label": "Analysis", "value": len(analysis) or None},
                {"label": "Dashboards", "value": len(dashboards) or None},
                {"label": "Lumira", "value": len(lumira) or None},
            ],
            "publications": len(pubs),
            "scheduledReports": sched_summary.get("total"),
            "destinations": [
                {"label": k, "value": v} for k, v in merged_destinations.items()
            ],
            "events": [
                {"label": k, "value": v} for k, v in events.items()
            ],
        })
    except Exception as exc:  # noqa: BLE001
        return error_response(exc)


@app.route("/api/reports/metadata")
def api_reports_metadata():
    """Fetch $metadata (dimensions & measures) for all WebI documents."""
    try:
        session = get_session()
        results = metadata.get_all_metadata(session)
        return jsonify(results)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return error_response(exc)


@app.route("/api/reports/list")
def api_reports_list():
    """Fetch report inventory grouped by type with WebI metadata."""
    try:
        session = get_session()
        return jsonify(report_details.get_report_list(session))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return error_response(exc)


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )

def cleanup():

    global _session
    if _session:

        print("Logging off BusinessObjects...")

        try:
            _session.logoff()
        except Exception:
            pass
        _session = None
