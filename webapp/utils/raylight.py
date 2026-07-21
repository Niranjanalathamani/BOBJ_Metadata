import requests


def get_raylight(session, endpoint_path: str) -> dict:
    """Perform a GET request against the Raylight API.

    Args:
        session: BOBJSession object providing ``base_url`` and ``headers()``.
        endpoint_path: Path relative to the Raylight base, e.g. ``"/universes"``.

    Returns:
        Parsed JSON response as a dict. Raises ``requests.HTTPError`` on failure.
    """
    # Ensure leading slash
    if not endpoint_path.startswith('/'):
        endpoint_path = '/' + endpoint_path
    # Construct full URL: <base_url>/raylight/v1<endpoint_path>
    url = f"{session.base_url}/raylight/v1{endpoint_path}"
    response = requests.get(url, headers=session.headers(), timeout=30)
    response.raise_for_status()
    return response.json()
