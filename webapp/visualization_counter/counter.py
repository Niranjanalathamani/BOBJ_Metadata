"""
standalone visualization & table counter
----------------------------------------
Can be run directly: python counter.py <doc_id1> <doc_id2> ...
If no doc IDs are provided, it will count for all WebI documents in the repository.
"""

import os
import sys
import xml.etree.ElementTree as ET
import requests

# Add parent directory to path so we can import auth, config, and modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from auth import BOBJSession
from modules.visualizations import fetch_visualization_counts
from modules.metadata import fetch_webi_documents


def main():
    print("Initializing BusinessObjects Session...")
    session = BOBJSession(config.BOBJ_BASE_URL)
    try:
        session.login(
            config.BOBJ_USERNAME,
            config.BOBJ_PASSWORD,
            config.BOBJ_AUTH_TYPE
        )
        print("Logged in successfully.")
    except Exception as e:
        print(f"Failed to log in: {e}")
        sys.exit(1)

    # Determine which document IDs to query
    doc_ids = sys.argv[1:]
    if not doc_ids:
        print("No document IDs provided. Fetching all WebI documents from CMS...")
        try:
            docs = fetch_webi_documents(session)
            doc_ids = [d["id"] for d in docs]
            print(f"Found {len(doc_ids)} WebI documents.")
        except Exception as e:
            print(f"Failed to fetch documents: {e}")
            sys.exit(1)

    print("-" * 80)
    print(f"{'Document ID':<12} | {'Report Tab Name':<22} | {'Visualizations':<16} | {'Tables':<12}")
    print("-" * 80)

    for doc_id in doc_ids:
        try:
            counts = fetch_visualization_counts(session, doc_id)
            if not counts:
                print(f"{doc_id:<12} | {'No tabs/elements found':<22} | {'0':<16} | {'0':<12}")
            for tab_name, data in counts.items():
                vis = data.get("visualizations", 0)
                tbl = data.get("tables", 0)
                print(f"{doc_id:<12} | {tab_name:<22} | {vis:<16} | {tbl:<12}")
        except Exception as e:
            print(f"Error querying doc {doc_id}: {e}")

    # Logout
    try:
        session.logoff()
        print("Logged off successfully.")
    except Exception:
        pass


if __name__ == "__main__":
    main()
