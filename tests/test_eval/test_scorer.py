"""Tests for eval/scorer.py — T006 Scorer (metrics + SEM).

TDD RED phase: comprehensive tests for all scoring functions.
"""

from __future__ import annotations

import math
import statistics

import pytest

from eval.models import (
    AggregateMetrics,
    CaseResult,
    CIMethod,
    DualMetricResult,
    ExpectedFinding,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
    MetricWithSEM,
    RebuttalResult,
    TrialMetrics,
    TrialResult,
)
from eval.scorer import (
    aggregate_metrics,
    bca_ci,
    check_thresholds,
    compute_rebuttal_accuracy,
    compute_trial_metrics,
    metric_with_sem,
    wilson_ci,
)
from server.models import (
    Category,
    Finding,
    FindingStatus,
    Location,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    finding_id: str,
    severity: Severity = Severity.BUG,
    category: Category = Category.SECURITY,
    rule_id: str = "rule-1",
) -> Finding:
    """Create a minimal Finding for testing."""
    return Finding(
        finding_id=finding_id,
        rule_id=rule_id,
        severity=severity,
        category=category,
        message="test",
        primary_location=Location(file="f.py", start_line=1, end_line=2),
        fingerprint=f"fp-{finding_id}",
        confidence="high",
        evidence="evidence",
    )


def _expected(
    expected_id: str,
    severity: Severity = Severity.BUG,
    category: Category = Category.SECURITY,
    rule_id: str = "rule-1",
) -> ExpectedFinding:
    """Create a minimal ExpectedFinding for testing."""
    return ExpectedFinding(
        expected_id=expected_id,
        rule_id=rule_id,
        severity=severity,
        category=category,
        file="f.py",
        approximate_line=1,
        description="test",
    )


def _grader(
    verdict: GraderVerdict,
    actual_finding_id: str,
    matched_expected_id: str | None = None,
) -> GraderResult:
    """Create a minimal GraderResult for testing."""
    return GraderResult(
        tier=1,
        verdict=verdict,
        confidence=GraderConfidence.HIGH,
        matched_expected_id=matched_expected_id,
        actual_finding_id=actual_finding_id,
    )


# ===========================================================================
# metric_with_sem
# ===========================================================================


class TestMetricWithSEM:
    """Tests for the metric_with_sem helper."""

    def test_basic_computation(self) -> None:
        """Mean, SEM, CI bounds computed correctly."""
        values = [0.8, 0.9, 0.7, 0.85]
        result = metric_with_sem(values, threshold=0.70)

        expected_mean = sum(values) / len(values)
        expected_stdev = (
            sum((v - expected_mean) ** 2 for v in values) / (len(values) - 1)
        ) ** 0.5
        expected_sem = expected_stdev / math.sqrt(len(values))

        assert result.mean == pytest.approx(expected_mean)
        assert result.sem == pytest.approx(expected_sem)
        assert result.ci_lower == pytest.approx(expected_mean - 1.96 * expected_sem)
        assert result.ci_upper == pytest.approx(expected_mean + 1.96 * expected_sem)

    def test_single_value_sem_zero(self) -> None:
        """With a single value, SEM=0 and CI bounds equal the mean."""
        result = metric_with_sem([0.9], threshold=0.70)

        assert result.mean == pytest.approx(0.9)
        assert result.sem == pytest.approx(0.0)
        assert result.ci_lower == pytest.approx(0.9)
        assert result.ci_upper == pytest.approx(0.9)

    def test_gte_passes_when_ci_lower_above_threshold(self) -> None:
        """For direction='gte', passes when ci_lower >= threshold."""
        # All values well above threshold => ci_lower still above
        result = metric_with_sem([0.95, 0.96, 0.97, 0.98], threshold=0.70)
        assert result.passes_threshold is True

    def test_gte_fails_when_ci_lower_below_threshold(self) -> None:
        """For direction='gte', fails when ci_lower < threshold."""
        # Values straddle threshold; high variance => ci_lower dips below
        result = metric_with_sem([0.5, 0.9], threshold=0.70)
        assert result.passes_threshold is False

    def test_lte_passes_when_ci_upper_below_threshold(self) -> None:
        """For direction='lte', passes when ci_upper <= threshold."""
        result = metric_with_sem([0.05, 0.06, 0.04, 0.05], threshold=0.20, direction="lte")
        assert result.passes_threshold is True

    def test_lte_fails_when_ci_upper_above_threshold(self) -> None:
        """For direction='lte', fails when ci_upper > threshold."""
        result = metric_with_sem([0.15, 0.25], threshold=0.20, direction="lte")
        assert result.passes_threshold is False

    def test_empty_values_raises(self) -> None:
        """Empty values list should raise ValueError."""
        with pytest.raises(ValueError, match="at least one value"):
            metric_with_sem([], threshold=0.70)


# ===========================================================================
# wilson_ci
# ===========================================================================


class TestWilsonCI:
    """Tests for Wilson score confidence interval."""

    def test_basic_proportion(self) -> None:
        """Wilson CI for 5/10 should center around 0.5."""
        result = wilson_ci(5, 10, threshold=0.20)
        assert result.mean == pytest.approx(0.5)
        assert result.ci_lower < 0.5
        assert result.ci_upper > 0.5
        assert result.method == "wilson"
        assert result.passes_threshold is True  # ci_lower > 0.20

    def test_zero_total(self) -> None:
        """0/0 should return zeros."""
        result = wilson_ci(0, 0, threshold=0.50)
        assert result.mean == 0.0
        assert result.ci_lower == 0.0
        assert result.ci_upper == 0.0

    def test_all_successes(self) -> None:
        """n/n should have ci_upper = 1.0 and ci_lower < 1.0."""
        result = wilson_ci(10, 10, threshold=0.50)
        assert result.mean == pytest.approx(1.0)
        assert result.ci_upper == pytest.approx(1.0)
        assert result.ci_lower < 1.0  # Wilson doesn't collapse to point estimate

    def test_lte_direction(self) -> None:
        """LTE direction uses ci_upper for threshold check."""
        result = wilson_ci(1, 10, threshold=0.50, direction="lte")
        assert result.passes_threshold is True  # ci_upper for 1/10 < 0.50

    def test_lte_fails_when_ci_upper_above(self) -> None:
        """LTE direction fails when ci_upper > threshold."""
        result = wilson_ci(5, 10, threshold=0.20, direction="lte")
        assert result.passes_threshold is False  # ci_upper for 5/10 >> 0.20


# ===========================================================================
# bca_ci
# ===========================================================================


class TestBcaCI:
    """Tests for BCa bootstrap confidence interval."""

    def test_basic_computation(self) -> None:
        """BCa CI for well-behaved data."""
        values = [0.8, 0.85, 0.9, 0.82, 0.88, 0.87, 0.83, 0.86, 0.89, 0.84]
        result = bca_ci(values, threshold=0.70)
        assert result.mean == pytest.approx(statistics.mean(values))
        assert result.ci_lower < result.mean
        assert result.ci_upper > result.mean
        assert result.method == "bca"
        assert result.passes_threshold is True

    def test_single_value(self) -> None:
        """Single value gives point estimate."""
        result = bca_ci([0.9], threshold=0.70)
        assert result.mean == pytest.approx(0.9)
        assert result.ci_lower == pytest.approx(0.9)
        assert result.ci_upper == pytest.approx(0.9)

    def test_two_values_falls_back_to_normal(self) -> None:
        """With < 3 values, falls back to normal-approx."""
        result = bca_ci([0.8, 0.9], threshold=0.70)
        assert result.method == "normal"

    def test_empty_raises(self) -> None:
        """Empty values should raise ValueError."""
        with pytest.raises(ValueError):
            bca_ci([], threshold=0.70)

    def test_identical_values_falls_back(self) -> None:
        """All identical values (stdev=0) should fall back to normal."""
        result = bca_ci([0.5, 0.5, 0.5, 0.5], threshold=0.30)
        assert result.method == "normal"
        assert result.passes_threshold is True


