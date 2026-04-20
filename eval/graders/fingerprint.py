"""Tier 1 fingerprint grader for the eval harness.

Deterministic matching of actual findings against expected findings using
rule_id, file path, and line proximity. Fast and reproducible -- no API calls.
"""

from __future__ import annotations

from eval.models import (
    ExpectedFinding,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
)
from server.models import Finding


def grade_finding(
    finding: Finding,
    expected_findings: list[ExpectedFinding],
    line_tolerance: int = 5,
    claimed_expected_ids: set[str] | None = None,
) -> GraderResult | None:
    """Attempt to match a finding via fingerprint.

    Returns GraderResult if a match is found, None if no match
    (finding should be forwarded to Tier 2).

    The claimed_expected_ids set tracks which expected findings have already been
    matched. If an expected finding is already claimed, it's skipped. If a match
    is found, the expected ID is added to the set.
    """
    # Build list of (line_distance, index, expected) for all matching candidates.
    candidates: list[tuple[int, int, ExpectedFinding]] = []

    for idx, expected in enumerate(expected_findings):
        # Skip already-claimed expected findings.
        if claimed_expected_ids is not None and expected.expected_id in claimed_expected_ids:
            continue

        # All three conditions must hold.
        if finding.rule_id != expected.rule_id:
            continue
        if finding.primary_location.file != expected.file:
            continue

        line_distance = abs(finding.primary_location.start_line - expected.approximate_line)
        if line_distance > line_tolerance:
            continue

        candidates.append((line_distance, idx, expected))

    if not candidates:
        return None

    # Select best: smallest line distance, then earliest in expected list (index).
    candidates.sort(key=lambda c: (c[0], c[1]))
    _, _, best = candidates[0]

    # Track the claim.
    if claimed_expected_ids is not None:
        claimed_expected_ids.add(best.expected_id)

    # Determine verdict.
    severity_match = finding.severity == best.severity
    category_match = finding.category == best.category

    if severity_match and category_match:
        verdict = GraderVerdict.MATCH
    else:
        verdict = GraderVerdict.PARTIAL_MATCH

    return GraderResult(
        tier=1,
        verdict=verdict,
        confidence=GraderConfidence.HIGH,
        reasoning=None,
        matched_expected_id=best.expected_id,
        actual_finding_id=finding.finding_id,
    )
