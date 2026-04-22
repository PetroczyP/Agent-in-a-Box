"""Tests for the Tier 1 fingerprint grader (T003)."""

from __future__ import annotations

from eval.graders.fingerprint import grade_finding
from eval.models import (
    ExpectedFinding,
    GraderConfidence,
    GraderVerdict,
)
from server.models import (
    Category,
    Finding,
    Location,
    Severity,
)


# --- Helpers ---


def _make_finding(
    *,
    finding_id: str = "F-001",
    rule_id: str = "sql-injection",
    severity: Severity = Severity.BUG,
    category: Category = Category.SECURITY,
    file: str = "src/main.py",
    start_line: int = 10,
    end_line: int = 15,
) -> Finding:
    return Finding(
        finding_id=finding_id,
        rule_id=rule_id,
        severity=severity,
        category=category,
        message="Test finding",
        primary_location=Location(file=file, start_line=start_line, end_line=end_line),
        fingerprint="fp-hash",
        confidence="high",
        evidence="Test evidence",
    )


def _make_expected(
    *,
    expected_id: str = "EF-001",
    rule_id: str = "sql-injection",
    severity: Severity = Severity.BUG,
    category: Category = Category.SECURITY,
    file: str = "src/main.py",
    approximate_line: int = 10,
) -> ExpectedFinding:
    return ExpectedFinding(
        expected_id=expected_id,
        rule_id=rule_id,
        severity=severity,
        category=category,
        file=file,
        approximate_line=approximate_line,
        description="Test expected finding",
    )


# --- Tests ---


class TestExactMatch:
    """Finding matches expected: same rule_id, file, line within tolerance, severity, category."""

    def test_exact_match_returns_grader_result(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]

        result = grade_finding(finding, expected)

        assert result is not None
        assert result.verdict == GraderVerdict.MATCH
        assert result.confidence == GraderConfidence.HIGH
        assert result.matched_expected_id == "EF-001"
        assert result.actual_finding_id == "F-001"
        assert result.tier == 1
        assert result.reasoning is None


class TestPartialMatchSeverity:
    """Rule_id + file + line match, but severity differs -> partial_match."""

    def test_severity_mismatch_returns_partial_match(self) -> None:
        finding = _make_finding(severity=Severity.WARN)
        expected = [_make_expected(severity=Severity.BUG)]

        result = grade_finding(finding, expected)

        assert result is not None
        assert result.verdict == GraderVerdict.PARTIAL_MATCH
        assert result.confidence == GraderConfidence.HIGH
        assert result.matched_expected_id == "EF-001"
        assert result.tier == 1


class TestPartialMatchCategory:
    """Rule_id + file + line match, but category differs -> partial_match."""

    def test_category_mismatch_returns_partial_match(self) -> None:
        finding = _make_finding(category=Category.CORRECTNESS)
        expected = [_make_expected(category=Category.SECURITY)]

        result = grade_finding(finding, expected)

        assert result is not None
        assert result.verdict == GraderVerdict.PARTIAL_MATCH
        assert result.confidence == GraderConfidence.HIGH
        assert result.matched_expected_id == "EF-001"
        assert result.tier == 1


class TestNoMatch:
    """Wrong rule_id -> no match, returns None."""

    def test_wrong_rule_id_returns_none(self) -> None:
        finding = _make_finding(rule_id="buffer-overflow")
        expected = [_make_expected(rule_id="sql-injection")]

        result = grade_finding(finding, expected)

        assert result is None

    def test_wrong_file_returns_none(self) -> None:
        finding = _make_finding(file="src/other.py")
        expected = [_make_expected(file="src/main.py")]

        result = grade_finding(finding, expected)

        assert result is None