# ===========================================================================
# compute_trial_metrics
# ===========================================================================


class TestComputeTrialMetrics:
    """Tests for single-trial metric computation."""

    def test_precision_excludes_novel_valid(self) -> None:
        """Precision = (match + partial) / (match + partial + no_match). Novel excluded."""
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.PARTIAL_MATCH, "F2", "EF2"),
            _grader(GraderVerdict.NOVEL_VALID, "F3"),
            _grader(GraderVerdict.NO_MATCH, "F4"),
        ]
        expected = [_expected("EF1"), _expected("EF2")]
        findings = [_finding(f"F{i}") for i in range(1, 5)]

        result = compute_trial_metrics(graded, expected, findings)

        # precision = 2 / (2 + 1) = 2/3
        assert result.precision == pytest.approx(2 / 3)

    def test_recall_unique_matched(self) -> None:
        """Recall = unique matched expected IDs / total expected."""
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.PARTIAL_MATCH, "F2", "EF1"),  # duplicate match
            _grader(GraderVerdict.MATCH, "F3", "EF2"),
        ]
        expected = [_expected("EF1"), _expected("EF2"), _expected("EF3")]
        findings = [_finding(f"F{i}") for i in range(1, 4)]

        result = compute_trial_metrics(graded, expected, findings)

        # unique matched: EF1, EF2 => 2 / 3
        assert result.recall == pytest.approx(2 / 3)

    def test_snr_formula(self) -> None:
        """SNR = (match + partial + novel) / no_match."""
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.PARTIAL_MATCH, "F2", "EF2"),
            _grader(GraderVerdict.NOVEL_VALID, "F3"),
            _grader(GraderVerdict.NO_MATCH, "F4"),
            _grader(GraderVerdict.NO_MATCH, "F5"),
        ]
        expected = [_expected("EF1"), _expected("EF2")]
        findings = [_finding(f"F{i}") for i in range(1, 6)]

        result = compute_trial_metrics(graded, expected, findings)

        # signal = 3, noise = 2 => SNR = 1.5
        assert result.snr == pytest.approx(1.5)

    def test_severity_accuracy(self) -> None:
        """Severity accuracy uses adjacency scoring: adjacent mismatch = 0.5."""
        expected_findings = [
            _expected("EF1", severity=Severity.BUG),
            _expected("EF2", severity=Severity.WARN),
        ]
        findings_list = [
            _finding("F1", severity=Severity.BUG),   # exact match → 1.0
            _finding("F2", severity=Severity.BUG),    # adjacent (WARN→BUG) → 0.5
        ]
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.MATCH, "F2", "EF2"),
        ]

        result = compute_trial_metrics(graded, expected_findings, findings_list)

        # (1.0 + 0.5) / 2 = 0.75
        assert result.severity_accuracy == pytest.approx(0.75)

    def test_category_accuracy(self) -> None:
        """Category accuracy = correct category / total matched."""
        expected_findings = [
            _expected("EF1", category=Category.SECURITY),
            _expected("EF2", category=Category.DESIGN),
        ]
        findings_list = [
            _finding("F1", category=Category.SECURITY),   # correct
            _finding("F2", category=Category.SECURITY),    # wrong — expected DESIGN
        ]
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.PARTIAL_MATCH, "F2", "EF2"),  # partial counts
        ]

        result = compute_trial_metrics(graded, expected_findings, findings_list)

        assert result.category_accuracy == pytest.approx(0.5)

    def test_grading_error_excluded_from_all_metrics(self) -> None:
        """grading_error findings are excluded from precision, recall, SNR, etc."""
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.GRADING_ERROR, "F2"),
            _grader(GraderVerdict.NO_MATCH, "F3"),
        ]
        expected = [_expected("EF1")]
        findings = [_finding(f"F{i}") for i in range(1, 4)]

        result = compute_trial_metrics(graded, expected, findings)

        # Without grading_error: match=1, no_match=1 => precision = 1/2
        assert result.precision == pytest.approx(0.5)
        # recall: 1 unique matched / 1 expected = 1.0
        assert result.recall == pytest.approx(1.0)
        # SNR: 1 / 1 = 1.0
        assert result.snr == pytest.approx(1.0)
        assert result.grading_error_count == 1

    def test_zero_findings_precision_is_one(self) -> None:
        """With no findings, precision = 1.0 (vacuous truth)."""
        result = compute_trial_metrics([], [], [])

        assert result.precision == pytest.approx(1.0)
        assert result.finding_count == 0

    def test_zero_expected_recall_is_nan(self) -> None:
        """With no expected findings, recall is undefined (NaN).

        Clean-code cases have no recall denominator — a 0.0 observation
        would poison the run-level recall average. NaN lets the aggregator
        filter the trial out via ``_filter_nan`` (per FR-004).
        """
        graded = [_grader(GraderVerdict.NO_MATCH, "F1")]
        findings = [_finding("F1")]

        result = compute_trial_metrics(graded, [], findings)

        assert math.isnan(result.recall)

    def test_zero_noise_snr_is_nan(self) -> None:
        """With 0 no_match, SNR should be NaN (all signal, no noise)."""
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
        ]
        expected = [_expected("EF1")]
        findings = [_finding("F1")]

        result = compute_trial_metrics(graded, expected, findings)

        assert math.isnan(result.snr)

    def test_novel_count_tracked(self) -> None:
        """novel_count should count novel_valid findings."""
        graded = [
            _grader(GraderVerdict.NOVEL_VALID, "F1"),
            _grader(GraderVerdict.NOVEL_VALID, "F2"),
            _grader(GraderVerdict.MATCH, "F3", "EF1"),
        ]
        expected = [_expected("EF1")]
        findings = [_finding(f"F{i}") for i in range(1, 4)]

        result = compute_trial_metrics(graded, expected, findings)

        assert result.novel_count == 2

    def test_finding_count_tracks_total(self) -> None:
        """finding_count = total findings (input list length)."""
        findings = [_finding(f"F{i}") for i in range(1, 6)]
        graded = [_grader(GraderVerdict.NO_MATCH, f"F{i}") for i in range(1, 6)]

        result = compute_trial_metrics(graded, [], findings)

        assert result.finding_count == 5

    def test_severity_adjacency_two_step_scores_zero(self) -> None:
        """BUG→NIT (2-step mismatch) scores 0.0, not partial credit."""
        expected_findings = [_expected("EF1", severity=Severity.NIT)]
        findings_list = [_finding("F1", severity=Severity.BUG)]
        graded = [_grader(GraderVerdict.MATCH, "F1", "EF1")]

        result = compute_trial_metrics(graded, expected_findings, findings_list)

        assert result.severity_accuracy == pytest.approx(0.0)

    def test_severity_adjacency_warn_nit(self) -> None:
        """WARN→NIT (1-step mismatch) gets 0.5 partial credit."""
        expected_findings = [_expected("EF1", severity=Severity.WARN)]
        findings_list = [_finding("F1", severity=Severity.NIT)]
        graded = [_grader(GraderVerdict.MATCH, "F1", "EF1")]

        result = compute_trial_metrics(graded, expected_findings, findings_list)

        assert result.severity_accuracy == pytest.approx(0.5)

    def test_severity_dedup_best_score_per_expected(self) -> None:
        """Multiple findings matching one expected → keep best severity score."""
        expected_findings = [_expected("EF1", severity=Severity.WARN)]
        findings_list = [
            _finding("F1", severity=Severity.BUG),   # adjacent → 0.5
            _finding("F2", severity=Severity.WARN),   # exact → 1.0
        ]
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.MATCH, "F2", "EF1"),
        ]

        result = compute_trial_metrics(graded, expected_findings, findings_list)

        # Best score for EF1 is 1.0 (from F2), only 1 unique expected
        assert result.severity_accuracy == pytest.approx(1.0)

    def test_severity_dedup_counts_unique_expected_ids(self) -> None:
        """3 actual findings matching 1 expected → denominator is 1, not 3."""
        expected_findings = [_expected("EF1", severity=Severity.BUG)]
        findings_list = [
            _finding("F1", severity=Severity.WARN),   # adjacent → 0.5
            _finding("F2", severity=Severity.WARN),   # adjacent → 0.5
            _finding("F3", severity=Severity.WARN),   # adjacent → 0.5
        ]
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.MATCH, "F2", "EF1"),
            _grader(GraderVerdict.MATCH, "F3", "EF1"),
        ]

        result = compute_trial_metrics(graded, expected_findings, findings_list)

        # Best for EF1 is 0.5 (all adjacent). 1 unique expected → 0.5/1 = 0.5
        assert result.severity_accuracy == pytest.approx(0.5)

    def test_severity_accuracy_with_no_matches(self) -> None:
        """When no matched findings, severity_accuracy = NaN (undefined)."""
        graded = [_grader(GraderVerdict.NO_MATCH, "F1")]
        findings = [_finding("F1")]
        expected = [_expected("EF1")]

        result = compute_trial_metrics(graded, expected, findings)

        assert math.isnan(result.severity_accuracy)

    def test_category_accuracy_with_no_matches(self) -> None:
        """When no matched findings, category_accuracy = NaN (undefined)."""
        graded = [_grader(GraderVerdict.NO_MATCH, "F1")]
        findings = [_finding("F1")]
        expected = [_expected("EF1")]

        result = compute_trial_metrics(graded, expected, findings)

        assert math.isnan(result.category_accuracy)

    def test_severity_pairs_collected(self) -> None:
        """compute_trial_metrics should populate severity_pairs."""
        expected_findings = [
            _expected("EF1", severity=Severity.BUG),
            _expected("EF2", severity=Severity.WARN),
        ]
        findings_list = [
            _finding("F1", severity=Severity.BUG),
            _finding("F2", severity=Severity.NIT),
        ]
        graded = [
            _grader(GraderVerdict.MATCH, "F1", "EF1"),
            _grader(GraderVerdict.MATCH, "F2", "EF2"),
        ]
        result = compute_trial_metrics(graded, expected_findings, findings_list)
        assert len(result.severity_pairs) == 2
        assert ["BUG", "BUG"] in result.severity_pairs
        assert ["WARN", "NIT"] in result.severity_pairs


