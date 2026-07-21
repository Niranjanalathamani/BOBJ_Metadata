import requests


class APIClient:

    def __init__(self, token):
        
        self.token = token

    def headers(self, accept="application/json"):

        return {
            "X-SAP-LogonToken": self.token,
            "Accept": accept,
            "Content-Type": "application/json"
        }

    def get(self, url):

        response = requests.get(
            url,
            headers=self.headers()
        )

        response.raise_for_status()

        return response.json()

    def get_text(self, url):

        response = requests.get(
            url,
            headers=self.headers("application/xml")
        )

        response.raise_for_status()

        return response.text