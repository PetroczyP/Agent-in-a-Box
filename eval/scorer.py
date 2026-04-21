"""Scorer — metrics computation + SEM for the eval harness.

Computes per-trial metrics from grading results and aggregates them
across cases/trials with Standard Error of Mean (SEM) and 95% CIs.
"""

from __future__ import annotations

import math
import statistics

import logging

from eval.models import (
    AggregateMetrics,
    CaseResult,
    CIMethod,
    ExpectedFinding,
    GraderResult,
    GraderVerdict,
    MetricWithSEM,
    TrialMetrics,
    TrialResult,
)
from server.models import Finding, Severity

import numpy as np
from scipy.stats import bootstrap as scipy_bootstrap
from sklearn.metrics import cohen_kappa_score

logger = logging.getLogger(__name__)

# Adjacency-weighted severity scoring for ordinal BUG > WARN > NIT scale.
# Adjacent mismatches (1 step) get partial credit; 2-step mismatches get 0.
_SEVERITY_SCORE: dict[tuple[Severity, Severity], float] = {
    (Severity.BUG, Severity.BUG): 1.0,
    (Severity.BUG, Severity.WARN): 0.5,
    (Severity.BUG, Severity.NIT): 0.0,
    (Severity.WARN, Severity.BUG): 0.5,
    (Severity.WARN, Severity.WARN): 1.0,
    (Severity.WARN, Severity.NIT): 0.5,
    (Severity.NIT, Severity.BUG): 0.0,
    (Severity.NIT, Severity.WARN): 0.5,
    (Severity.NIT, Severity.NIT): 1.0,
}


def metric_with_sem(
    values: list[float],
    threshold: float,
    direction: str = "gte",
) -> MetricWithSEM:
    """Compute mean, SEM, CI bounds, and threshold pass/fail.

    Args:
        values: List of metric values (at least one).
        threshold: The threshold to compare against.
        direction: "gte" for >= threshold (uses ci_lower),
                   "lte" for <= threshold (uses ci_upper).

    Returns:
        MetricWithSEM with computed statistics.

    Raises:
        ValueError: If values is empty.
    """
    if not values:
        raise ValueError("metric_with_sem requires at least one value")

    mean = statistics.mean(values)

    if len(values) == 1:
        sem = 0.0
    else:
        stdev = statistics.stdev(values)
        sem = stdev / math.sqrt(len(values))

    ci_lower = mean - 1.96 * sem
    ci_upper = mean + 1.96 * sem

    if direction == "lte":
        passes = ci_upper <= threshold
    else:
        passes = ci_lower >= threshold

    return MetricWithSEM(
        mean=mean,
        sem=sem,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        passes_threshold=passes,
        method=CIMethod.NORMAL,
    )


def wilson_ci(
    successes: int,
    total: int,
    threshold: float,
    direction: str = "gte",
) -> MetricWithSEM:
    """Wilson score interval for Bernoulli proportion metrics.

    Used for fp_rate and rebuttal_accuracy where the underlying data
    is binary (success/failure) rather than continuous.
    """
    if total == 0:
        return MetricWithSEM(
            mean=0.0,
            sem=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            passes_threshold=(direction == "lte"),
            method=CIMethod.WILSON,
        )

    p_hat = successes / total
    z = 1.96  # 95% CI
    n = total

    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    spread = z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) / denom

    ci_lower = max(0.0, center - spread)
    ci_upper = min(1.0, center + spread)

    sem = math.sqrt(p_hat * (1 - p_hat) / total)

    if direction == "lte":
        passes = ci_upper <= threshold
    else:
        passes = ci_lower >= threshold

    return MetricWithSEM(
        mean=p_hat,
        sem=sem,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        passes_threshold=passes,
        method=CIMethod.WILSON,
    )