# ===========================================================================
# aggregate_metrics
# ===========================================================================


class TestAggregateMetrics:
    """Tests for aggregate_metrics across cases/trials."""

    @staticmethod
    def _make_case_result(
        case_id: str,
        trial_metrics_list: list[TrialMetrics],
        pass_at_1: dict[str, bool] | None = None,
        pass_at_k: dict[str, bool] | None = None,
        rebuttal_results: list[RebuttalResult] | None = None,
    ) -> CaseResult:
        """Build a CaseResult with given trial metrics."""
        trials = []
        for i, tm in enumerate(trial_metrics_list, start=1):
            trials.append(
                TrialResult(
                    trial_number=i,
                    findings=[],
                    graded=[],
                    metrics=tm,
                )
            )
        return CaseResult(
            case_id=case_id,
            trials=trials,
            pass_at_1=pass_at_1 or {"precision": True, "recall": True},
            pass_at_k=pass_at_k or {"precision": True, "recall": True},
            rebuttal_results=rebuttal_results,
        )

    def test_basic_aggregation(self) -> None:
        """Metrics are aggregated across all trials of all cases."""
        tm1 = TrialMetrics(
            precision=0.8, recall=0.7, severity_accuracy=0.9,
            category_accuracy=0.8, snr=4.0, novel_count=1,
            grading_error_count=0, finding_count=5,
        )
        tm2 = TrialMetrics(
            precision=0.9, recall=0.8, severity_accuracy=0.85,
            category_accuracy=0.75, snr=5.0, novel_count=2,
            grading_error_count=1, finding_count=6,
        )
        cases = [self._make_case_result("c1", [tm1, tm2])]
        thresholds = {
            "precision": 0.70,
            "recall": 0.60,
            "severity_accuracy": 0.80,
            "category_accuracy": 0.70,
            "fp_rate": 0.20,
            "snr": 3.0,
        }

        result = aggregate_metrics(cases, thresholds)

        assert result.precision.mean == pytest.approx((0.8 + 0.9) / 2)
        assert result.recall.mean == pytest.approx((0.7 + 0.8) / 2)

    def test_fp_rate_uses_lte(self) -> None:
        """fp_rate uses <= threshold comparison (direction='lte').

        fp_rate: BUG-only findings on clean-code cases.
        Clean case = pass_at_1 is empty dict (no expected findings).
        """
        # Clean-code case: 2 trials, one with BUG finding, one without
        clean_tm1 = TrialMetrics(
            precision=1.0, recall=0.0, severity_accuracy=1.0,
            category_accuracy=1.0, snr=0.0, novel_count=0,
            grading_error_count=0, finding_count=1,
        )
        clean_tm2 = TrialMetrics(
            precision=1.0, recall=0.0, severity_accuracy=1.0,
            category_accuracy=1.0, snr=0.0, novel_count=0,
            grading_error_count=0, finding_count=0,
        )
        # Trial 1 has a BUG finding (FP), trial 2 has none
        clean_trial_1 = TrialResult(
            trial_number=1,
            findings=[_finding("F1", severity=Severity.BUG)],
            graded=[],
            metrics=clean_tm1,
        )
        clean_trial_2 = TrialResult(
            trial_number=2,
            findings=[],
            graded=[],
            metrics=clean_tm2,
        )
        clean_case = CaseResult(
            case_id="clean",
            trials=[clean_trial_1, clean_trial_2],
            pass_at_1={},  # empty = clean-code case
            pass_at_k={},
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        result = aggregate_metrics([clean_case], thresholds)

        # Per FR-004 fp_rate collapses to one observation per clean case
        # (OR across trials): one case × any trial with a BUG = 1.0.
        assert result.fp_rate.mean == pytest.approx(1.0)
        # direction='lte', ci_upper for 1/1 > 0.20 → fails
        assert result.fp_rate.passes_threshold is False

    def test_pass_at_1_rate(self) -> None:
        """pass_at_1_rate = % of expected findings caught on first trial."""
        cases = [
            self._make_case_result(
                "c1", [TrialMetrics(
                    precision=0.8, recall=0.7, severity_accuracy=0.9,
                    category_accuracy=0.8, snr=4.0, novel_count=0,
                    grading_error_count=0, finding_count=5,
                )],
                pass_at_1={"EF1": True, "EF2": True},
            ),
            self._make_case_result(
                "c2", [TrialMetrics(
                    precision=0.5, recall=0.4, severity_accuracy=0.7,
                    category_accuracy=0.6, snr=2.0, novel_count=0,
                    grading_error_count=0, finding_count=5,
                )],
                pass_at_1={"EF3": False, "EF4": False},
            ),
        ]
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        result = aggregate_metrics(cases, thresholds)

        # 2 caught out of 4 total expected findings = 0.5
        assert result.pass_at_1_rate == pytest.approx(0.5)

    def test_pass_at_k_rate(self) -> None:
        """pass_at_k_rate = % of expected findings caught in any trial."""
        cases = [
            self._make_case_result(
                "c1", [TrialMetrics(
                    precision=0.8, recall=0.7, severity_accuracy=0.9,
                    category_accuracy=0.8, snr=4.0, novel_count=0,
                    grading_error_count=0, finding_count=5,
                )],
                pass_at_k={"EF1": True, "EF2": True},
            ),
            self._make_case_result(
                "c2", [TrialMetrics(
                    precision=0.5, recall=0.4, severity_accuracy=0.7,
                    category_accuracy=0.6, snr=2.0, novel_count=0,
                    grading_error_count=0, finding_count=5,
                )],
                pass_at_k={"EF3": True, "EF4": False},
            ),
        ]
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        result = aggregate_metrics(cases, thresholds)

        # 3 caught out of 4 total expected findings = 0.75
        assert result.pass_at_k_rate == pytest.approx(0.75)

    def test_novel_count_is_sum_across_run(self) -> None:
        """F16 regression: aggregate novel finding count must be the SUM
        of ``novel_count`` across every trial in the run, not the mean.

        FR-004 defines "Novel finding count" as the number of
        ``novel_valid`` findings across the run. Two trials with 2 and 4
        novel findings must aggregate to 6, not 3.
        """
        tm1 = TrialMetrics(
            precision=0.8, recall=0.7, severity_accuracy=0.9,
            category_accuracy=0.8, snr=4.0, novel_count=2,
            grading_error_count=0, finding_count=5,
        )
        tm2 = TrialMetrics(
            precision=0.9, recall=0.8, severity_accuracy=0.85,
            category_accuracy=0.75, snr=5.0, novel_count=4,
            grading_error_count=0, finding_count=6,
        )
        cases = [self._make_case_result("c1", [tm1, tm2])]
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        result = aggregate_metrics(cases, thresholds)

        assert result.novel_count == 6

    def test_aggregate_metrics_json_round_trip_with_single_class_pairs(self) -> None:
        """F15 round-trip contract: aggregate emitted with only same-class
        severity pairs must deserialize cleanly as a ``--baseline`` input.
        Prior to the scorer guard, ``severity_qwk`` became NaN, serialized
        to JSON ``null``, and ``model_validate_json`` rejected the float
        field — producing run-*.json files that could not be reloaded.
        """
        from eval.models import AggregateMetrics

        tm = TrialMetrics(
            precision=1.0, recall=1.0, severity_accuracy=1.0,
            category_accuracy=1.0, snr=0.0, novel_count=0,
            grading_error_count=0, finding_count=2,
            severity_pairs=[["BUG", "BUG"], ["BUG", "BUG"]],
        )
        cases = [self._make_case_result("c1", [tm])]
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }
        agg = aggregate_metrics(cases, thresholds)

        # This is the failure mode in the finding: dump → reload.
        blob = agg.model_dump_json()
        restored = AggregateMetrics.model_validate_json(blob)
        assert restored.severity_qwk == agg.severity_qwk

    def test_severity_qwk_single_class_is_not_nan(self) -> None:
        """F15 regression: when every matched pair falls in the same
        severity class (e.g., two perfect BUG->BUG matches),
        ``cohen_kappa_score`` returns NaN. Pydantic serializes NaN to
        JSON ``null``, which ``AggregateMetrics.model_validate_json``
        then rejects as the next run's ``--baseline``. Scorer must
        detect the single-class case and emit 0.0 instead so the
        machine-readable artifact stays round-trippable.
        """
        import math

        tm = TrialMetrics(
            precision=1.0, recall=1.0, severity_accuracy=1.0,
            category_accuracy=1.0, snr=0.0, novel_count=0,
            grading_error_count=0, finding_count=2,
            severity_pairs=[["BUG", "BUG"], ["BUG", "BUG"]],
        )
        cases = [self._make_case_result("c1", [tm])]
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }
        result = aggregate_metrics(cases, thresholds)
        assert not math.isnan(result.severity_qwk), (
            "severity_qwk must not be NaN for single-class pairs — "
            "baseline JSON round-trip breaks otherwise"
        )

    def test_severity_qwk_computed(self) -> None:
        """aggregate_metrics should compute severity_qwk."""
        tm = TrialMetrics(
            precision=0.8, recall=0.7, severity_accuracy=0.9,
            category_accuracy=0.8, snr=4.0, novel_count=1,
            grading_error_count=0, finding_count=5,
            severity_pairs=[["BUG", "BUG"], ["WARN", "WARN"], ["NIT", "NIT"]],
        )
        cases = [self._make_case_result("c1", [tm])]
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }
        result = aggregate_metrics(cases, thresholds)
        # Perfect agreement -> kappa = 1.0
        assert result.severity_qwk == pytest.approx(1.0)

    def test_all_nan_severity_accuracy_is_inconclusive_not_pass(self) -> None:
        """When no trial has matches, severity/category accuracy is undefined.

        The previous implementation fell back to MetricWithSEM(mean=1.0, ...)
        which force-PASSed the threshold and painted the whole run green even
        though the reviewer never produced a finding to grade. The correct
        outcome is an INCONCLUSIVE metric tagged with CIMethod.UNDEFINED so
        operators see the missing data and strict-mode CI fails the run.
        """
        from eval.models import MetricStatus

        tm_no_matches = TrialMetrics(
            precision=1.0, recall=0.0,
            severity_accuracy=float("nan"),
            category_accuracy=float("nan"),
            snr=0.0, novel_count=0,
            grading_error_count=0, finding_count=0,
        )
        cases = [self._make_case_result("c1", [tm_no_matches, tm_no_matches])]
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        result = aggregate_metrics(cases, thresholds)

        assert result.severity_accuracy.method == CIMethod.UNDEFINED
        assert result.severity_accuracy.passes_threshold is False
        assert result.severity_accuracy.status == MetricStatus.INCONCLUSIVE
        assert result.category_accuracy.method == CIMethod.UNDEFINED
        assert result.category_accuracy.passes_threshold is False
        assert result.category_accuracy.status == MetricStatus.INCONCLUSIVE

    def test_undefined_metric_check_thresholds_respects_strict_mode(self) -> None:
        """UNDEFINED metrics pass in non-strict mode and fail in strict mode.

        Build an AggregateMetrics where only severity_accuracy is UNDEFINED
        and every other metric cleanly passes. Non-strict must tolerate the
        undefined metric (pass-through, matching WILSON_INSUFFICIENT_N).
        Strict must reject it so CI cannot claim success without data.
        """
        def _passing(mean: float) -> MetricWithSEM:
            return MetricWithSEM(
                mean=mean, sem=0.0, ci_lower=mean, ci_upper=mean,
                passes_threshold=True, method=CIMethod.BCA,
            )
        passing_lte = MetricWithSEM(
            mean=0.0, sem=0.0, ci_lower=0.0, ci_upper=0.0,
            passes_threshold=True, method=CIMethod.WILSON,
        )
        undefined = MetricWithSEM(
            mean=0.0, sem=0.0, ci_lower=0.0, ci_upper=0.0,
            passes_threshold=False, method=CIMethod.UNDEFINED,
        )
        agg = AggregateMetrics(
            precision=_passing(1.0),
            recall=_passing(1.0),
            severity_accuracy=undefined,
            category_accuracy=_passing(1.0),
            fp_rate=passing_lte,
            snr=_passing(5.0),
            novel_count=0,
            pass_at_1_rate=1.0,
            pass_at_k_rate=1.0,
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        assert check_thresholds(agg, thresholds, strict=False) is True
        assert check_thresholds(agg, thresholds, strict=True) is False


# ===========================================================================
# compute_rebuttal_accuracy
# ===========================================================================


class TestComputeRebuttalAccuracy:
    """Tests for rebuttal accuracy computation."""

    @staticmethod
    def _make_case_result_with_rebuttals(
        rebuttals: list[RebuttalResult] | None,
    ) -> CaseResult:
        return CaseResult(
            case_id="c1",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[],
                    graded=[],
                    metrics=TrialMetrics(
                        precision=1.0, recall=1.0, severity_accuracy=1.0,
                        category_accuracy=1.0, snr=float("inf"), novel_count=0,
                        grading_error_count=0, finding_count=0,
                    ),
                )
            ],
            pass_at_1={},
            pass_at_k={},
            rebuttal_results=rebuttals,
        )

    def test_basic_rebuttal_accuracy(self) -> None:
        """Rebuttal accuracy = correct / total across all cases."""
        rebuttals = [
            RebuttalResult(
                turn_number=1, target_expected_id="EF1", actual_finding_id="F1",
                expected_status=FindingStatus.DISMISSED,
                actual_status=FindingStatus.DISMISSED,
                correct=True, finding_not_found=False,
            ),
            RebuttalResult(
                turn_number=2, target_expected_id="EF2", actual_finding_id="F2",
                expected_status=FindingStatus.DISMISSED,
                actual_status=FindingStatus.OPEN,
                correct=False, finding_not_found=False,
            ),
        ]
        cases = [self._make_case_result_with_rebuttals(rebuttals)]

        result = compute_rebuttal_accuracy(cases)

        assert result is not None
        assert result.mean == pytest.approx(0.5)

    def test_none_when_no_multi_turn_cases(self) -> None:
        """Returns None when no cases have rebuttal_results."""
        cases = [self._make_case_result_with_rebuttals(None)]

        result = compute_rebuttal_accuracy(cases)

        assert result is None

    def test_none_when_rebuttals_empty_list(self) -> None:
        """Returns None when rebuttal_results is an empty list."""
        cases = [self._make_case_result_with_rebuttals([])]

        result = compute_rebuttal_accuracy(cases)

        assert result is None

    def test_finding_not_found_counts_as_incorrect(self) -> None:
        """finding_not_found rebuttals count as incorrect."""
        rebuttals = [
            RebuttalResult(
                turn_number=1, target_expected_id="EF1", actual_finding_id=None,
                expected_status=FindingStatus.DISMISSED,
                actual_status=None,
                correct=False, finding_not_found=True,
            ),
            RebuttalResult(
                turn_number=2, target_expected_id="EF2", actual_finding_id="F2",
                expected_status=FindingStatus.DISMISSED,
                actual_status=FindingStatus.DISMISSED,
                correct=True, finding_not_found=False,
            ),
        ]
        cases = [self._make_case_result_with_rebuttals(rebuttals)]

        result = compute_rebuttal_accuracy(cases)

        assert result is not None
        assert result.mean == pytest.approx(0.5)

    def test_rebuttal_single_observation_insufficient_for_threshold(self) -> None:
        """Single observation yields natural Wilson fail + wilson_insufficient_n method.

        Even a perfect 1/1 has ci_lower below 0.75. Per B' coordinator
        ratification, passes_threshold reflects the natural Wilson result
        (False); the method tag surfaces the inconclusive state so the
        scorecard can render INCONCLUSIVE and check_thresholds can treat
        it as non-fatal (unless --strict).
        """
        rebuttals = [
            RebuttalResult(
                turn_number=1, target_expected_id="EF1", actual_finding_id="F1",
                expected_status=FindingStatus.DISMISSED,
                actual_status=FindingStatus.DISMISSED,
                correct=True, finding_not_found=False,
            ),
        ]
        cases = [self._make_case_result_with_rebuttals(rebuttals)]

        result = compute_rebuttal_accuracy(cases)

        assert result is not None
        assert result.mean == pytest.approx(1.0)
        assert result.method == "wilson_insufficient_n"
        assert result.passes_threshold is False
        assert result.ci_lower < 0.75

    def test_rebuttal_accuracy_threshold_passes_with_enough_data(self) -> None:
        """With enough correct rebuttals, Wilson CI lower bound exceeds 0.75."""
        # Wilson CI for 15/15: ci_lower ~0.768 > 0.75
        rebuttals = [
            RebuttalResult(
                turn_number=i,
                target_expected_id=f"EF{i}",
                actual_finding_id=f"F{i}",
                expected_status=FindingStatus.DISMISSED,
                actual_status=FindingStatus.DISMISSED,
                correct=True,
                finding_not_found=False,
            )
            for i in range(1, 16)
        ]
        cases = [self._make_case_result_with_rebuttals(rebuttals)]

        result = compute_rebuttal_accuracy(cases)

        assert result is not None
        assert result.mean == pytest.approx(1.0)
        assert result.method == "wilson"
        assert result.passes_threshold is True

    def test_rebuttal_across_multiple_cases(self) -> None:
        """Rebuttal accuracy aggregates across multiple cases."""
        reb1 = [
            RebuttalResult(
                turn_number=1, target_expected_id="EF1", actual_finding_id="F1",
                expected_status=FindingStatus.DISMISSED,
                actual_status=FindingStatus.DISMISSED,
                correct=True, finding_not_found=False,
            ),
        ]
        reb2 = [
            RebuttalResult(
                turn_number=1, target_expected_id="EF2", actual_finding_id="F2",
                expected_status=FindingStatus.DISMISSED,
                actual_status=FindingStatus.OPEN,
                correct=False, finding_not_found=False,
            ),
        ]
        cases = [
            self._make_case_result_with_rebuttals(reb1),
            CaseResult(
                case_id="c2",
                trials=[
                    TrialResult(
                        trial_number=1,
                        findings=[], graded=[],
                        metrics=TrialMetrics(
                            precision=1.0, recall=1.0, severity_accuracy=1.0,
                            category_accuracy=1.0, snr=float("inf"), novel_count=0,
                            grading_error_count=0, finding_count=0,
                        ),
                    )
                ],
                pass_at_1={}, pass_at_k={},
                rebuttal_results=reb2,
            ),
        ]

        result = compute_rebuttal_accuracy(cases)

        assert result is not None
        # 1 correct out of 2 total
        assert result.mean == pytest.approx(0.5)


