# Assessment Details — BOBJ Dashboard (Backend-Driven)

All BOBJ REST calls (login + data collection) happen **on the server**
(`app.py` and `modules/*.py`). The browser page (`static/index.html`) never
sees BOBJ credentials or a session token — it only calls this local
backend's own `/api/*` endpoints and displays what comes back.

## Setup

```bash
pip install -r requirements.txt
```

Edit `config.py` (or set environment variables) with your real BOBJ server:

```bash
export BOBJ_BASE_URL="http://your-bobj-host:6405/biprws"
export BOBJ_USERNAME="Administrator"
export BOBJ_PASSWORD="your-password"
export BOBJ_AUTH_TYPE="secEnterprise"   # secEnterprise | secLDAP | secWinAD | secSAPR3
```

## Run

```bash
python app.py
```

Open **http://localhost:5000** in your browser and click **Run Assessment**.

## How the request order works

1. Browser clicks "Run Assessment" → calls `GET /api/platform`
2. Once that resolves and renders → calls `GET /api/universes`
3. Once that resolves and renders → calls `GET /api/reports`

Each backend endpoint logs into BOBJ once (session is cached and reused
across calls — see `get_session()` in `app.py`) and runs its own BOBJ REST
queries in `modules/*.py`, using the paginated `/infostore` helper in
`utils/infostore.py` that already accounts for the platform's 50-record
per-page cap.

## What's real vs. what needs your input

Fully implemented and working end-to-end:
- Login/session handling (`auth.py`) — XML payload format
- Paginated `/infostore?type=...` queries (`utils/infostore.py`)
- Universe count by type (UNV/UNX), WebI count, Crystal Reports count,
  Publications count, total Users count

Marked `# TODO` and returning `None` / "Not configured" until you fill
them in (each is a short comment explaining exactly what's needed):
- BI Version, Authentication Types, License Keys — these live in CMC
  admin/status resources, not `/infostore`
- Relational vs. OLAP connection split — needs the exact field name your
  CMS uses to distinguish datasource type
- Single vs. Multi-sourced universes, Linked (kernel) universes — needs a
  per-universe detail call or the right property name
- Analysis / Dashboards / Lumira counts — needs the exact `SI_KIND` value
  per report type in your CMS version
- Destination type breakdown, Event subtype breakdown — need per-item
  detail calls or the right property names

The frontend already renders these as "Not configured" cleanly, so you
can wire each one up independently without touching the UI code.
