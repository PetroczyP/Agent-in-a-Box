"""Validation sample: WARN — broad exception handling.

Expected finding:
  severity: WARN
  category: correctness
  rule_id: broad-except (or similar)
"""

import json


def load_config(path: str) -> dict:
    """Load configuration from a JSON file."""
    try:
        with open(path) as f:
            return json.load(f)
    except:  # noqa: E722  # WARN: bare except catches everything including KeyboardInterrupt
        return {}