def bca_ci(
    values: list[float],
    threshold: float,
    direction: str = "gte",
    n_resamples: int = 9999,
) -> MetricWithSEM:
    """BCa bootstrap CI for per-trial rate aggregations.

    Used for precision, recall, severity_accuracy, category_accuracy.
    Falls back to normal-approximation CI when sample size is too small
    or variance is zero.
    """
    if not values:
        raise ValueError("bca_ci requires at least one value")

    mean = statistics.mean(values)

    if len(values) == 1:
        return MetricWithSEM(
            mean=mean,
            sem=0.0,
            ci_lower=mean,
            ci_upper=mean,
            passes_threshold=(
                mean <= threshold if direction == "lte" else mean >= threshold
            ),
            method=CIMethod.BCA,
        )

    stdev = statistics.stdev(values)
    sem = stdev / math.sqrt(len(values))

    # Fall back to normal approximation if too few samples or zero variance
    if len(values) < 3 or stdev == 0:
        ci_lower = mean - 1.96 * sem
        ci_upper = mean + 1.96 * sem
        if direction == "lte":
            passes = ci_upper <= threshold
        else:
            passes = ci_lower >= threshold
        return MetricWithSEM(
            mean=mean,
            sem=sem,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            passes_threshold=passes,
            method=CIMethod.NORMAL,
        )

    try:
        result = scipy_bootstrap(
            (np.array(values),),
            statistic=np.mean,
            confidence_level=0.95,
            method="BCa",
            n_resamples=n_resamples,
            random_state=42,
        )
        ci_lower = float(result.confidence_interval.low)
        ci_upper = float(result.confidence_interval.high)
        method = CIMethod.BCA
    except (ValueError, ZeroDivisionError) as exc:
        # scipy raises ValueError for degenerate samples (all identical) and
        # ZeroDivisionError when bootstrap acceleration hits a zero variance.
        # RuntimeWarning is not raised as an exception — warnings propagate
        # via the warnings module; scipy's degenerate cases either raise
        # ValueError or return finite fallback bounds, so no warning capture
        # is needed here.
        logger.warning(
            "BCa bootstrap fell back to normal CI (n=%d): %s", len(values), exc,
        )
        ci_lower = mean - 1.96 * sem
        ci_upper = mean + 1.96 * sem
        method = CIMethod.NORMAL

    if direction == "lte":
        passes = ci_upper <= threshold
    else:
        passes = ci_lower >= threshold

    return MetricWithSEM(
        mean=mean,
        sem=sem,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        passes_threshold=passes,
        method=method,
    )


def _filter_nan(values: list[float]) -> list[float]:
    """Filter NaN values from a list of floats."""
    return [v for v in values if not math.isnan(v)]


