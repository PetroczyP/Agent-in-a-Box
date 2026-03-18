"""Validation sample: BUG — division by zero.

Expected finding:
  severity: BUG
  category: correctness
  rule_id: division-by-zero (or similar)
"""


def calculate_average(numbers: list[int]) -> float:
    """Calculate the average of a list of numbers."""
    total = sum(numbers)
    return total / len(numbers)  # BUG: will raise ZeroDivisionError if numbers is empty
