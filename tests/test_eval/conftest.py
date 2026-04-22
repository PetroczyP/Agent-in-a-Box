"""Shared test fixtures for eval harness tests."""

from __future__ import annotations

import pytest

from eval.models import (
    ExpectedFinding,
    GoldenCase,
    GoldenCaseSource,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
    MetricWithSEM,
    TrialMetrics,
    TrialResult,
)
from server.models import (
    Category,
    Finding,
    Location,
    ReviewBundle,
    Severity,
)


@pytest.fixture
def sample_location() -> Location:
    return Location(file="src/main.py", start_line=10, end_line=15)


@pytest.fixture
def sample_finding(sample_location: Location) -> Finding:
    return Finding(
        finding_id="F-001",
        rule_id="sql-injection",
        severity=Severity.BUG,
        category=Category.SECURITY,
        message="SQL injection vulnerability",
        primary_location=sample_location,
        fingerprint="abc123",
        confidence="high",
        evidence="User input directly in query",
    )


@pytest.fixture
def sample_expected_finding() -> ExpectedFinding:
    return ExpectedFinding(
        expected_id="EF-001",
        rule_id="sql-injection",
        severity=Severity.BUG,
        category=Category.SECURITY,
        file="src/main.py",
        approximate_line=10,
        description="SQL injection in query builder",
    )


@pytest.fixture
def sample_review_bundle() -> ReviewBundle:
    return ReviewBundle(
        diff="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new",
        files={"main.py": "new content"},
    )


@pytest.fixture
def sample_golden_case(
    sample_review_bundle: ReviewBundle,
    sample_expected_finding: ExpectedFinding,
) -> GoldenCase:
    return GoldenCase(
        case_id="case-001",
        description="SQL injection in query builder",
        source=GoldenCaseSource.HAND_CURATED,
        tags=["security", "python"],
        bundle=sample_review_bundle,
        expected_findings=[sample_expected_finding],
    )


@pytest.fixture
def sample_grader_result() -> GraderResult:
    return GraderResult(
        tier=1,
        verdict=GraderVerdict.MATCH,
        confidence=GraderConfidence.HIGH,
        matched_expected_id="EF-001",
        actual_finding_id="F-001",
    )


@pytest.fixture
def sample_trial_metrics() -> TrialMetrics:
    return TrialMetrics(
        precision=0.8,
        recall=0.9,
        severity_accuracy=0.85,
        category_accuracy=0.75,
        snr=4.0,
        novel_count=1,
        grading_error_count=0,
        finding_count=5,
    )


@pytest.fixture
def sample_trial_result(
    sample_finding: Finding,
    sample_grader_result: GraderResult,
    sample_trial_metrics: TrialMetrics,
) -> TrialResult:
    return TrialResult(
        trial_number=1,
        findings=[sample_finding],
        graded=[sample_grader_result],
        metrics=sample_trial_metrics,
    )


@pytest.fixture
def sample_metric_with_sem() -> MetricWithSEM:
    return MetricWithSEM(
        mean=0.85,
        sem=0.03,
        ci_lower=0.85 - 1.96 * 0.03,
        ci_upper=0.85 + 1.96 * 0.03,
        passes_threshold=True,
    )