def compute_trial_metrics(
    graded: list[GraderResult],
    expected_findings: list[ExpectedFinding],
    findings: list[Finding],
) -> TrialMetrics:
    """Compute metrics for a single trial from grading results.

    Scoring contract:
    - grading_error findings are excluded from ALL metrics.
    - novel_valid findings are excluded from precision (both num and denom).
    - precision = (match + partial_match) / (match + partial_match + no_match)
    - recall = unique matched expected IDs / total expected findings
    - snr = (match + partial_match + novel_valid) / no_match
    - severity_accuracy = adjacency-weighted severity score / unique matched expected IDs
      (adjacent mismatch = 0.5, two-step = 0.0; best per expected ID when deduped)
    - category_accuracy = correct category / unique matched expected IDs
      (best per expected ID when deduped)
    """
    # Filter out grading errors
    active = [g for g in graded if g.verdict != GraderVerdict.GRADING_ERROR]
    grading_error_count = len(graded) - len(active)

    # Count verdicts
    match_count = sum(
        1 for g in active if g.verdict == GraderVerdict.MATCH
    )
    partial_count = sum(
        1 for g in active if g.verdict == GraderVerdict.PARTIAL_MATCH
    )
    novel_count = sum(
        1 for g in active if g.verdict == GraderVerdict.NOVEL_VALID
    )
    no_match_count = sum(
        1 for g in active if g.verdict == GraderVerdict.NO_MATCH
    )

    # --- Precision ---
    # Excludes novel_valid entirely
    precision_num = match_count + partial_count
    precision_denom = match_count + partial_count + no_match_count
    precision = precision_num / precision_denom if precision_denom > 0 else 1.0

    # --- Recall ---
    # Unique matched expected IDs / total expected
    matched_ids: set[str] = set()
    for g in active:
        if g.verdict in (GraderVerdict.MATCH, GraderVerdict.PARTIAL_MATCH):
            if g.matched_expected_id is not None:
                matched_ids.add(g.matched_expected_id)

    total_expected = len(expected_findings)
    # Clean-code trials have no recall denominator; emit NaN so the
    # aggregator's ``_filter_nan`` drops the trial instead of averaging a
    # bogus 0.0 into the run-level recall (FR-004).
    recall = (
        len(matched_ids) / total_expected if total_expected > 0 else math.nan
    )

    # --- SNR ---
    signal = match_count + partial_count + novel_count
    noise = no_match_count
    snr = signal / noise if noise > 0 else math.nan

    # --- Severity & Category accuracy ---
    # Build lookup tables
    expected_by_id = {ef.expected_id: ef for ef in expected_findings}
    finding_by_id = {f.finding_id: f for f in findings}

    matched_graded = [
        g for g in active
        if g.verdict in (GraderVerdict.MATCH, GraderVerdict.PARTIAL_MATCH)
        and g.matched_expected_id is not None
    ]

    # Dedup: keep the best severity score per expected finding ID.
    # When multiple actual findings match one expected finding, we count
    # once (with the highest adjacency score) to avoid amplification.
    best_severity_by_ef: dict[str, float] = {}
    best_category_by_ef: dict[str, float] = {}
    for g in matched_graded:
        ef = expected_by_id.get(g.matched_expected_id)  # type: ignore[arg-type]
        actual = finding_by_id.get(g.actual_finding_id)
        if ef is None or actual is None:
            continue
        ef_id = ef.expected_id

        sev_score = _SEVERITY_SCORE.get(
            (ef.severity, actual.severity), 0.0
        )
        cat_score = 1.0 if actual.category == ef.category else 0.0

        best_severity_by_ef[ef_id] = max(
            best_severity_by_ef.get(ef_id, 0.0), sev_score
        )
        best_category_by_ef[ef_id] = max(
            best_category_by_ef.get(ef_id, 0.0), cat_score
        )

    total_unique = len(best_severity_by_ef)

    severity_accuracy = (
        sum(best_severity_by_ef.values()) / total_unique
        if total_unique > 0
        else math.nan
    )
    category_accuracy = (
        sum(best_category_by_ef.values()) / total_unique
        if total_unique > 0
        else math.nan
    )

    # Collect deduped severity label pairs for qwk computation
    severity_pairs: list[list[str]] = []
    for ef_id in best_severity_by_ef:
        ef = expected_by_id.get(ef_id)
        if ef is None:
            continue
        # Find the actual finding that produced the best severity score
        best_actual_sev = None
        best_score = -1.0
        for g in matched_graded:
            if g.matched_expected_id == ef_id:
                actual = finding_by_id.get(g.actual_finding_id)
                if actual is not None:
                    score = _SEVERITY_SCORE.get((ef.severity, actual.severity), 0.0)
                    if score > best_score:
                        best_score = score
                        best_actual_sev = actual.severity
        if best_actual_sev is not None:
            severity_pairs.append([ef.severity.value, best_actual_sev.value])

    return TrialMetrics(
        precision=precision,
        recall=recall,
        severity_accuracy=severity_accuracy,
        category_accuracy=category_accuracy,
        snr=snr,
        novel_count=novel_count,
        grading_error_count=grading_error_count,
        finding_count=len(findings),
        severity_pairs=severity_pairs,
    )


