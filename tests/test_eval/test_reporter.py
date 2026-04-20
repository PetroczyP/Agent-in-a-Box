"""Tests for eval/reporter.py -- T007 Reporter + scorecard.

TDD RED phase: comprehensive tests for all reporter functions.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from eval.models import (
    AggregateMetrics,
    CaseResult,
    CaseSummary,
    ComparisonResult,
    EvalRun,
    MetricDelta,
    MetricWithSEM,
    RebuttalResult,
    Scorecard,
    TrialMetrics,
    TrialResult,
)
from eval.reporter import (
    compare_runs,
    generate_scorecard,
    render_json,
    render_markdown,
)
from server.models import FindingStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric(
    mean: float,
    sem: float = 0.03,
    passes: bool = True,
) -> MetricWithSEM:
    """Create a MetricWithSEM with auto-computed CI bounds."""
    return MetricWithSEM(
        mean=mean,
        sem=sem,
        ci_lower=mean - 1.96 * sem,
        ci_upper=mean + 1.96 * sem,
        passes_threshold=passes,
    )


def _trial_metrics(
    precision: float = 0.85,
    recall: float = 0.90,
    novel_count: int = 1,
    finding_count: int = 5,
) -> TrialMetrics:
    """Create minimal TrialMetrics."""
    return TrialMetrics(
        precision=precision,
        recall=recall,
        severity_accuracy=0.90,
        category_accuracy=0.80,
        snr=4.0,
        novel_count=novel_count,
        grading_error_count=0,
        finding_count=finding_count,
    )


def _trial(
    trial_number: int = 1,
    precision: float = 0.85,
    recall: float = 0.90,
    novel_count: int = 1,
    finding_count: int = 5,
) -> TrialResult:
    """Create a minimal TrialResult."""
    return TrialResult(
        trial_number=trial_number,
        findings=[],
        graded=[],
        metrics=_trial_metrics(
            precision=precision,
            recall=recall,
            novel_count=novel_count,
            finding_count=finding_count,
        ),
    )


def _case(
    case_id: str = "case-001",
    trials: list[TrialResult] | None = None,
    pass_at_1: dict[str, bool] | None = None,
    pass_at_k: dict[str, bool] | None = None,
    rebuttal_results: list[RebuttalResult] | None = None,
) -> CaseResult:
    """Create a minimal CaseResult."""
    return CaseResult(
        case_id=case_id,
        trials=trials or [_trial()],
        pass_at_1=pass_at_1 or {"precision": True, "recall": True},
        pass_at_k=pass_at_k or {"precision": True, "recall": True},
        rebuttal_results=rebuttal_results,
    )


def _aggregate(
    rebuttal_accuracy: MetricWithSEM | None = None,
    pass_at_1_rate: float = 1.0,
    pass_at_k_rate: float = 1.0,
) -> AggregateMetrics:
    """Create a minimal AggregateMetrics."""
    return AggregateMetrics(
        precision=_metric(0.85),
        recall=_metric(0.78),
        severity_accuracy=_metric(0.90),
        category_accuracy=_metric(0.80),
        fp_rate=_metric(0.15, passes=True),
        rebuttal_accuracy=rebuttal_accuracy,
        snr=_metric(4.5),
        novel_count=3,
        pass_at_1_rate=pass_at_1_rate,
        pass_at_k_rate=pass_at_k_rate,
    )


def _eval_run(
    run_id: str = "run-001",
    cases: list[CaseResult] | None = None,
    aggregate: AggregateMetrics | None = None,
    pass_fail: bool = True,
    duration: float = 120.5,
) -> EvalRun:
    """Create a minimal EvalRun."""
    return EvalRun(
        run_id=run_id,
        timestamp=datetime(2026, 4, 1, 12, 0, 0),
        model_evaluated="copilot-gpt-4",
        grader_model="claude-sonnet-4-20250514",
        grader_prompt_version="abc123",
        num_trials=3,
        line_tolerance=5,
        cases=cases or [_case()],
        aggregate=aggregate or _aggregate(),
        pass_fail=pass_fail,
        duration_seconds=duration,
    )


def _case_descriptions() -> dict[str, str]:
    """Map case IDs to descriptions for scorecard generation."""
    return {
        "case-001": "SQL injection in query builder",
        "case-002": "XSS in template rendering",
        "case-003": "Multi-turn rebuttal test case",
    }


# ===========================================================================
# generate_scorecard
# ===========================================================================


class TestGenerateScorecard:
    """Tests for generate_scorecard function."""

    def test_creates_scorecard_with_run(self) -> None:
        """Scorecard wraps the EvalRun and thresholds."""
        run = _eval_run()
        thresholds = {"precision": 0.70, "recall": 0.60}
        descriptions = _case_descriptions()

        sc = generate_scorecard(run, thresholds, descriptions)

        assert sc.run == run
        assert sc.thresholds == thresholds

    def test_creates_case_summaries(self) -> None:
        """generate_scorecard creates CaseSummary for each case."""
        trial1 = _trial(trial_number=1, precision=0.80, recall=0.90, novel_count=1, finding_count=5)
        trial2 = _trial(trial_number=2, precision=0.90, recall=0.80, novel_count=2, finding_count=6)
        case = _case(case_id="case-001", trials=[trial1, trial2])
        run = _eval_run(cases=[case])
        thresholds = {"precision": 0.70, "recall": 0.60}
        descriptions = {"case-001": "SQL injection in query builder"}

        sc = generate_scorecard(run, thresholds, descriptions)

        assert len(sc.per_case_summary) == 1
        summary = sc.per_case_summary[0]
        assert summary.case_id == "case-001"
        assert summary.description == "SQL injection in query builder"
        # avg precision: (0.80 + 0.90) / 2 = 0.85
        assert summary.precision == pytest.approx(0.85)
        # avg recall: (0.90 + 0.80) / 2 = 0.85
        assert summary.recall == pytest.approx(0.85)
        # sum finding_count: 5 + 6 = 11
        assert summary.finding_count == 11
        # sum novel_count: 1 + 2 = 3
        assert summary.novel_count == 3

    def test_case_summary_expected_count(self) -> None:
        """CaseSummary.expected_count comes from pass_at_1 dict length."""
        case = _case(
            case_id="case-001",
            pass_at_1={"precision": True, "recall": True, "severity": False},
        )
        run = _eval_run(cases=[case])
        descriptions = {"case-001": "Test case"}

        sc = generate_scorecard(run, {"precision": 0.70}, descriptions)

        # expected_count is derived from the thresholds count checked
        summary = sc.per_case_summary[0]
        assert summary.expected_count >= 0

    def test_case_summary_pass_fail(self) -> None:
        """CaseSummary.pass_fail is True when all pass_at_k values are True."""
        passing_case = _case(
            case_id="case-001",
            pass_at_k={"precision": True, "recall": True},
        )
        failing_case = _case(
            case_id="case-002",
            pass_at_k={"precision": True, "recall": False},
        )
        run = _eval_run(cases=[passing_case, failing_case])
        descriptions = {"case-001": "Passing case", "case-002": "Failing case"}

        sc = generate_scorecard(run, {"precision": 0.70}, descriptions)

        summaries = {s.case_id: s for s in sc.per_case_summary}
        assert summaries["case-001"].pass_fail is True
        assert summaries["case-002"].pass_fail is False

    def test_missing_description_uses_case_id(self) -> None:
        """When description not in map, falls back to case_id."""
        case = _case(case_id="case-999")
        run = _eval_run(cases=[case])

        sc = generate_scorecard(run, {}, {})

        assert sc.per_case_summary[0].description == "case-999"

    def test_comparison_is_none_by_default(self) -> None:
        """Scorecard.comparison is None when not provided."""
        run = _eval_run()

        sc = generate_scorecard(run, {}, _case_descriptions())

        assert sc.comparison is None

    def test_per_case_summary_excludes_errored_trials(self) -> None:
        """Errored trials must be excluded from per-case precision/recall."""
        good_trial = TrialResult(
            trial_number=1,
            findings=[],
            graded=[],
            metrics=_trial_metrics(precision=0.9, recall=0.8, finding_count=5),
        )
        bad_trial = TrialResult(
            trial_number=2,
            findings=[],
            graded=[],
            metrics=_trial_metrics(precision=0.0, recall=0.0, finding_count=0),
            error="MCP transport failure",
        )
        case = _case(case_id="case-001", trials=[good_trial, bad_trial])
        run = _eval_run(cases=[case])

        sc = generate_scorecard(run, {}, {"case-001": "Flaky case"})

        summary = sc.per_case_summary[0]
        assert summary.precision == pytest.approx(0.9)
        assert summary.recall == pytest.approx(0.8)
        assert summary.finding_count == 5  # errored trial's zeros not summed

    def test_clean_case_with_bug_false_positive_fails(self) -> None:
        """Clean cases (no expected findings) must fail when any valid trial
        emits a BUG finding. Prior behavior rendered PASS unconditionally
        because CaseSummary.pass_fail was derived only from pass_at_k, which
        is empty for clean cases — masking false positives in the scorecard.
        """
        from server.models import (
            Category,
            Confidence,
            Finding,
            FindingStatus,
            Location,
            Severity,
        )

        fp_finding = Finding(
            finding_id="F-001",
            rule_id="bogus-bug",
            severity=Severity.BUG,
            category=Category.CORRECTNESS,
            message="False positive",
            primary_location=Location(file="clean.py", start_line=1, end_line=1),
            related_locations=[],
            fingerprint="a" * 16,
            confidence=Confidence.HIGH,
            evidence="x = 1",
            status=FindingStatus.OPEN,
        )
        trial = TrialResult(
            trial_number=1,
            findings=[fp_finding],
            graded=[],
            metrics=_trial_metrics(precision=0.0, recall=0.0, finding_count=1),
        )
        clean_case = CaseResult(
            case_id="clean-001",
            trials=[trial],
            pass_at_1={},
            pass_at_k={},
        )
        run = _eval_run(cases=[clean_case])

        sc = generate_scorecard(run, {}, {"clean-001": "Clean code"})

        summary = sc.per_case_summary[0]
        assert summary.expected_count == 0
        assert summary.finding_count == 1
        assert summary.pass_fail is False

    def test_clean_case_with_no_findings_passes(self) -> None:
        """Clean cases with zero findings in all valid trials must pass."""
        trial = TrialResult(
            trial_number=1,
            findings=[],
            graded=[],
            metrics=_trial_metrics(precision=1.0, recall=0.0, finding_count=0),
        )
        clean_case = CaseResult(
            case_id="clean-002",
            trials=[trial],
            pass_at_1={},
            pass_at_k={},
        )
        run = _eval_run(cases=[clean_case])

        sc = generate_scorecard(run, {}, {"clean-002": "Clean code"})

        assert sc.per_case_summary[0].pass_fail is True

    def test_clean_case_with_only_warn_finding_passes(self) -> None:
        """WARN findings on clean cases are expected reviewer behavior
        (design observations) and do not count as false positives — must
        render PASS, matching the fp_rate definition."""
        from server.models import (
            Category,
            Confidence,
            Finding,
            FindingStatus,
            Location,
            Severity,
        )

        warn_finding = Finding(
            finding_id="F-001",
            rule_id="design-observation",
            severity=Severity.WARN,
            category=Category.DESIGN,
            message="Consider refactoring",
            primary_location=Location(file="clean.py", start_line=1, end_line=1),
            related_locations=[],
            fingerprint="b" * 16,
            confidence=Confidence.HIGH,
            evidence="x = 1",
            status=FindingStatus.OPEN,
        )
        trial = TrialResult(
            trial_number=1,
            findings=[warn_finding],
            graded=[],
            metrics=_trial_metrics(precision=1.0, recall=0.0, finding_count=1),
        )
        clean_case = CaseResult(
            case_id="clean-003",
            trials=[trial],
            pass_at_1={},
            pass_at_k={},
        )
        run = _eval_run(cases=[clean_case])

        sc = generate_scorecard(run, {}, {"clean-003": "Clean code"})

        assert sc.per_case_summary[0].pass_fail is True

    def test_dual_metric_fixed_side_bug_false_positive_fails_summary(self) -> None:
        """Dual-metric case with a fixed-side BUG FP must surface as FAIL.

        Regression guard for F9: the per-case summary previously considered
        only ``case.trials`` (vulnerable half) and pass_at_k, so a correct
        vulnerable detection plus a fixed-side false positive rendered PASS
        with zero visibility into the fixed hallucination. Spec.md:90 /
        FR-015 require both halves to contribute to the per-case view.
        """
        from eval.models import DualMetricResult
        from server.models import (
            Category,
            Confidence,
            Finding,
            Location,
            Severity,
        )

        matched_finding = Finding(
            finding_id="F-001",
            rule_id="bug-rule",
            severity=Severity.BUG,
            category=Category.CORRECTNESS,
            message="Real bug",
            primary_location=Location(file="vuln.py", start_line=1, end_line=1),
            related_locations=[],
            fingerprint="v" * 16,
            confidence=Confidence.HIGH,
            evidence="bad()",
            status=FindingStatus.OPEN,
        )
        vulnerable_trial = TrialResult(
            trial_number=1,
            findings=[matched_finding],
            graded=[],
            metrics=_trial_metrics(precision=1.0, recall=1.0, finding_count=1),
        )

        fp_finding = Finding(
            finding_id="F-002",
            rule_id="bug-rule",
            severity=Severity.BUG,
            category=Category.CORRECTNESS,
            message="Hallucination on fixed bundle",
            primary_location=Location(file="fixed.py", start_line=1, end_line=1),
            related_locations=[],
            fingerprint="f" * 16,
            confidence=Confidence.HIGH,
            evidence="good()",
            status=FindingStatus.OPEN,
        )
        fixed_trial = TrialResult(
            trial_number=1,
            findings=[fp_finding],
            graded=[],
            metrics=_trial_metrics(precision=0.0, recall=0.0, finding_count=1),
        )

        dual = DualMetricResult(
            vulnerable_results=[vulnerable_trial],
            fixed_results=[fixed_trial],
        )
        case = CaseResult(
            case_id="dual-001",
            trials=[vulnerable_trial],
            pass_at_1={"EF1": True},
            pass_at_k={"EF1": True},
            dual_metric_results=dual,
        )
        run = _eval_run(cases=[case])

        sc = generate_scorecard(run, {}, {"dual-001": "Dual-metric case"})

        summary = sc.per_case_summary[0]
        assert summary.pass_fail is False
        # Fixed-side finding should surface in total finding_count
        assert summary.finding_count == 2


# ===========================================================================
# render_markdown
# ===========================================================================


class TestRenderMarkdown:
    """Tests for render_markdown function."""

    def test_contains_header(self) -> None:
        """Markdown starts with '# Eval Scorecard'."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "# Eval Scorecard" in md

    def test_contains_run_metadata(self) -> None:
        """Markdown includes run ID, date, model, grader, trials, case count."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "run-001" in md
        assert "copilot-gpt-4" in md
        assert "claude-sonnet-4-20250514" in md
        assert "abc123" in md
        assert "120.5" in md

    def test_contains_metrics_table(self) -> None:
        """Markdown contains metrics table with all core metrics."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "## Metrics" in md
        assert "Precision" in md
        assert "Recall" in md
        assert "Severity Accuracy" in md
        assert "Category Accuracy" in md
        assert "FP Rate" in md
        assert "SNR" in md

    def test_metrics_contain_sem_and_ci(self) -> None:
        """Each metric row includes SEM and 95% CI bounds."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        # Precision row should contain its SEM value (0.03)
        assert "0.03" in md

    def test_fp_rate_shows_lte_direction(self) -> None:
        """FP Rate threshold displayed as '<= X' not '>= X'."""
        thresholds = {"fp_rate": 0.20, "precision": 0.70}
        sc = _make_scorecard(thresholds=thresholds)
        md = render_markdown(sc)

        assert "<= 0.20" in md

    def test_gte_thresholds_show_gte_direction(self) -> None:
        """Non-fp_rate thresholds displayed as '>= X'."""
        thresholds = {"precision": 0.70, "recall": 0.60}
        sc = _make_scorecard(thresholds=thresholds)
        md = render_markdown(sc)

        assert ">= 0.70" in md
        assert ">= 0.60" in md

    def test_pass_fail_labels_in_metrics(self) -> None:
        """Metrics table shows PASS/FAIL for each metric."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "PASS" in md

    def test_pass_at_1_in_metrics(self) -> None:
        """Metrics table includes pass@1_rate."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "pass@1" in md.lower() or "Pass@1" in md

    def test_pass_at_k_in_metrics(self) -> None:
        """Metrics table includes pass@k_rate."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "pass@k" in md.lower() or "Pass@k" in md

    def test_aggregate_novel_count_rendered(self) -> None:
        """F16: FR-004 requires the aggregate novel-finding count to appear
        in the human-readable scorecard. Prior to the fix, the markdown
        metrics table had no row for it at all."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "Novel" in md
        # The aggregate novel count (sum across the run) must show up
        # in the metrics section, not only in per-case summary columns.
        metrics_section, _, rest = md.partition("## Per-Case Summary")
        assert "Novel" in metrics_section, (
            "Aggregate novel finding count must be listed in the metrics "
            "table (before the Per-Case Summary), not only per-case."
        )

    def test_per_case_summary_section(self) -> None:
        """Markdown contains per-case breakdown table."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "## Per-Case Summary" in md
        assert "case-001" in md

    def test_per_case_table_columns(self) -> None:
        """Per-case table has expected columns."""
        sc = _make_scorecard()
        md = render_markdown(sc)

        assert "Case" in md
        assert "Description" in md
        assert "P/F" in md
        assert "Precision" in md
        assert "Recall" in md
        assert "Findings" in md
        assert "Expected" in md
        assert "Novel" in md

    def test_overall_result_pass(self) -> None:
        """When pass_fail is True, result line says PASS."""
        sc = _make_scorecard(pass_fail=True)
        md = render_markdown(sc)

        assert "## Result: PASS" in md

    def test_overall_result_fail(self) -> None:
        """When pass_fail is False, result line says FAIL."""
        sc = _make_scorecard(pass_fail=False)
        md = render_markdown(sc)

        assert "## Result: FAIL" in md

    def test_rebuttal_accuracy_shown_when_present(self) -> None:
        """Rebuttal Accuracy row appears when rebuttal_accuracy is not None."""
        agg = _aggregate(rebuttal_accuracy=_metric(0.80, sem=0.05))
        sc = _make_scorecard(aggregate=agg)
        md = render_markdown(sc)

        assert "Rebuttal Accuracy" in md

    def test_rebuttal_accuracy_omitted_when_none(self) -> None:
        """Rebuttal Accuracy row absent when rebuttal_accuracy is None."""
        agg = _aggregate(rebuttal_accuracy=None)
        sc = _make_scorecard(aggregate=agg)
        md = render_markdown(sc)

        assert "Rebuttal Accuracy" not in md

    def test_wilson_insufficient_n_renders_inconclusive(self) -> None:
        """Metric with method=wilson_insufficient_n renders INCONCLUSIVE.

        Transparency requirement (B' coordinator ratification): the
        scorecard must never show PASS for a metric that was not
        actually gated. The status cell renders INCONCLUSIVE so humans
        reading the scorecard see the corpus-maturity state clearly.
        """
        inconclusive = MetricWithSEM(
            mean=1.0, sem=0.0,
            ci_lower=0.342, ci_upper=1.0,
            passes_threshold=False,
            method="wilson_insufficient_n",
        )
        agg = _aggregate(rebuttal_accuracy=inconclusive)
        sc = _make_scorecard(aggregate=agg)
        md = render_markdown(sc)

        assert "INCONCLUSIVE" in md
        # The row that is INCONCLUSIVE must not also say PASS in its status
        reb_lines = [
            line for line in md.splitlines()
            if "Rebuttal Accuracy" in line
        ]
        assert len(reb_lines) == 1
        assert "INCONCLUSIVE" in reb_lines[0]
        assert "| PASS" not in reb_lines[0]
        assert "| FAIL" not in reb_lines[0]

    def test_method_column_shown_in_metrics_table(self) -> None:
        """Metrics table includes the CI method used for each metric.

        Consumers need to know whether a metric used normal-approx,
        Wilson, BCa, or was inconclusive / vacuous — rendering the
        method resolves the AP-002 contract-drift concern from judge
        Round 12 M-1.
        """
        inconclusive = MetricWithSEM(
            mean=1.0, sem=0.0,
            ci_lower=0.342, ci_upper=1.0,
            passes_threshold=False,
            method="wilson_insufficient_n",
        )
        agg = _aggregate(rebuttal_accuracy=inconclusive)
        sc = _make_scorecard(aggregate=agg)
        md = render_markdown(sc)

        assert "Method" in md
        assert "wilson_insufficient_n" in md

    def test_comparison_section_when_present(self) -> None:
        """Comparison section appears when scorecard.comparison is set."""
        comparison = ComparisonResult(
            baseline_run_id="run-000",
            baseline_timestamp=datetime(2026, 3, 30, 12, 0, 0),
            deltas={
                "precision": MetricDelta(
                    baseline=0.80, current=0.85, delta=0.05, delta_pct=6.25,
                ),
            },
            regressions=[],
            improvements=["precision"],
        )
        sc = _make_scorecard(comparison=comparison)
        md = render_markdown(sc)

        assert "## Comparison" in md
        assert "run-000" in md
        assert "precision" in md.lower()

    def test_comparison_section_absent_when_none(self) -> None:
        """Comparison section not rendered when comparison is None."""
        sc = _make_scorecard(comparison=None)
        md = render_markdown(sc)

        assert "## Comparison" not in md

    def test_comparison_shows_regressions(self) -> None:
        """Regression metrics flagged in comparison section."""
        comparison = ComparisonResult(
            baseline_run_id="run-000",
            baseline_timestamp=datetime(2026, 3, 30, 12, 0, 0),
            deltas={
                "recall": MetricDelta(
                    baseline=0.90, current=0.75, delta=-0.15, delta_pct=-16.67,
                ),
            },
            regressions=["recall"],
            improvements=[],
        )
        sc = _make_scorecard(comparison=comparison)
        md = render_markdown(sc)

        assert "REGRESSION" in md or "regression" in md.lower()

    def test_comparison_shows_improvements(self) -> None:
        """Improvement metrics flagged in comparison section."""
        comparison = ComparisonResult(
            baseline_run_id="run-000",
            baseline_timestamp=datetime(2026, 3, 30, 12, 0, 0),
            deltas={
                "precision": MetricDelta(
                    baseline=0.80, current=0.90, delta=0.10, delta_pct=12.5,
                ),
            },
            regressions=[],
            improvements=["precision"],
        )
        sc = _make_scorecard(comparison=comparison)
        md = render_markdown(sc)

        assert "IMPROVED" in md or "improved" in md.lower()


