"""Reporter -- scorecard generation + rendering for the eval harness.

Generates markdown and JSON scorecards from completed eval runs.
Compares runs to detect regressions and improvements.
"""

from __future__ import annotations

import math
import statistics

from eval.models import (
    CaseResult,
    CaseSummary,
    ComparisonResult,
    EvalRun,
    MetricDelta,
    MetricStatus,
    MetricWithSEM,
    Scorecard,
    TrialResult,
)
from server.models import Severity


# Metrics where lower is better (use <= threshold).
_LTE_METRICS = {"fp_rate"}

# Ordered list of metrics to display in the scorecard table.
_METRIC_DISPLAY_ORDER = [
    ("precision", "Precision"),
    ("recall", "Recall"),
    ("severity_accuracy", "Severity Accuracy"),
    ("category_accuracy", "Category Accuracy"),
    ("fp_rate", "FP Rate"),
    ("snr", "SNR"),
    ("rebuttal_accuracy", "Rebuttal Accuracy"),
]


def generate_scorecard(
    run: EvalRun,
    thresholds: dict[str, float],
    case_descriptions: dict[str, str] | None = None,
    case_expected_counts: dict[str, int] | None = None,
) -> Scorecard:
    """Generate a scorecard from an eval run.

    Args:
        run: Completed eval run with cases and aggregate metrics.
        thresholds: Metric name -> threshold value mapping.
        case_descriptions: Optional case_id -> description mapping.
            Falls back to case_id if not provided.
        case_expected_counts: Optional case_id -> expected finding count.
            When provided, used for accurate per-case expected_count.

    Returns:
        Scorecard with per-case summaries.
    """
    descriptions = case_descriptions or {}
    expected_counts = case_expected_counts or {}
    summaries = [
        _build_case_summary(case, descriptions, expected_counts)
        for case in run.cases
    ]

    return Scorecard(
        run=run,
        thresholds=thresholds,
        per_case_summary=summaries,
        comparison=None,
    )


def _build_case_summary(
    case: CaseResult,
    descriptions: dict[str, str],
    expected_counts: dict[str, int] | None = None,
) -> CaseSummary:
    """Build a CaseSummary from a CaseResult by averaging trial metrics.

    Errored trials carry zero metrics that would otherwise poison the
    per-case averages; exclude them here so the per-case display is
    consistent with aggregate_metrics (which also skips errored trials).
    """
    valid_trials = [t for t in case.trials if t.error is None]
    # Dual-metric fixed trials are independent clean observations; include
    # them in per-case aggregates so the scorecard mirrors aggregate_metrics
    # and surfaces fixed-side hallucinations (FR-015 / spec.md:90).
    fixed_trials: list[TrialResult] = []
    if case.dual_metric_results is not None:
        fixed_trials = [
            t for t in case.dual_metric_results.fixed_results if t.error is None
        ]
    combined_trials = valid_trials + fixed_trials

    if combined_trials:
        precisions = [
            t.metrics.precision for t in combined_trials
            if not math.isnan(t.metrics.precision)
        ]
        recalls = [
            t.metrics.recall for t in combined_trials
            if not math.isnan(t.metrics.recall)
        ]
        avg_precision = (
            statistics.mean(precisions) if precisions else 0.0
        )
        avg_recall = statistics.mean(recalls) if recalls else 0.0
        total_finding_count = sum(
            t.metrics.finding_count for t in combined_trials
        )
        total_novel_count = sum(
            t.metrics.novel_count for t in combined_trials
        )
    else:
        avg_precision = 0.0
        avg_recall = 0.0
        total_finding_count = 0
        total_novel_count = 0

    # Use authoritative expected count from golden case when available,
    # fall back to pass_at_1 keys (which track expected finding IDs).
    counts = expected_counts or {}
    if case.case_id in counts:
        expected_count = counts[case.case_id]
    else:
        expected_count = len(case.pass_at_1)

    # pass_fail:
    #   - cases with expected findings: all pass_at_k checks must pass AND
    #     no BUG false positive on any fixed-side trial (dual-metric cases)
    #   - clean cases (no expected findings): no BUG-severity finding in any
    #     valid trial (matches fp_rate definition — WARN on clean code is
    #     expected reviewer behavior, not a false positive)
    def _has_bug(trials: list[TrialResult]) -> bool:
        return any(
            any(f.severity == Severity.BUG for f in t.findings)
            for t in trials
        )

    if case.pass_at_k:
        pass_fail = all(case.pass_at_k.values()) and not _has_bug(fixed_trials)
    else:
        pass_fail = not _has_bug(valid_trials) and not _has_bug(fixed_trials)

    return CaseSummary(
        case_id=case.case_id,
        description=descriptions.get(case.case_id, case.case_id),
        pass_fail=pass_fail,
        precision=avg_precision,
        recall=avg_recall,
        finding_count=total_finding_count,
        expected_count=expected_count,
        novel_count=total_novel_count,
    )