def aggregate_metrics(
    case_results: list[CaseResult],
    thresholds: dict[str, float],
) -> AggregateMetrics:
    """Aggregate metrics across all cases/trials with SEM.

    Collects per-trial metric values from all cases.

    fp_rate per spec: BUG findings on clean-code cases / total
    clean-code cases. WARN findings on clean cases are expected
    reviewer behavior (design observations) and tracked separately
    as warn_rate (informational, no threshold gate).

    pass@1/pass@k per spec: % of expected findings caught on first
    trial / in any trial (across all cases).
    """
    precisions: list[float] = []
    recalls: list[float] = []
    severity_accs: list[float] = []
    category_accs: list[float] = []
    snrs: list[float] = []
    novel_counts: list[float] = []

    def _ingest_trial(trial: TrialResult) -> None:
        # Errored trials carry zero metrics that would otherwise poison
        # the mean/CI; treat them as missing data instead.
        if trial.error is not None:
            return
        m = trial.metrics
        precisions.append(m.precision)
        recalls.append(m.recall)
        severity_accs.append(m.severity_accuracy)
        category_accs.append(m.category_accuracy)
        snrs.append(m.snr)
        novel_counts.append(float(m.novel_count))

    for case in case_results:
        for trial in case.trials:
            _ingest_trial(trial)

        # Dual-metric fixed-version trials are independent observations:
        # they're graded against an empty expected set (fixed bundles are
        # clean by definition), and any BUG on them is a false positive
        # that must reduce precision/SNR (FR-015 / spec.md:90).
        if case.dual_metric_results is not None:
            for trial in case.dual_metric_results.fixed_results:
                _ingest_trial(trial)

    # Filter NaN values before computing CIs
    precisions_clean = _filter_nan(precisions)
    recalls_clean = _filter_nan(recalls)
    severity_accs_clean = _filter_nan(severity_accs)
    category_accs_clean = _filter_nan(category_accs)
    snrs_clean = _filter_nan(snrs)

    # --- fp_rate: BUG-only findings on clean-code trials ---
    fp_values = _collect_fp_values(case_results)

    # --- warn_rate: WARN findings on clean-code trials (informational) ---
    warn_values = _collect_warn_values(case_results)

    # warn_values fallback for mean computation
    if not warn_values:
        warn_values = [0.0]

    # --- pass@1 / pass@k: % of expected findings caught ---
    total_expected = sum(len(c.pass_at_1) for c in case_results)
    caught_at_1 = sum(
        sum(1 for v in c.pass_at_1.values() if v) for c in case_results
    )
    caught_at_k = sum(
        sum(1 for v in c.pass_at_k.values() if v) for c in case_results
    )
    pass_at_1_rate = caught_at_1 / total_expected if total_expected > 0 else 0.0
    pass_at_k_rate = caught_at_k / total_expected if total_expected > 0 else 0.0

    # Warn rate (informational, no threshold)
    warn_rate_mean = statistics.mean(warn_values) if warn_values else 0.0

    # F16: Novel findings reported as the SUM across the run, per FR-004.
    # Prior code used mean() which collapsed the signal when --trials > 1
    # (a case with 4 novel findings across 2 trials would read as 2, not 4).
    novel_count_total = int(sum(novel_counts))

    # Rebuttal accuracy
    rebuttal_accuracy = compute_rebuttal_accuracy(
        case_results, threshold=thresholds.get("rebuttal_accuracy", 0.75)
    )

    # --- Rate metrics via BCa bootstrap ---
    precision_ci = (
        bca_ci(precisions_clean, thresholds.get("precision", 0.70))
        if precisions_clean
        else metric_with_sem([0.0], thresholds.get("precision", 0.70))
    )
    recall_ci = (
        bca_ci(recalls_clean, thresholds.get("recall", 0.60))
        if recalls_clean
        else metric_with_sem([0.0], thresholds.get("recall", 0.60))
    )
    # Severity/category accuracy are only defined when at least one trial
    # produced a matched finding. With zero observations the previous
    # metric_with_sem([1.0], ...) fallback force-PASSed the threshold on
    # empty data; emit UNDEFINED (INCONCLUSIVE) instead so the operator
    # sees the gap and strict-mode CI fails.
    severity_accuracy_ci = (
        bca_ci(severity_accs_clean, thresholds.get("severity_accuracy", 0.80))
        if severity_accs_clean
        else MetricWithSEM(
            mean=0.0, sem=0.0, ci_lower=0.0, ci_upper=0.0,
            passes_threshold=False, method=CIMethod.UNDEFINED,
        )
    )
    category_accuracy_ci = (
        bca_ci(category_accs_clean, thresholds.get("category_accuracy", 0.70))
        if category_accs_clean
        else MetricWithSEM(
            mean=0.0, sem=0.0, ci_lower=0.0, ci_upper=0.0,
            passes_threshold=False, method=CIMethod.UNDEFINED,
        )
    )

    # --- fp_rate via Wilson CI ---
    if fp_values:
        fp_successes = sum(1 for v in fp_values if v == 1.0)
        fp_total = len(fp_values)
        fp_rate_ci = wilson_ci(
            fp_successes, fp_total, thresholds.get("fp_rate", 0.20), direction="lte"
        )
    else:
        # No clean cases — fp_rate is vacuously 0
        fp_rate_ci = MetricWithSEM(
            mean=0.0, sem=0.0, ci_lower=0.0, ci_upper=0.0,
            passes_threshold=True, method=CIMethod.VACUOUS,
        )

    # --- SNR via BCa bootstrap ---
    if snrs_clean:
        snr_ci = bca_ci(snrs_clean, thresholds.get("snr", 3.0))
    else:
        # All trials had zero noise — SNR undefined but favorable
        snr_ci = MetricWithSEM(
            mean=0.0, sem=0.0, ci_lower=0.0, ci_upper=0.0,
            passes_threshold=True, method=CIMethod.VACUOUS,
        )

    # --- Severity QWK ---
    all_severity_pairs: list[list[str]] = []
    for case in case_results:
        for trial in case.trials:
            all_severity_pairs.extend(trial.metrics.severity_pairs)

    # F15: cohen_kappa_score returns NaN when every pair falls in a
    # single class (e.g., two perfect BUG->BUG matches). NaN serializes
    # to JSON ``null`` which ``AggregateMetrics.model_validate_json``
    # rejects, breaking baseline round-trip. Detect the single-class
    # case up front and fall back to 0.0 — kappa is undefined there
    # (no variance), not "zero agreement". We use 0.0 rather than NaN
    # because the field is typed ``float`` in the artifact contract
    # and baselines must stay loadable.
    expected_labels = [p[0] for p in all_severity_pairs]
    actual_labels = [p[1] for p in all_severity_pairs]
    distinct_labels = set(expected_labels) | set(actual_labels)
    if len(all_severity_pairs) >= 2 and len(distinct_labels) >= 2:
        severity_qwk = float(cohen_kappa_score(
            expected_labels, actual_labels,
            weights='quadratic',
            labels=['NIT', 'WARN', 'BUG'],
        ))
        if math.isnan(severity_qwk):
            severity_qwk = 0.0
    else:
        severity_qwk = 0.0

    return AggregateMetrics(
        precision=precision_ci,
        recall=recall_ci,
        severity_accuracy=severity_accuracy_ci,
        category_accuracy=category_accuracy_ci,
        fp_rate=fp_rate_ci,
        warn_rate=warn_rate_mean,
        rebuttal_accuracy=rebuttal_accuracy,
        snr=snr_ci,
        severity_qwk=severity_qwk,
        novel_count=novel_count_total,
        pass_at_1_rate=pass_at_1_rate,
        pass_at_k_rate=pass_at_k_rate,
    )


