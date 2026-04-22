import os
import json


def read_config(config_path: str) -> dict:
    """Read a JSON config file if it exists."""
    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r") as f:
        return json.load(f)


def write_config(config_path: str, data: dict) -> None:
    """Write config data to a JSON file."""
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)
