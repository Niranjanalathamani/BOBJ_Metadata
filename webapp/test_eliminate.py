import sys
import os
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import config
    from auth import BOBJSession
    from utils.infostore import run_paginated_cmsquery
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def main():
    session = BOBJSession(config.BOBJ_BASE_URL)
    
    # Try using the alternative credentials (dganas2 / Incture123!)
    username = "dganas2"
    password = "Incture123!"
    auth_type = "secEnterprise"
    
    print(f"Trying to login as {username}...")
    try:
        session.login(username, password, auth_type)
    except Exception as e:
        print(f"Login as {username} failed: {e}")
        print("Retrying with config credentials...")
        try:
            session.login(config.BOBJ_USERNAME, config.BOBJ_PASSWORD, config.BOBJ_AUTH_TYPE)
        except Exception as e2:
            print(f"Login with config credentials failed: {e2}")
            return

    # Testing exclusions with standard SQL operators:
    query = "SELECT SI_ID, SI_NAME, SI_PARENTID FROM CI_INFOOBJECTS WHERE SI_KIND='Webi' AND SI_INSTANCE=0 AND SI_PARENTID != 6108"
    entries = run_paginated_cmsquery(session, query)
    
    print("\n--- ELIMINATING TEMPORARY COPIES ---")
    print(f"Query: {query}")
    print(f"Total parent Webi reports (excluding 6108): {len(entries)}")
    
    print("\nAll Original Reports:")
    print(f"{'Index':<6} | {'ID':<8} | {'Parent ID':<10} | Name")
    print("-" * 60)
    for idx, entry in enumerate(entries, 1):
        name = entry.get("SI_NAME") or entry.get("title") or "Unnamed"
        sid = entry.get("SI_ID") or entry.get("id") or "No ID"
        pid = entry.get("SI_PARENTID") or "N/A"
        print(f"{idx:<6} | {sid:<8} | {pid:<10} | {name}")

if __name__ == "__main__":
    main()
