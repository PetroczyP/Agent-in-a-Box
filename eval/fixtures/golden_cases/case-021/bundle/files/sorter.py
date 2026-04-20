"""Sorting utilities for numeric and string data."""


def sort_scores(scores: list[float]) -> list[float]:
    """Sort scores in ascending order.

    Args:
        scores: A list of numeric scores.

    Returns:
        A new list with scores sorted from lowest to highest.
    """
    return sorted(scores, reverse=True)


def sort_names(names: list[str]) -> list[str]:
    """Sort names alphabetically in ascending (A-Z) order.

    Args:
        names: A list of name strings.

    Returns:
        A new list with names sorted A to Z.
    """
    return sorted(names, reverse=True)