def _collect_fp_values(case_results: list[CaseResult]) -> list[float]:
    """Collect per-case FP indicators from clean-code cases.

    Clean-code sources:
    1. Cases with no expected findings (``pass_at_1`` empty) — the case's
       trials collapse to one observation (1.0 if ANY trial flagged a BUG,
       else 0.0).
    2. Dual-metric fixed-version trials — collapsed per case the same way.

    WARN findings on clean code are expected reviewer behavior (design
    observations) and do not count as false positives.

    Spec (FR-004): ``BUG findings on clean code cases / total clean code
    cases``. Collapsing per-case prevents ``--trials=N`` from diluting a
    single false-positive hallucination into 1/N.
    """
    fp_values: list[float] = []

    for case in case_results:
        is_clean = not case.pass_at_1  # empty dict = no expected findings
        if is_clean:
            observation = _any_trial_has_bug(case.trials)
            if observation is not None:
                fp_values.append(observation)

        # Dual-metric fixed-version side is a distinct clean observation.
        if case.dual_metric_results is not None:
            fixed = case.dual_metric_results.fixed_results
            observation = _any_trial_has_bug(fixed)
            if observation is not None:
                fp_values.append(observation)

    return fp_values


def _any_trial_has_bug(trials: list[TrialResult]) -> float | None:
    """Return 1.0 if any non-errored trial has a BUG finding, else 0.0.

    Returns None when every trial errored (no usable observation).
    """
    saw_usable = False
    for trial in trials:
        if trial.error is not None:
            continue
        saw_usable = True
        if _trial_has_bug(trial.findings) == 1.0:
            return 1.0
    return 0.0 if saw_usable else None