# ===========================================================================
# render_json
# ===========================================================================


class TestRenderJSON:
    """Tests for render_json function."""

    def test_output_is_valid_json(self) -> None:
        """render_json returns valid JSON string."""
        sc = _make_scorecard()
        result = render_json(sc)

        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_json_matches_eval_run_schema(self) -> None:
        """JSON output contains all EvalRun fields."""
        sc = _make_scorecard()
        result = render_json(sc)

        parsed = json.loads(result)
        assert "run_id" in parsed
        assert "timestamp" in parsed
        assert "model_evaluated" in parsed
        assert "grader_model" in parsed
        assert "cases" in parsed
        assert "aggregate" in parsed
        assert "pass_fail" in parsed

    def test_json_roundtrip_to_eval_run(self) -> None:
        """JSON can be deserialized back to an EvalRun."""
        run = _eval_run()
        sc = _make_scorecard(run=run)
        result = render_json(sc)

        restored = EvalRun.model_validate_json(result)
        assert restored.run_id == run.run_id
        assert restored.model_evaluated == run.model_evaluated
        assert restored.pass_fail == run.pass_fail


# ===========================================================================
# compare_runs
# ===========================================================================


class TestCompareRuns:
    """Tests for compare_runs function."""

    def test_computes_deltas(self) -> None:
        """Deltas computed as current - baseline for each metric."""
        baseline_agg = _aggregate()
        baseline_agg.precision = _metric(0.80)
        current_agg = _aggregate()
        current_agg.precision = _metric(0.85)

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        assert "precision" in result.deltas
        d = result.deltas["precision"]
        assert d.baseline == pytest.approx(0.80)
        assert d.current == pytest.approx(0.85)
        assert d.delta == pytest.approx(0.05)

    def test_delta_pct_computation(self) -> None:
        """delta_pct = (delta / baseline) * 100."""
        baseline_agg = _aggregate()
        baseline_agg.recall = _metric(0.80)
        current_agg = _aggregate()
        current_agg.recall = _metric(0.90)

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        d = result.deltas["recall"]
        assert d.delta_pct == pytest.approx(12.5)

    def test_detects_regression_gte_metric(self) -> None:
        """A 'gte' metric (e.g., recall) decrease is a regression."""
        baseline_agg = _aggregate()
        baseline_agg.recall = _metric(0.90)
        current_agg = _aggregate()
        current_agg.recall = _metric(0.75)

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        assert "recall" in result.regressions

    def test_detects_improvement_gte_metric(self) -> None:
        """A 'gte' metric increase is an improvement."""
        baseline_agg = _aggregate()
        baseline_agg.precision = _metric(0.75)
        current_agg = _aggregate()
        current_agg.precision = _metric(0.90)

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        assert "precision" in result.improvements

    def test_detects_regression_lte_metric(self) -> None:
        """A 'lte' metric (fp_rate) increase is a regression."""
        baseline_agg = _aggregate()
        baseline_agg.fp_rate = _metric(0.10)
        current_agg = _aggregate()
        current_agg.fp_rate = _metric(0.25)

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        assert "fp_rate" in result.regressions

    def test_detects_improvement_lte_metric(self) -> None:
        """A 'lte' metric (fp_rate) decrease is an improvement."""
        baseline_agg = _aggregate()
        baseline_agg.fp_rate = _metric(0.25)
        current_agg = _aggregate()
        current_agg.fp_rate = _metric(0.10)

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        assert "fp_rate" in result.improvements

    def test_no_change_is_neutral(self) -> None:
        """When metrics are identical, no regressions or improvements."""
        run = _eval_run()

        result = compare_runs(run, run)

        assert len(result.regressions) == 0
        assert len(result.improvements) == 0

    def test_baseline_metadata_recorded(self) -> None:
        """ComparisonResult records baseline run_id and timestamp."""
        baseline = _eval_run(run_id="run-000")
        current = _eval_run(run_id="run-001")

        result = compare_runs(current, baseline)

        assert result.baseline_run_id == "run-000"
        assert result.baseline_timestamp == baseline.timestamp

    def test_rebuttal_accuracy_included_when_both_have_it(self) -> None:
        """Rebuttal accuracy delta computed when both runs have it."""
        baseline_agg = _aggregate(rebuttal_accuracy=_metric(0.70))
        current_agg = _aggregate(rebuttal_accuracy=_metric(0.85))

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        assert "rebuttal_accuracy" in result.deltas
        d = result.deltas["rebuttal_accuracy"]
        assert d.delta == pytest.approx(0.15)

    def test_rebuttal_accuracy_skipped_when_baseline_none(self) -> None:
        """Rebuttal accuracy omitted from deltas when baseline lacks it."""
        baseline_agg = _aggregate(rebuttal_accuracy=None)
        current_agg = _aggregate(rebuttal_accuracy=_metric(0.85))

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        assert "rebuttal_accuracy" not in result.deltas

    def test_delta_pct_zero_when_baseline_zero(self) -> None:
        """When baseline is 0, delta_pct should be 0 to avoid division by zero."""
        baseline_agg = _aggregate()
        baseline_agg.fp_rate = _metric(0.0)
        current_agg = _aggregate()
        current_agg.fp_rate = _metric(0.10)

        baseline = _eval_run(run_id="run-000", aggregate=baseline_agg)
        current = _eval_run(run_id="run-001", aggregate=current_agg)

        result = compare_runs(current, baseline)

        d = result.deltas["fp_rate"]
        assert d.delta_pct == pytest.approx(0.0)


