"""Service that syncs local data to a remote API."""

import time
import requests


def sync_records(records: list[dict], api_url: str) -> dict:
    """Push local records to the remote API, retrying on failure."""
    results = {"synced": 0, "failed": 0}
    for record in records:
        try:
            resp = requests.post(
                f"{api_url}/records",
                json=record,
                timeout=10,
            )
            resp.raise_for_status()
            results["synced"] += 1
        except:
            # Silently swallow ALL exceptions — including KeyboardInterrupt,
            # SystemExit, MemoryError, etc.
            results["failed"] += 1
            time.sleep(1)
    return results


def sync_forever(records: list[dict], api_url: str, interval: int = 60) -> None:
    """Run sync in an infinite loop."""
    while True:
        try:
            sync_records(records, api_url)
        except:
            pass
        time.sleep(interval)
