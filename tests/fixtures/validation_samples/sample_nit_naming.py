"""Validation sample: NIT — naming convention issue.

Expected finding:
  severity: NIT
  category: style
  rule_id: naming-convention (or similar)
"""


def calcAvg(Data):  # NIT: should be snake_case (calc_avg), param should be lowercase (data)
    """Calculate average."""
    return sum(Data) / len(Data)
