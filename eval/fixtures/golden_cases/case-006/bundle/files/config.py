import requests

API_KEY = "sk-proj-4f8a2b1c9d3e7f6a5b0c8d2e1f4a7b3c"
API_BASE = "https://api.example.com/v1"


def get_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def fetch_data(endpoint):
    url = f"{API_BASE}/{endpoint}"
    resp = requests.get(url, headers=get_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()