def _collect_warn_values(case_results: list[CaseResult]) -> list[float]:
    """Collect per-case WARN indicators from clean-code cases.

    Mirrors _collect_fp_values: WARN observations collapse per case via OR
    across trials, so WARN rate is not diluted by trial count.
    """
    warn_values: list[float] = []

    for case in case_results:
        is_clean = not case.pass_at_1
        if is_clean:
            observation = _any_trial_has_warn(case.trials)
            if observation is not None:
                warn_values.append(observation)

        if case.dual_metric_results is not None:
            fixed = case.dual_metric_results.fixed_results
            observation = _any_trial_has_warn(fixed)
            if observation is not None:
                warn_values.append(observation)

    return warn_values


def _any_trial_has_warn(trials: list[TrialResult]) -> float | None:
    """Return 1.0 if any non-errored trial has a WARN finding, else 0.0.

    Returns None when every trial errored.
    """
    saw_usable = False
    for trial in trials:
        if trial.error is not None:
            continue
        saw_usable = True
        if _trial_has_warn(trial.findings) == 1.0:
            return 1.0
    return 0.0 if saw_usable else None


def _trial_has_bug(findings: list[Finding]) -> float:
    """Return 1.0 if any finding has BUG severity, else 0.0."""
    for f in findings:
        if f.severity == Severity.BUG:
            return 1.0
    return 0.0


def _trial_has_warn(findings: list[Finding]) -> float:
    """Return 1.0 if any finding has WARN severity, else 0.0."""
    for f in findings:
        if f.severity == Severity.WARN:
            return 1.0
    return 0.0


def compute_rebuttal_accuracy(
    case_results: list[CaseResult],
    threshold: float = 0.75,
) -> MetricWithSEM | None:
    """Compute rebuttal accuracy from multi-turn case results.

    Returns None if no multi-turn cases exist. Uses Wilson CI for
    threshold gating.

    Small-sample handling: when even a perfect score (n/n) at the current
    sample size cannot produce ci_lower >= threshold, the metric is tagged
    ``CIMethod.WILSON_INSUFFICIENT_N``. ``passes_threshold`` reflects the
    natural Wilson CI result (typically False at small n) — the scorecard
    renders the metric as INCONCLUSIVE instead of PASS/FAIL, and
    ``check_thresholds`` treats it as non-fatal unless ``strict=True``.
    This keeps the scorecard honest (inconclusive is never silently PASS)
    without blocking releases on corpus maturity.
    """
    total = 0
    correct = 0

    for case in case_results:
        if case.rebuttal_results is None or len(case.rebuttal_results) == 0:
            continue
        for r in case.rebuttal_results:
            total += 1
            if r.correct and not r.finding_not_found:
                correct += 1

    if total == 0:
        return None

    result = wilson_ci(correct, total, threshold=threshold)

    # Detect insufficient-n by testing whether a perfect score at this n
    # would clear the threshold. If not, tag method but do NOT override
    # passes_threshold — consumers (check_thresholds, reporter) branch
    # on the method tag to render/gate correctly.
    perfect = wilson_ci(total, total, threshold=threshold)
    if not perfect.passes_threshold:
        return MetricWithSEM(
            mean=result.mean,
            sem=result.sem,
            ci_lower=result.ci_lower,
            ci_upper=result.ci_upper,
            passes_threshold=result.passes_threshold,
            method=CIMethod.WILSON_INSUFFICIENT_N,
        )

    return result


