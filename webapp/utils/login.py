import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from config import (
    BOBJ_BASE_URL,
    BOBJ_USERNAME,
    BOBJ_PASSWORD,
    BOBJ_AUTH_TYPE
)


def login():

    body = (
        '<attrs xmlns="http://www.sap.com/rws/bip">'
        f'<attr name="userName" type="string">{escape(BOBJ_USERNAME)}</attr>'
        f'<attr name="password" type="string">{escape(BOBJ_PASSWORD)}</attr>'
        f'<attr name="auth" type="string">{escape(BOBJ_AUTH_TYPE)}</attr>'
        '</attrs>'
    )

    headers = {
        "Content-Type": "application/xml;charset=utf-8",
        "Accept": "application/xml"
    }

    response = requests.post(
        f"{BOBJ_BASE_URL.rstrip('/')}/logon/long",
        data=body.encode("utf-8"),
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    token = response.headers.get("X-SAP-LogonToken")

    if token:
        return token

    root = ET.fromstring(response.content)

    ns = {
        "b": "http://www.sap.com/rws/bip"
    }

    for attr in root.findall("b:attr", ns):

        if attr.get("name") == "logonToken":

            return attr.text

    raise RuntimeError("Unable to obtain token")