# ===========================================================================
# check_thresholds
# ===========================================================================


class TestCheckThresholds:
    """Tests for threshold checking."""

    def test_all_pass(self) -> None:
        """Returns True when all metrics pass their thresholds."""
        aggregate = _build_aggregate(
            precision=0.90, recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.05, snr=5.0,
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        assert check_thresholds(aggregate, thresholds) is True

    def test_honors_thresholds_argument_independently(self) -> None:
        """check_thresholds must compare CI bounds to its thresholds arg.

        The previous implementation trusted m.passes_threshold, which was
        precomputed by aggregate_metrics against whatever thresholds it
        received. If a CLI run passed custom thresholds to the scorecard
        layer but aggregate_metrics was built with DEFAULT_THRESHOLDS,
        check_thresholds would happily return True against the stricter
        bar. Re-verify from CI bounds so the argument is load-bearing.
        """
        aggregate = _build_aggregate(
            precision=0.80, recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.05, snr=5.0,
        )
        # Aggregate's internal passes_threshold flags were built against
        # 0.70/0.60/etc., so they all say PASS. A stricter threshold
        # (precision >= 0.95) must now flip the overall result to FAIL
        # based on the actual CI bound, not the stale flag.
        strict = {
            "precision": 0.95, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        assert check_thresholds(aggregate, strict) is False

    def test_one_fails(self) -> None:
        """Returns False when any metric fails its threshold."""
        aggregate = _build_aggregate(
            precision=0.50, recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.05, snr=5.0,
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        assert check_thresholds(aggregate, thresholds) is False

    def test_fp_rate_fails_above_threshold(self) -> None:
        """fp_rate fails when mean is above threshold."""
        aggregate = _build_aggregate(
            precision=0.90, recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.30, snr=5.0,
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        assert check_thresholds(aggregate, thresholds) is False

    def test_rebuttal_accuracy_checked_when_present(self) -> None:
        """Rebuttal accuracy is included in threshold check when present."""
        aggregate = _build_aggregate(
            precision=0.90, recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.05, snr=5.0,
            rebuttal_accuracy=0.50,  # below 0.75 threshold
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
            "rebuttal_accuracy": 0.75,
        }

        assert check_thresholds(aggregate, thresholds) is False

    def test_rebuttal_accuracy_skipped_when_none(self) -> None:
        """When rebuttal_accuracy is None, it is not checked."""
        aggregate = _build_aggregate(
            precision=0.90, recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.05, snr=5.0,
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
            "rebuttal_accuracy": 0.75,
        }

        # rebuttal_accuracy is None, should not cause failure
        assert check_thresholds(aggregate, thresholds) is True

    def test_wilson_insufficient_n_non_strict_passes(self) -> None:
        """Metric with method=wilson_insufficient_n is inconclusive, not fail.

        Default (non-strict) semantics: inconclusive metrics do not block
        release. passes_threshold may be False (natural Wilson result),
        but check_thresholds treats the method tag as "do not gate".
        """
        aggregate = _build_aggregate(
            precision=0.90, recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.05, snr=5.0,
        )
        # Inject an inconclusive rebuttal metric
        aggregate.rebuttal_accuracy = MetricWithSEM(
            mean=1.0, sem=0.0,
            ci_lower=0.342, ci_upper=1.0,
            passes_threshold=False,
            method="wilson_insufficient_n",
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
            "rebuttal_accuracy": 0.75,
        }

        assert check_thresholds(aggregate, thresholds) is True
        assert check_thresholds(aggregate, thresholds, strict=False) is True

    def test_wilson_insufficient_n_strict_fails(self) -> None:
        """With strict=True, inconclusive metrics are treated as failure.

        --strict mode is for mature corpora where insufficient-n must not
        silently pass. Everything else equal, same inconclusive metric
        that passes in default mode fails in strict mode.
        """
        aggregate = _build_aggregate(
            precision=0.90, recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.05, snr=5.0,
        )
        aggregate.rebuttal_accuracy = MetricWithSEM(
            mean=1.0, sem=0.0,
            ci_lower=0.342, ci_upper=1.0,
            passes_threshold=False,
            method="wilson_insufficient_n",
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
            "rebuttal_accuracy": 0.75,
        }

        assert check_thresholds(aggregate, thresholds, strict=True) is False

    def test_real_fail_fails_in_both_modes(self) -> None:
        """A non-inconclusive failure must fail in both strict and non-strict.

        Ensures the inconclusive exemption is narrow — only applies to
        method=wilson_insufficient_n, not to any metric that happens to
        have passes_threshold=False.
        """
        aggregate = _build_aggregate(
            precision=0.50,  # below 0.70 threshold
            recall=0.80, severity_accuracy=0.90,
            category_accuracy=0.80, fp_rate=0.05, snr=5.0,
        )
        thresholds = {
            "precision": 0.70, "recall": 0.60,
            "severity_accuracy": 0.80, "category_accuracy": 0.70,
            "fp_rate": 0.20, "snr": 3.0,
        }

        assert check_thresholds(aggregate, thresholds) is False
        assert check_thresholds(aggregate, thresholds, strict=True) is False


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------


def _build_aggregate(
    precision: float = 0.9,
    recall: float = 0.8,
    severity_accuracy: float = 0.9,
    category_accuracy: float = 0.8,
    fp_rate: float = 0.05,
    snr: float = 5.0,
    rebuttal_accuracy: float | None = None,
) -> AggregateMetrics:
    """Build an AggregateMetrics with single-value MetricWithSEM entries."""
    from eval.scorer import metric_with_sem

    reb = None
    if rebuttal_accuracy is not None:
        reb = metric_with_sem([rebuttal_accuracy], threshold=0.75)

    return AggregateMetrics(
        precision=metric_with_sem([precision], threshold=0.70),
        recall=metric_with_sem([recall], threshold=0.60),
        severity_accuracy=metric_with_sem([severity_accuracy], threshold=0.80),
        category_accuracy=metric_with_sem([category_accuracy], threshold=0.70),
        fp_rate=metric_with_sem([fp_rate], threshold=0.20, direction="lte"),
        rebuttal_accuracy=reb,
        snr=metric_with_sem([snr], threshold=3.0),
        novel_count_avg=0.0,
        pass_at_1_rate=1.0,
        pass_at_k_rate=1.0,
    )


# ===========================================================================
# FP rate — clean-code cases only
# ===========================================================================


_DUMMY_METRICS = TrialMetrics(
    precision=1.0, recall=0.0, severity_accuracy=1.0,
    category_accuracy=1.0, snr=0.0, novel_count=0,
    grading_error_count=0, finding_count=0,
)

_DEFAULT_THRESHOLDS: dict[str, float] = {
    "precision": 0.70, "recall": 0.60,
    "severity_accuracy": 0.80, "category_accuracy": 0.70,
    "fp_rate": 0.20, "snr": 3.0,
}


class TestFPRateCleanCases:
    """Tests that fp_rate is computed exclusively from clean-code cases.

    FP rate counts only BUG findings on clean cases. WARN findings on
    clean code are expected reviewer behavior and do NOT count as FP.
    """

    def test_fp_rate_computed_from_clean_cases_only(self) -> None:
        """Only cases with empty pass_at_1 contribute to fp_rate."""
        clean_case = CaseResult(
            case_id="clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.BUG)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={},
            pass_at_k={},
        )
        non_clean_case = CaseResult(
            case_id="non-clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F2", severity=Severity.BUG)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={"EF1": True},
            pass_at_k={"EF1": True},
        )

        result = aggregate_metrics([clean_case, non_clean_case], _DEFAULT_THRESHOLDS)

        # Only clean_case trial counted: BUG finding => fp=1.0
        assert result.fp_rate.mean == pytest.approx(1.0)

    def test_clean_trial_with_bug_finding_gives_fp_one(self) -> None:
        """A clean case trial containing a BUG finding produces fp=1.0."""
        case = CaseResult(
            case_id="clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.BUG)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={},
            pass_at_k={},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        assert result.fp_rate.mean == pytest.approx(1.0)

    def test_clean_trial_with_warn_only_gives_fp_zero(self) -> None:
        """WARN-only findings on clean code do NOT count as false positives."""
        case = CaseResult(
            case_id="clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.WARN)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={},
            pass_at_k={},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        # WARN on clean code is expected behavior, not FP
        assert result.fp_rate.mean == pytest.approx(0.0)

    def test_clean_trial_without_bug_finding_gives_fp_zero(self) -> None:
        """A clean case trial with no BUG findings produces fp=0.0."""
        case = CaseResult(
            case_id="clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.NIT)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={},
            pass_at_k={},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        assert result.fp_rate.mean == pytest.approx(0.0)

    def test_non_clean_cases_do_not_contribute_to_fp_rate(self) -> None:
        """Cases with expected findings are excluded from fp_rate entirely."""
        non_clean_case = CaseResult(
            case_id="has-expected",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.BUG)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={"EF1": True},
            pass_at_k={"EF1": True},
        )

        result = aggregate_metrics([non_clean_case], _DEFAULT_THRESHOLDS)

        # No clean cases => fp_rate defaults to 0.0
        assert result.fp_rate.mean == pytest.approx(0.0)

    def test_dual_metric_fixed_results_contribute_to_fp_rate(self) -> None:
        """Fixed-version trials from DualMetricResult count as clean trials."""
        dual = DualMetricResult(
            vulnerable_results=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.BUG)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            fixed_results=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F2", severity=Severity.BUG)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
        )
        case = CaseResult(
            case_id="dual",
            trials=[
                TrialResult(
                    trial_number=1, findings=[], graded=[], metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={"EF1": True},
            pass_at_k={"EF1": True},
            dual_metric_results=dual,
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        # Non-clean case's own trials excluded, but fixed_results BUG => fp=1.0
        assert result.fp_rate.mean == pytest.approx(1.0)

    def test_fp_rate_collapses_trials_to_one_observation_per_case(self) -> None:
        """One clean case with a BUG on any trial = one FP observation at 1.0.

        Regression guard for F8: the spec defines fp_rate as
        ``BUG findings on clean code cases / total clean code cases``.
        Previously each trial of a clean case produced an independent Wilson
        observation, which dropped fp_rate as --trials increased (e.g. one
        clean case × 3 trials with one hallucination reported 0.33 instead
        of 1.0). fp_rate now ORs across trials of the same clean case.
        """
        case = CaseResult(
            case_id="clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.BUG)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
                TrialResult(
                    trial_number=2,
                    findings=[_finding("F2", severity=Severity.NIT)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
                TrialResult(
                    trial_number=3,
                    findings=[_finding("F3", severity=Severity.NIT)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={},
            pass_at_k={},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        # Spec: one clean case hallucinated a BUG on any trial => fp_rate=1.0
        assert result.fp_rate.mean == pytest.approx(1.0)

    def test_no_clean_cases_fp_rate_defaults_to_zero(self) -> None:
        """When no clean cases exist at all, fp_rate defaults to 0.0."""
        case = CaseResult(
            case_id="only-expected",
            trials=[
                TrialResult(
                    trial_number=1, findings=[], graded=[], metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={"EF1": False},
            pass_at_k={"EF1": False},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        assert result.fp_rate.mean == pytest.approx(0.0)

    def test_vacuous_snr_when_all_trials_zero_noise(self) -> None:
        """If every trial has SNR=NaN (zero noise), aggregate SNR is vacuous.

        The scorer drops NaN values from the BCa input; if none remain the
        aggregate is tagged method=vacuous with passes_threshold=True. This
        test locks that short-circuit in — without it a regression could
        return NaN means or fail the run on clean corpora.
        """
        perfect_trial = TrialResult(
            trial_number=1,
            findings=[_finding("F1", severity=Severity.BUG)],
            graded=[_grader(GraderVerdict.MATCH, "F1", "EF1")],
            metrics=TrialMetrics(
                precision=1.0,
                recall=1.0,
                severity_accuracy=1.0,
                category_accuracy=1.0,
                snr=float("nan"),
                novel_count=0,
                grading_error_count=0,
                finding_count=1,
            ),
        )
        case = CaseResult(
            case_id="perfect",
            trials=[perfect_trial],
            pass_at_1={"EF1": True},
            pass_at_k={"EF1": True},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        assert result.snr.method == CIMethod.VACUOUS
        assert result.snr.passes_threshold is True
        assert result.snr.mean == pytest.approx(0.0)

    def test_clean_cases_do_not_depress_aggregate_recall(self) -> None:
        """Clean cases contribute no recall observation (NaN, filtered out).

        Regression guard for F7: previously clean trials reported
        ``recall=0.0`` and aggregate_metrics averaged that into the run-level
        recall, so a perfect bug case plus one clean case reported
        ``aggregate.recall.mean == 0.5`` despite every expected finding being
        caught. FR-004 defines recall over expected findings only — clean
        cases should not enter the denominator.
        """
        bug_trial = TrialResult(
            trial_number=1,
            findings=[_finding("F1", severity=Severity.BUG)],
            graded=[_grader(GraderVerdict.MATCH, "F1", "EF1")],
            metrics=TrialMetrics(
                precision=1.0,
                recall=1.0,
                severity_accuracy=1.0,
                category_accuracy=1.0,
                snr=float("nan"),
                novel_count=0,
                grading_error_count=0,
                finding_count=1,
            ),
        )
        bug_case = CaseResult(
            case_id="bug",
            trials=[bug_trial],
            pass_at_1={"EF1": True},
            pass_at_k={"EF1": True},
        )

        clean_trial = TrialResult(
            trial_number=1,
            findings=[],
            graded=[],
            metrics=TrialMetrics(
                precision=1.0,
                recall=float("nan"),
                severity_accuracy=float("nan"),
                category_accuracy=float("nan"),
                snr=float("nan"),
                novel_count=0,
                grading_error_count=0,
                finding_count=0,
            ),
        )
        clean_case = CaseResult(
            case_id="clean",
            trials=[clean_trial],
            pass_at_1={},
            pass_at_k={},
        )

        result = aggregate_metrics(
            [bug_case, clean_case], _DEFAULT_THRESHOLDS
        )

        assert result.recall.mean == pytest.approx(1.0)

    def test_dual_metric_fixed_trials_depress_precision(self) -> None:
        """Dual-metric fixed trials contribute to precision independently.

        Regression guard for F9: previously fixed_results only fed fp_rate
        and warn_rate, so a perfect vulnerable trial plus a false-positive
        fixed trial reported ``aggregate.precision.mean == 1.0`` even though
        the reviewer flagged a non-existent bug on the fixed bundle. The
        dual-metric edge case in the spec explicitly says both halves
        contribute independently (FR-015 / spec.md:90).
        """
        vulnerable_trial = TrialResult(
            trial_number=1,
            findings=[_finding("F1", severity=Severity.BUG)],
            graded=[_grader(GraderVerdict.MATCH, "F1", "EF1")],
            metrics=TrialMetrics(
                precision=1.0,
                recall=1.0,
                severity_accuracy=1.0,
                category_accuracy=1.0,
                snr=float("nan"),
                novel_count=0,
                grading_error_count=0,
                finding_count=1,
            ),
        )
        fixed_fp_trial = TrialResult(
            trial_number=1,
            findings=[_finding("F2", severity=Severity.BUG)],
            graded=[_grader(GraderVerdict.NO_MATCH, "F2")],
            metrics=TrialMetrics(
                precision=0.0,
                recall=float("nan"),
                severity_accuracy=float("nan"),
                category_accuracy=float("nan"),
                snr=0.0,
                novel_count=0,
                grading_error_count=0,
                finding_count=1,
            ),
        )
        dual = DualMetricResult(
            vulnerable_results=[vulnerable_trial],
            fixed_results=[fixed_fp_trial],
        )
        case = CaseResult(
            case_id="dual",
            trials=[vulnerable_trial],
            pass_at_1={"EF1": True},
            pass_at_k={"EF1": True},
            dual_metric_results=dual,
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        # Vulnerable precision=1.0, fixed precision=0.0 → mean=0.5
        assert result.precision.mean == pytest.approx(0.5)


class TestWarnRate:
    """Tests that warn_rate tracks WARN findings on clean cases (informational)."""

    def test_warn_rate_counts_warn_on_clean_cases(self) -> None:
        """WARN finding on clean case produces warn_rate=1.0."""
        case = CaseResult(
            case_id="clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.WARN)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={},
            pass_at_k={},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        assert result.warn_rate == pytest.approx(1.0)

    def test_warn_rate_zero_when_no_warns(self) -> None:
        """No WARN findings on clean cases produces warn_rate=0.0."""
        case = CaseResult(
            case_id="clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.NIT)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={},
            pass_at_k={},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        assert result.warn_rate == pytest.approx(0.0)

    def test_warn_rate_excludes_non_clean_cases(self) -> None:
        """Non-clean cases do not contribute to warn_rate."""
        non_clean = CaseResult(
            case_id="has-expected",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[_finding("F1", severity=Severity.WARN)],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={"EF1": True},
            pass_at_k={"EF1": True},
        )

        result = aggregate_metrics([non_clean], _DEFAULT_THRESHOLDS)

        assert result.warn_rate == pytest.approx(0.0)

    def test_warn_rate_independent_of_fp_rate(self) -> None:
        """BUG and WARN on same clean trial: fp_rate=1.0, warn_rate=1.0."""
        case = CaseResult(
            case_id="clean",
            trials=[
                TrialResult(
                    trial_number=1,
                    findings=[
                        _finding("F1", severity=Severity.BUG),
                        _finding("F2", severity=Severity.WARN),
                    ],
                    graded=[],
                    metrics=_DUMMY_METRICS,
                ),
            ],
            pass_at_1={},
            pass_at_k={},
        )

        result = aggregate_metrics([case], _DEFAULT_THRESHOLDS)

        assert result.fp_rate.mean == pytest.approx(1.0)
        assert result.warn_rate == pytest.approx(1.0)


# ===========================================================================
# pass@1 / pass@k rate computation
# ===========================================================================


class TestPassAtRateComputation:
    """Tests that pass_at_1_rate and pass_at_k_rate are computed correctly."""

    def test_pass_at_1_rate_total_caught_over_total_expected(self) -> None:
        """pass_at_1_rate = total expected findings caught in trial 1 / total expected."""
        cases = [
            CaseResult(
                case_id="c1",
                trials=[TrialResult(
                    trial_number=1, findings=[], graded=[], metrics=_DUMMY_METRICS,
                )],
                pass_at_1={"EF1": True, "EF2": False},
                pass_at_k={"EF1": True, "EF2": False},
            ),
            CaseResult(
                case_id="c2",
                trials=[TrialResult(
                    trial_number=1, findings=[], graded=[], metrics=_DUMMY_METRICS,
                )],
                pass_at_1={"EF3": True, "EF4": True},
                pass_at_k={"EF3": True, "EF4": True},
            ),
        ]

        result = aggregate_metrics(cases, _DEFAULT_THRESHOLDS)

        # 3 caught at trial 1 out of 4 total = 0.75
        assert result.pass_at_1_rate == pytest.approx(0.75)

    def test_pass_at_k_rate_total_caught_any_trial_over_total_expected(self) -> None:
        """pass_at_k_rate = total expected findings caught in any trial / total expected."""
        cases = [
            CaseResult(
                case_id="c1",
                trials=[TrialResult(
                    trial_number=1, findings=[], graded=[], metrics=_DUMMY_METRICS,
                )],
                pass_at_1={"EF1": False, "EF2": False},
                pass_at_k={"EF1": True, "EF2": False},
            ),
            CaseResult(
                case_id="c2",
                trials=[TrialResult(
                    trial_number=1, findings=[], graded=[], metrics=_DUMMY_METRICS,
                )],
                pass_at_1={"EF3": False},
                pass_at_k={"EF3": True},
            ),
        ]

        result = aggregate_metrics(cases, _DEFAULT_THRESHOLDS)

        # pass_at_k: 2 caught out of 3 total = 2/3
        assert result.pass_at_k_rate == pytest.approx(2 / 3)

    def test_mixed_caught_missed_across_cases(self) -> None:
        """With a mix of caught/missed across multiple cases, both rates are correct."""
        cases = [
            CaseResult(
                case_id="c1",
                trials=[TrialResult(
                    trial_number=1, findings=[], graded=[], metrics=_DUMMY_METRICS,
                )],
                pass_at_1={"EF1": True, "EF2": False, "EF3": False},
                pass_at_k={"EF1": True, "EF2": True, "EF3": False},
            ),
            CaseResult(
                case_id="c2",
                trials=[TrialResult(
                    trial_number=1, findings=[], graded=[], metrics=_DUMMY_METRICS,
                )],
                pass_at_1={"EF4": True},
                pass_at_k={"EF4": True},
            ),
        ]

        result = aggregate_metrics(cases, _DEFAULT_THRESHOLDS)

        # pass_at_1: EF1 + EF4 caught = 2 / 4 = 0.5
        assert result.pass_at_1_rate == pytest.approx(0.5)
        # pass_at_k: EF1 + EF2 + EF4 caught = 3 / 4 = 0.75
        assert result.pass_at_k_rate == pytest.approx(0.75)