# ===========================================================================
# Scorecard builder helper
# ===========================================================================


def _make_scorecard(
    run: EvalRun | None = None,
    thresholds: dict[str, float] | None = None,
    aggregate: AggregateMetrics | None = None,
    pass_fail: bool = True,
    comparison: ComparisonResult | None = None,
) -> Scorecard:
    """Build a Scorecard for testing render functions."""
    if thresholds is None:
        thresholds = {
            "precision": 0.70,
            "recall": 0.60,
            "severity_accuracy": 0.80,
            "category_accuracy": 0.70,
            "fp_rate": 0.20,
            "snr": 3.0,
        }
    if run is None:
        agg = aggregate or _aggregate()
        run = _eval_run(aggregate=agg, pass_fail=pass_fail)

    summary = CaseSummary(
        case_id="case-001",
        description="SQL injection in query builder",
        pass_fail=True,
        precision=0.85,
        recall=0.90,
        finding_count=5,
        expected_count=4,
        novel_count=1,
    )

    return Scorecard(
        run=run,
        thresholds=thresholds,
        per_case_summary=[summary],
        comparison=comparison,
    )


# ===========================================================================
# TestExpectedCountFromGoldenCase (M-1 fix)
# ===========================================================================


class TestExpectedCountFromGoldenCase:
    """expected_count uses authoritative count from golden case, not matched IDs."""

    def test_expected_count_from_case_expected_counts(self) -> None:
        """When case_expected_counts provided, uses that for expected_count."""
        from eval.models import GraderConfidence, GraderResult, GraderVerdict

        # Case with 3 expected findings but only 1 matched in grading
        graded = [
            GraderResult(
                tier=1, verdict=GraderVerdict.MATCH,
                confidence=GraderConfidence.HIGH,
                matched_expected_id="EF-001", actual_finding_id="F-001",
            ),
        ]
        trial = TrialResult(
            trial_number=1, findings=[], graded=graded,
            metrics=_trial_metrics(),
        )
        case_result = CaseResult(
            case_id="case-001",
            trials=[trial],
            pass_at_1={"EF-001": True, "EF-002": False, "EF-003": False},
            pass_at_k={"EF-001": True, "EF-002": False, "EF-003": False},
        )
        run = _eval_run(cases=[case_result])
        thresholds = {"precision": 0.70}

        scorecard = generate_scorecard(
            run, thresholds,
            case_expected_counts={"case-001": 3},
        )

        assert scorecard.per_case_summary[0].expected_count == 3

    def test_expected_count_falls_back_to_pass_at_1_keys(self) -> None:
        """Without case_expected_counts, uses len(pass_at_1) as fallback."""
        trial = TrialResult(
            trial_number=1, findings=[], graded=[],
            metrics=_trial_metrics(),
        )
        case_result = CaseResult(
            case_id="case-001",
            trials=[trial],
            pass_at_1={"EF-001": True, "EF-002": False},
            pass_at_k={"EF-001": True, "EF-002": True},
        )
        run = _eval_run(cases=[case_result])
        thresholds = {"precision": 0.70}

        scorecard = generate_scorecard(run, thresholds)

        assert scorecard.per_case_summary[0].expected_count == 2