def render_markdown(scorecard: Scorecard) -> str:
    """Render scorecard as a markdown string.

    Format follows the spec: header, metadata, metrics table,
    per-case summary, comparison (if present), and overall result.
    """
    run = scorecard.run
    agg = run.aggregate
    lines: list[str] = []

    # --- Header ---
    lines.append("# Eval Scorecard")
    lines.append("")
    lines.append(
        f"**Run ID**: {run.run_id} | "
        f"**Date**: {run.timestamp.isoformat()} | "
        f"**Duration**: {run.duration_seconds}s"
    )
    lines.append(
        f"**Model**: {run.model_evaluated} | "
        f"**Grader**: {run.grader_model} ({run.grader_prompt_version})"
    )
    lines.append(
        f"**Trials**: {run.num_trials} | "
        f"**Cases**: {len(run.cases)}"
    )
    lines.append("")

    # --- Metrics table ---
    lines.append("## Metrics")
    lines.append("")
    lines.append(
        "| Metric | Value | SEM | 95% CI | Method | Threshold | Pass |"
    )
    lines.append(
        "|--------|-------|-----|--------|--------|-----------|------|"
    )

    for key, label in _METRIC_DISPLAY_ORDER:
        metric: MetricWithSEM | None = getattr(agg, key, None)
        if metric is None:
            continue

        threshold_val = scorecard.thresholds.get(key)
        threshold_str = _format_threshold(key, threshold_val)
        pass_str = {
            MetricStatus.PASS: "PASS",
            MetricStatus.FAIL: "FAIL",
            MetricStatus.INCONCLUSIVE: "INCONCLUSIVE",
        }[metric.status]

        lines.append(
            f"| {label} "
            f"| {metric.mean:.2f} "
            f"| {metric.sem:.2f} "
            f"| [{metric.ci_lower:.2f}, {metric.ci_upper:.2f}] "
            f"| {metric.method.value} "
            f"| {threshold_str} "
            f"| {pass_str} |"
        )

    # warn_rate (informational, no threshold)
    lines.append(
        f"| Warn Rate (info) "
        f"| {agg.warn_rate:.2f} "
        f"| - "
        f"| - "
        f"| - "
        f"| - "
        f"| - |"
    )

    # pass@1 and pass@k rates (not MetricWithSEM, just floats)
    lines.append(
        f"| Pass@1 Rate "
        f"| {agg.pass_at_1_rate:.2f} "
        f"| - "
        f"| - "
        f"| - "
        f"| - "
        f"| - |"
    )
    lines.append(
        f"| Pass@k Rate "
        f"| {agg.pass_at_k_rate:.2f} "
        f"| - "
        f"| - "
        f"| - "
        f"| - "
        f"| - |"
    )
    # F16: FR-004 requires the aggregate novel-finding count to be visible
    # in the human-readable scorecard. The per-case table only shows
    # per-case novel counts; the run-wide total belongs in the metrics
    # section.
    lines.append(
        f"| Novel Findings (total) "
        f"| {agg.novel_count} "
        f"| - "
        f"| - "
        f"| - "
        f"| - "
        f"| - |"
    )
    lines.append("")

    # --- Per-case summary ---
    lines.append("## Per-Case Summary")
    lines.append("")
    lines.append(
        "| Case | Description | P/F | Precision | Recall "
        "| Findings | Expected | Novel |"
    )
    lines.append(
        "|------|-------------|-----|-----------|--------"
        "|----------|----------|-------|"
    )

    for cs in scorecard.per_case_summary:
        pf = "PASS" if cs.pass_fail else "FAIL"
        lines.append(
            f"| {cs.case_id} "
            f"| {cs.description} "
            f"| {pf} "
            f"| {cs.precision:.2f} "
            f"| {cs.recall:.2f} "
            f"| {cs.finding_count} "
            f"| {cs.expected_count} "
            f"| {cs.novel_count} |"
        )

    lines.append("")

    # --- Comparison (optional) ---
    if scorecard.comparison is not None:
        lines.extend(_render_comparison(scorecard.comparison))

    # --- Overall result ---
    result_str = "PASS" if run.pass_fail else "FAIL"
    if run.pass_fail:
        lines.append(f"## Result: {result_str} (all thresholds met)")
    else:
        lines.append(f"## Result: {result_str} (threshold failure)")

    lines.append("")
    return "\n".join(lines)


