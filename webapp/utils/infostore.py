"""
utils/infostore.py
-------------------
Shared helper for querying the BOBJ InfoStore, with a pagination loop that
correctly walks every page (the platform caps each page at 50 records
regardless of what you ask for).
"""

import requests

MAX_PAGES = 500  # safety cap so a server-side quirk can never hang the app


def get_by_type(session, kind: str, page_size: int = 50, extra_params: dict | None = None) -> list[dict]:
    """
    GET /infostore?type=<kind>&page=<n>&pagesize=<page_size>

    Loops pages until a short page comes back (fewer than page_size records),
    which means you've reached the end.

    `kind` examples seen in your own scaffold notes:
      - "ConnectionObject"   → data connections
      - "Universe"           → classic .unv universes
      - "UniverseReferences" → .unx universes
      - "Webi"                → Web Intelligence documents
      - "CrystalReport"       → Crystal Reports
      - "Publication"         → publications
      - "User"                → system users
    """
    # IMPORTANT: no query string baked into the URL — page/pagesize live
    # ONLY in `params`, otherwise requests sends both and the server can
    # lock onto the stale page=1 value forever.
    url = f"{session.base_url}/infostore"
    all_entries: list[dict] = []
    page = 1

    while page <= MAX_PAGES:
        params = {"type": kind, "page": page, "pagesize": page_size}
        if extra_params:
            params.update(extra_params)

        response = requests.get(url, headers=session.headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        entries = data.get("entries", [])
        if isinstance(entries, dict):  # some CMS versions return a single dict, not a list, for 1 result
            entries = [entries]

        all_entries.extend(entries)

        if len(entries) < page_size:
            break
        page += 1
    else:
        print(f"[WARN] get_by_type('{kind}') hit MAX_PAGES safety cap ({MAX_PAGES}) — results may be incomplete")

    return all_entries


def run_cmsquery(session, query: str) -> dict:
    """
    POST /v1/cmsquery
    Executes a SELECT query against the CMS repository using BOBJ REST query service.
    Single call, first page only — used where you just need a quick peek or a
    COUNT(...) result, not a full paginated total.
    """
    url = f"{session.base_url}/v1/cmsquery"
    headers = session.headers().copy()
    headers["Content-Type"] = "application/json"

    payload = {"query": query}
    params = {"page": 1, "pagesize": 1000}
    response = requests.post(url, json=payload, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def run_paginated_cmsquery(session, query: str, page_size: int = 10000) -> list[dict]:
    """
    Executes a SELECT query against the CMS repository using BOBJ REST query service,
    looping pages until a short page comes back (fewer than page_size records).

    NOTE: The /v1/cmsquery endpoint does NOT reliably paginate via the `page`
    query parameter (unlike /infostore).  Requesting a large pagesize (10 000)
    ensures all results come back in a single response — matching the behaviour
    observed in Postman.  A deduplication step at the end guards against any
    residual overlap between pages.
    """
    url = f"{session.base_url}/v1/cmsquery"
    headers = session.headers().copy()
    headers["Content-Type"] = "application/json"
    payload = {"query": query}
    all_entries = []
    page = 1

    while page <= MAX_PAGES:
        params = {"page": page, "pagesize": page_size}
        response = requests.post(url, json=payload, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        entries = data.get("entries", [])

        if not entries:
            break

        if isinstance(entries, dict):
            entries = [entries]

        all_entries.extend(entries)

        if len(entries) < page_size:
            break
        page += 1
    else:
        print(f"[WARN] run_paginated_cmsquery hit MAX_PAGES safety cap ({MAX_PAGES}) — results may be incomplete")

    # ── Deduplicate by SI_ID to prevent inflated counts ──────────
    seen = set()
    unique = []
    for entry in all_entries:
        sid = entry.get("SI_ID") or entry.get("id")
        if sid is None or sid not in seen:
            if sid is not None:
                seen.add(sid)
            unique.append(entry)

    if len(unique) < len(all_entries):
        print(f"[INFO] run_paginated_cmsquery deduplicated {len(all_entries)} → {len(unique)} entries")

    return unique


def get_cms_count(session, query: str) -> int:
    """
    Executes a SELECT COUNT(...) query and attempts to extract the integer count
    from the response payload in a version-agnostic way.
    """
    try:
        res = run_cmsquery(session, query)
        entries = res.get("entries", [])
        if not entries:
            return 0
        entry = entries[0]

        def find_numeric(val):
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str) and val.isdigit():
                return int(val)
            if isinstance(val, dict):
                for v in val.values():
                    num = find_numeric(v)
                    if num is not None:
                        return num
            return None

        for val in entry.values():
            count = find_numeric(val)
            if count is not None:
                return count
        return len(entries)
    except Exception as exc:
        print(f"Failed to extract count from query: {exc}")
        return 0