class TestLineTolerance:
    """Line distance exactly at tolerance -> match; one beyond -> None."""

    def test_at_tolerance_boundary_matches(self) -> None:
        finding = _make_finding(start_line=15)
        expected = [_make_expected(approximate_line=10)]

        result = grade_finding(finding, expected, line_tolerance=5)

        assert result is not None
        assert result.verdict == GraderVerdict.MATCH

    def test_beyond_tolerance_returns_none(self) -> None:
        finding = _make_finding(start_line=16)
        expected = [_make_expected(approximate_line=10)]

        result = grade_finding(finding, expected, line_tolerance=5)

        assert result is None

    def test_negative_direction_at_boundary_matches(self) -> None:
        finding = _make_finding(start_line=5)
        expected = [_make_expected(approximate_line=10)]

        result = grade_finding(finding, expected, line_tolerance=5)

        assert result is not None
        assert result.verdict == GraderVerdict.MATCH

    def test_negative_direction_beyond_boundary_returns_none(self) -> None:
        finding = _make_finding(start_line=4)
        expected = [_make_expected(approximate_line=10)]

        result = grade_finding(finding, expected, line_tolerance=5)

        assert result is None


class TestDefaultLineTolerance:
    """Default line_tolerance is 5."""

    def test_default_tolerance_is_five(self) -> None:
        finding = _make_finding(start_line=15)
        expected = [_make_expected(approximate_line=10)]

        # No explicit line_tolerance -> should use default of 5
        result = grade_finding(finding, expected)

        assert result is not None
        assert result.verdict == GraderVerdict.MATCH

    def test_default_tolerance_six_beyond(self) -> None:
        finding = _make_finding(start_line=16)
        expected = [_make_expected(approximate_line=10)]

        result = grade_finding(finding, expected)

        assert result is None


class TestMultipleMatchResolution:
    """Multiple expected findings match -> smallest line distance wins."""

    def test_closest_line_wins(self) -> None:
        finding = _make_finding(start_line=12)
        expected = [
            _make_expected(expected_id="EF-001", approximate_line=10),  # distance 2
            _make_expected(expected_id="EF-002", approximate_line=13),  # distance 1
        ]

        result = grade_finding(finding, expected)

        assert result is not None
        assert result.matched_expected_id == "EF-002"

    def test_tie_broken_by_expected_order(self) -> None:
        finding = _make_finding(start_line=12)
        expected = [
            _make_expected(expected_id="EF-001", approximate_line=10),  # distance 2
            _make_expected(expected_id="EF-002", approximate_line=14),  # distance 2
        ]

        result = grade_finding(finding, expected)

        assert result is not None
        assert result.matched_expected_id == "EF-001"


class TestClaimedExpectedIds:
    """Already-claimed expected findings are skipped."""

    def test_claimed_id_skipped(self) -> None:
        finding = _make_finding()
        expected = [_make_expected(expected_id="EF-001")]
        claimed: set[str] = {"EF-001"}

        result = grade_finding(finding, expected, claimed_expected_ids=claimed)

        assert result is None

    def test_match_adds_to_claimed_set(self) -> None:
        finding = _make_finding()
        expected = [_make_expected(expected_id="EF-001")]
        claimed: set[str] = set()

        result = grade_finding(finding, expected, claimed_expected_ids=claimed)

        assert result is not None
        assert "EF-001" in claimed

    def test_falls_through_to_unclaimed(self) -> None:
        finding = _make_finding(start_line=12)
        expected = [
            _make_expected(expected_id="EF-001", approximate_line=10),  # distance 2
            _make_expected(expected_id="EF-002", approximate_line=13),  # distance 1
        ]
        # EF-002 is closest but claimed; should fall through to EF-001
        claimed: set[str] = {"EF-002"}

        result = grade_finding(finding, expected, claimed_expected_ids=claimed)

        assert result is not None
        assert result.matched_expected_id == "EF-001"
        assert "EF-001" in claimed

    def test_none_claimed_set_still_works(self) -> None:
        """When claimed_expected_ids is None (default), matching works normally."""
        finding = _make_finding()
        expected = [_make_expected()]

        result = grade_finding(finding, expected, claimed_expected_ids=None)

        assert result is not None
        assert result.verdict == GraderVerdict.MATCH


class TestEmptyExpectedFindings:
    """Empty expected findings list -> None."""

    def test_empty_expected_returns_none(self) -> None:
        finding = _make_finding()

        result = grade_finding(finding, [])

        assert result is None
