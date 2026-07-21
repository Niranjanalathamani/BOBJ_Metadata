"""
auth.py
-------
Handles SAP BusinessObjects (BOBJ) login and logout via REST API.
Stores the session token used by all other modules.
"""

from itsdangerous import url_safe
from itsdangerous import url_safe
from itsdangerous import url_safe
from itsdangerous import url_safe
from itsdangerous import url_safe
from werkzeug.datastructures import headers
import requests
from xml.etree import ElementTree as ET

BIP_NS = {"b": "http://www.sap.com/rws/bip"}


class BOBJSession:
    """Holds a live BOBJ REST session token."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None

        # Platform capabilities
        self.capabilities = {
            "raylight": False,
        }

    # ---------------------------------------------------------
    # Login
    # ---------------------------------------------------------
    def login(self, username: str, password: str, auth_type: str = "secEnterprise") -> str:

        url = f"{self.base_url}/logon/long"
        print(url)

        body = (
            '<attrs xmlns="http://www.sap.com/rws/bip">'
            f'<attr name="userName" type="string">{_escape(username)}</attr>'
            f'<attr name="password" type="string">{_escape(password)}</attr>'
            f'<attr name="auth" type="string">{_escape(auth_type)}</attr>'
            '</attrs>'
        )

        headers = {
            "Content-Type": "application/xml;charset=utf-8",
            "Accept": "application/xml",
        }

        response = requests.post(
            url,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        token = response.headers.get("X-SAP-LogonToken")

        if not token:
            root = ET.fromstring(response.content)

            for attr in root.findall("b:attr", BIP_NS):
                if attr.get("name") == "logonToken":
                    token = attr.text
                    break

        if not token:
            raise RuntimeError(
                "Logon succeeded but no session token was returned."
            )

        self.token = token

        print("Login successful")

        # Detect available platform services
        self.detect_capabilities()

        return token

    # ---------------------------------------------------------
    # Capability Detection
    # ---------------------------------------------------------
    def detect_capabilities(self):
        """
        Detect optional REST services supported by this BI system.

        Crystal-only systems simply won't expose Raylight.
        """

        self.capabilities = {
            "raylight": False,
        }

        try:

            url = f"{self.base_url}/raylight/v1"

            response = requests.get(
                url,
                headers=self.headers(),
                timeout=10,
            )

            if response.status_code == 200:
                self.capabilities["raylight"] = True
                print("Raylight service detected.")

            else:
                print(
                    f"Raylight not available (HTTP {response.status_code}). "
                    "Continuing in Crystal-only mode."
                )

        except requests.RequestException:
            print("Raylight service unavailable. Continuing in Crystal-only mode.")

    # ---------------------------------------------------------
    # Logout
    # ---------------------------------------------------------
    def logoff(self):

        if not self.token:
            return

        try:
            requests.post(
                f"{self.base_url}/logoff",
                headers=self.headers(),
                timeout=10,
            )

        except requests.RequestException:
            pass

        finally:
            self.token = None

    # ---------------------------------------------------------
    # Headers
    # ---------------------------------------------------------
    def headers(self):

        return {
            "X-SAP-LogonToken": self.token or "",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def is_logged_in(self):

        return self.token is not None

    def has_raylight(self) -> bool:
        return self.capabilities.get("raylight", False)


def _escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
 
   