_METRIC_DIRECTIONS: dict[str, str] = {
    "precision": "gte",
    "recall": "gte",
    "severity_accuracy": "gte",
    "category_accuracy": "gte",
    "fp_rate": "lte",
    "snr": "gte",
    "rebuttal_accuracy": "gte",
}


def _metric_passes_against(
    metric: MetricWithSEM,
    threshold: float,
    direction: str,
) -> bool:
    """Recompute pass/fail from CI bounds and a caller-supplied threshold.

    Mirrors the logic in ``metric_with_sem`` / ``wilson_ci`` but operates
    on the already-built MetricWithSEM, so callers that thread a custom
    threshold into ``check_thresholds`` don't depend on the flag baked in
    at aggregation time.
    """
    if direction == "lte":
        return metric.ci_upper <= threshold
    return metric.ci_lower >= threshold


def check_thresholds(
    aggregate: AggregateMetrics,
    thresholds: dict[str, float],
    strict: bool = False,
) -> bool:
    """Check if all metrics meet their thresholds. Returns True if all pass.

    For each metric the check re-derives pass/fail from the MetricWithSEM
    confidence interval and the ``thresholds`` mapping passed in here —
    trusting ``m.passes_threshold`` would silently honor whatever bar was
    baked in when ``aggregate_metrics`` ran, which may not match what the
    caller requested. Missing keys fall back to the metric's own
    ``passes_threshold`` flag so aggregates without a configured bar are
    not treated as failures.

    Metrics tagged ``CIMethod.WILSON_INSUFFICIENT_N`` or
    ``CIMethod.UNDEFINED`` are inconclusive — either the sample is too
    small for a Wilson CI to clear the threshold even at a perfect score,
    or the metric has no observations at all (e.g., severity accuracy
    when no finding was matched). Non-strict mode (default) treats
    inconclusive as non-fatal (pass-through) so small-corpus runs are
    not gated on sample size. ``--strict`` mode treats inconclusive as
    a fail (useful for CI once the corpus matures).
    """
    named_metrics: list[tuple[str, MetricWithSEM]] = [
        ("precision", aggregate.precision),
        ("recall", aggregate.recall),
        ("severity_accuracy", aggregate.severity_accuracy),
        ("category_accuracy", aggregate.category_accuracy),
        ("fp_rate", aggregate.fp_rate),
        ("snr", aggregate.snr),
    ]

    if aggregate.rebuttal_accuracy is not None:
        named_metrics.append(("rebuttal_accuracy", aggregate.rebuttal_accuracy))

    for name, m in named_metrics:
        if m.method in (CIMethod.WILSON_INSUFFICIENT_N, CIMethod.UNDEFINED):
            if strict:
                return False
            continue
        # CIMethod.VACUOUS = structurally empty but favorable (e.g. no clean
        # cases → fp_rate trivially safe, zero noise → SNR trivially high).
        # Re-deriving from the [0, 0] CI would wrongly FAIL a gte threshold
        # like snr >= 3.0, so trust the aggregator's verdict.
        if m.method == CIMethod.VACUOUS:
            if not m.passes_threshold:
                return False
            continue
        if name in thresholds:
            direction = _METRIC_DIRECTIONS.get(name, "gte")
            if not _metric_passes_against(m, thresholds[name], direction):
                return False
        elif not m.passes_threshold:
            return False
    return True
