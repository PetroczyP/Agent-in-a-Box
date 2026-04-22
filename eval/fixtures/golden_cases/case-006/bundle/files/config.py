import requests

API_KEY = "DUMMY_API_KEY_FOR_EVAL_FIXTURE_DO_NOT_USE"
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