def _format_threshold(key: str, value: float | None) -> str:
    """Format a threshold value with the correct direction prefix."""
    if value is None:
        return "-"
    if key in _LTE_METRICS:
        return f"<= {value:.2f}"
    return f">= {value:.2f}"


def _render_comparison(comparison: ComparisonResult) -> list[str]:
    """Render the comparison section as markdown lines."""
    lines: list[str] = []
    lines.append("## Comparison")
    lines.append("")
    lines.append(
        f"**Baseline**: {comparison.baseline_run_id} "
        f"({comparison.baseline_timestamp.isoformat()})"
    )
    lines.append("")
    lines.append(
        "| Metric | Baseline | Current | Delta | Delta % | Status |"
    )
    lines.append(
        "|--------|----------|---------|-------|---------|--------|"
    )

    for metric_name, delta in comparison.deltas.items():
        if metric_name in comparison.regressions:
            status = "REGRESSION"
        elif metric_name in comparison.improvements:
            status = "IMPROVED"
        else:
            status = "-"

        lines.append(
            f"| {metric_name} "
            f"| {delta.baseline:.2f} "
            f"| {delta.current:.2f} "
            f"| {delta.delta:+.2f} "
            f"| {delta.delta_pct:+.1f}% "
            f"| {status} |"
        )

    lines.append("")

    if comparison.regressions:
        lines.append(
            f"**Regressions**: {', '.join(comparison.regressions)}"
        )
    if comparison.improvements:
        lines.append(
            f"**Improvements**: {', '.join(comparison.improvements)}"
        )
    lines.append("")

    return lines


def render_json(scorecard: Scorecard) -> str:
    """Render scorecard as a JSON string (serialized EvalRun).

    Uses Pydantic model_dump_json for the full EvalRun,
    ensuring schema-compliant output.
    """
    return scorecard.run.model_dump_json(indent=2)


def compare_runs(current: EvalRun, baseline: EvalRun) -> ComparisonResult:
    """Compare two eval runs and compute deltas.

    For each metric, computes:
    - delta = current.mean - baseline.mean
    - delta_pct = (delta / baseline.mean) * 100 (0 if baseline is 0)

    Regression/improvement detection:
    - "gte" metrics (precision, recall, etc.): decrease = regression, increase = improvement
    - "lte" metrics (fp_rate): increase = regression, decrease = improvement
    """
    deltas: dict[str, MetricDelta] = {}
    regressions: list[str] = []
    improvements: list[str] = []

    # Metrics to compare: all MetricWithSEM fields
    metric_keys = [
        "precision",
        "recall",
        "severity_accuracy",
        "category_accuracy",
        "fp_rate",
        "snr",
        "rebuttal_accuracy",
    ]

    for key in metric_keys:
        baseline_metric: MetricWithSEM | None = getattr(
            baseline.aggregate, key, None
        )
        current_metric: MetricWithSEM | None = getattr(
            current.aggregate, key, None
        )

        # Skip if either side lacks the metric
        if baseline_metric is None or current_metric is None:
            continue

        delta = current_metric.mean - baseline_metric.mean
        if baseline_metric.mean != 0.0:
            delta_pct = (delta / baseline_metric.mean) * 100
        else:
            delta_pct = 0.0

        deltas[key] = MetricDelta(
            baseline=baseline_metric.mean,
            current=current_metric.mean,
            delta=delta,
            delta_pct=delta_pct,
        )

        # Classify as regression or improvement
        if key in _LTE_METRICS:
            # Lower is better: increase = regression, decrease = improvement
            if delta > 0:
                regressions.append(key)
            elif delta < 0:
                improvements.append(key)
        else:
            # Higher is better: decrease = regression, increase = improvement
            if delta < 0:
                regressions.append(key)
            elif delta > 0:
                improvements.append(key)

    return ComparisonResult(
        baseline_run_id=baseline.run_id,
        baseline_timestamp=baseline.timestamp,
        deltas=deltas,
        regressions=regressions,
        improvements=improvements,
    )
