"""Runner -- case x trial orchestration for the eval harness.

Orchestrates the full loop:
  For each golden case, run N trials of start_review -> grade -> score,
  optionally with multi-turn discuss and dual-metric flows.

Returns a complete EvalRun with aggregate metrics and pass/fail.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from eval.graders import DEFAULT_GRADER_MODEL
from eval.graders.pipeline import grade_all_findings
from eval.mcp_client import (
    MCPAbortError,
    MCPSkipCaseError,
    call_discuss,
    call_get_review_summary,
    call_start_review,
)
from eval.models import (
    CaseResult,
    DualMetricResult,
    EvalRun,
    ExpectedFinding,
    GoldenCase,
    GraderResult,
    GraderVerdict,
    RebuttalResult,
    ReviewBundle,
    TrialMetrics,
    TrialResult,
)
from eval.scorer import (
    aggregate_metrics,
    check_thresholds,
    compute_trial_metrics,
)
from server.models import Finding, FindingStatus

if TYPE_CHECKING:
    from mcp.client.session import ClientSession


logger = logging.getLogger(__name__)


DEFAULT_THRESHOLDS: dict[str, float] = {
    "precision": 0.70,
    "recall": 0.60,
    "severity_accuracy": 0.80,
    "category_accuracy": 0.70,
    "fp_rate": 0.20,
    "rebuttal_accuracy": 0.75,
    "snr": 3.0,
}


def resolve_finding_id(
    grader_results: list[GraderResult],
    target_expected_id: str,
) -> str | None:
    """Resolve a stable target_expected_id to the actual finding_id.

    Looks through grader_results for any match/partial_match with
    matched_expected_id == target_expected_id. Returns the actual_finding_id.
    Returns None if the expected finding was not matched.
    """
    for gr in grader_results:
        if (
            gr.verdict in (GraderVerdict.MATCH, GraderVerdict.PARTIAL_MATCH)
            and gr.matched_expected_id == target_expected_id
        ):
            return gr.actual_finding_id
    return None


def _parse_findings(review_result: dict) -> list[Finding]:
    """Parse Finding objects from MCP start_review response dict."""
    raw_findings = review_result.get("findings", [])
    return [Finding(**f) for f in raw_findings]


def _compute_pass_at_1(
    trials: list[TrialResult],
    expected_ids: list[str],
) -> dict[str, bool]:
    """For each expected finding, check if matched in trial 1."""
    if not trials:
        return {eid: False for eid in expected_ids}

    trial_1 = trials[0]
    matched_in_trial_1: set[str] = set()
    for gr in trial_1.graded:
        if (
            gr.verdict in (GraderVerdict.MATCH, GraderVerdict.PARTIAL_MATCH)
            and gr.matched_expected_id is not None
        ):
            matched_in_trial_1.add(gr.matched_expected_id)

    return {eid: eid in matched_in_trial_1 for eid in expected_ids}


def _compute_pass_at_k(
    trials: list[TrialResult],
    expected_ids: list[str],
) -> dict[str, bool]:
    """For each expected finding, check if matched in ANY trial."""
    matched_any: set[str] = set()
    for trial in trials:
        for gr in trial.graded:
            if (
                gr.verdict in (GraderVerdict.MATCH, GraderVerdict.PARTIAL_MATCH)
                and gr.matched_expected_id is not None
            ):
                matched_any.add(gr.matched_expected_id)

    return {eid: eid in matched_any for eid in expected_ids}


def _check_grading_error_rate(graded: list[GraderResult]) -> str | None:
    """If >50% of findings have grading_error verdict, return error message."""
    if not graded:
        return None

    error_count = sum(
        1 for g in graded if g.verdict == GraderVerdict.GRADING_ERROR
    )
    if error_count / len(graded) > 0.5:
        return (
            f"Grading error rate too high: {error_count}/{len(graded)} "
            f"findings had grading_error verdict"
        )
    return None


def _log(verbose: bool, message: str) -> None:
    """Print progress message to stderr if verbose mode is enabled."""
    if verbose:
        print(message, file=sys.stderr)


async def _run_multi_turn(
    session: ClientSession,
    case: GoldenCase,
    session_id: str,
    grader_results: list[GraderResult],
    verbose: bool = False,
) -> list[RebuttalResult]:
    """Execute multi-turn discuss flow and collect rebuttal results.

    For each TurnScript (in turn-order):
    1. Resolve target_expected_id to actual finding_id via grader results
    2. If not found: record RebuttalResult(finding_not_found=True)
    3. Otherwise: format message, call discuss, call get_review_summary
       to capture the per-turn status snapshot, compare to
       ``expected_status_after``.

    The summary call MUST happen after each rebuttal rather than once at
    the end (FR-007 / spec.md:38-50): rebuttals can evolve or reverse a
    finding's status across turns, and a single final snapshot would
    misjudge earlier turns against the final state.
    """
    if case.multi_turn_script is None:
        return []

    rebuttal_results: list[RebuttalResult] = []

    for turn in sorted(case.multi_turn_script, key=lambda t: t.turn_number):
        resolved_id = resolve_finding_id(
            grader_results, turn.target_expected_id
        )

        if resolved_id is None:
            _log(
                verbose,
                f"  Turn {turn.turn_number}: target "
                f"{turn.target_expected_id} not found, skipping discuss",
            )
            rebuttal_results.append(
                RebuttalResult(
                    turn_number=turn.turn_number,
                    target_expected_id=turn.target_expected_id,
                    actual_finding_id=None,
                    expected_status=turn.expected_status_after,
                    actual_status=None,
                    correct=False,
                    finding_not_found=True,
                )
            )
            continue

        # Format and send the rebuttal message, then snapshot status.
        message = turn.rebuttal_message_template.format(finding_id=resolved_id)
        _log(verbose, f"  Turn {turn.turn_number}: discussing finding {resolved_id}")
        await call_discuss(session, session_id, message)

        summary = await call_get_review_summary(session, session_id)
        status_by_id: dict[str, FindingStatus] = {}
        for f_dict in summary.get("findings", []):
            fid = f_dict.get("finding_id")
            fstatus = f_dict.get("status")
            if fid and fstatus:
                status_by_id[fid] = FindingStatus(fstatus)

        actual_status = status_by_id.get(resolved_id)
        correct = actual_status == turn.expected_status_after

        rebuttal_results.append(
            RebuttalResult(
                turn_number=turn.turn_number,
                target_expected_id=turn.target_expected_id,
                actual_finding_id=resolved_id,
                expected_status=turn.expected_status_after,
                actual_status=actual_status,
                correct=correct,
                finding_not_found=False,
            )
        )

    return rebuttal_results


async def _run_single_trial(
    case: GoldenCase,
    session: ClientSession,
    trial_number: int,
    grader_model: str,
    line_tolerance: int,
    prompt_template: str | None,
    rubric: str | None,
    few_shot_examples: list[dict] | None,
    max_retries: int,
    verbose: bool,
    bundle_override: ReviewBundle | None = None,
) -> tuple[TrialResult, str | None]:
    """Run a single trial for a case: start_review -> grade -> score.

    Args:
        bundle_override: If provided, use this bundle instead of case.bundle.
            Used for dual-metric fixed-version trials.

    Returns (TrialResult, model_name_or_None).
    """
    bundle = bundle_override or case.bundle
    _log(verbose, f"  Trial {trial_number}: calling start_review...")

    try:
        review_result = await call_start_review(
            session, bundle, case.case_id,
            max_retries=max_retries,
        )
    except (MCPAbortError, MCPSkipCaseError):
        raise
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(
            "Case %s trial %d: MCP error (%s): %s",
            case.case_id, trial_number, type(exc).__name__, exc,
        )
        return (
            TrialResult(
                trial_number=trial_number,
                findings=[],
                graded=[],
                metrics=TrialMetrics(
                    precision=0.0,
                    recall=0.0,
                    severity_accuracy=0.0,
                    category_accuracy=0.0,
                    snr=0.0,
                    novel_count=0,
                    grading_error_count=0,
                    finding_count=0,
                ),
                error=str(exc),
            ),
            None,
        )

    model_name = review_result.get("model")
    findings = _parse_findings(review_result)
    _log(verbose, f"  Trial {trial_number}: {len(findings)} findings, grading...")

    # Dual-metric fixed bundles are clean by definition (the fix has landed);
    # any finding on them must be treated as a false positive candidate.
    # Grading them against the vulnerable-version expected set would let
    # correct silence score as recall 0 or, worse, let a hallucination
    # coincidentally match an expected ID (FR-015 / spec.md:90).
    expected_for_trial: list[ExpectedFinding] = (
        [] if bundle_override is not None else case.expected_findings
    )

    graded = await grade_all_findings(
        findings=findings,
        expected_findings=expected_for_trial,
        case_description=case.description,
        grader_model=grader_model,
        line_tolerance=line_tolerance,
        prompt_template=prompt_template,
        rubric=rubric,
        few_shot_examples=few_shot_examples,
        max_retries=max_retries,
    )

    metrics = compute_trial_metrics(graded, expected_for_trial, findings)
    error_msg = _check_grading_error_rate(graded)

    return (
        TrialResult(
            trial_number=trial_number,
            findings=findings,
            graded=graded,
            metrics=metrics,
            error=error_msg,
        ),
        model_name,
    )


async def _run_single_case(
    case: GoldenCase,
    session: ClientSession,
    semaphore: asyncio.Semaphore,
    num_trials: int,
    grader_model: str,
    line_tolerance: int,
    prompt_template: str | None,
    rubric: str | None,
    few_shot_examples: list[dict] | None,
    max_retries: int,
    verbose: bool,
) -> tuple[CaseResult, str | None] | None:
    """Run all trials for a single case, guarded by *semaphore*.

    Returns ``(CaseResult, model_name_or_None)`` on success, ``None`` when
    the case is skipped (``MCPSkipCaseError``).  ``MCPAbortError`` is left
    to propagate so that ``asyncio.gather(return_exceptions=True)`` captures
    it for the caller.
    """
    async with semaphore:
        _log(verbose, f"Case {case.case_id}: starting {num_trials} trial(s)...")

        try:
            trials: list[TrialResult] = []
            case_model_name: str | None = None
            for trial_num in range(1, num_trials + 1):
                trial, trial_model = await _run_single_trial(
                    case=case,
                    session=session,
                    trial_number=trial_num,
                    grader_model=grader_model,
                    line_tolerance=line_tolerance,
                    prompt_template=prompt_template,
                    rubric=rubric,
                    few_shot_examples=few_shot_examples,
                    max_retries=max_retries,
                    verbose=verbose,
                )
                trials.append(trial)

                # Capture model name from first successful response
                if case_model_name is None and trial_model is not None:
                    case_model_name = trial_model

            # Compute pass@1 and pass@k
            expected_ids = [ef.expected_id for ef in case.expected_findings]
            pass_at_1 = _compute_pass_at_1(trials, expected_ids)
            pass_at_k = _compute_pass_at_k(trials, expected_ids)

            # Multi-turn rebuttal (uses a fresh start_review for session_id).
            # Only requires that at least one trial succeeded; the multi-turn
            # flow starts its own review session, so first-trial transients
            # must not skip rebuttal grading.
            #
            # F13: exceptions from start_review / grade_all_findings /
            # _run_multi_turn are NOT swallowed. Silently dropping them
            # erases rebuttal accuracy while leaving pass_fail=True; the
            # run_eval-level handler (see line ~530) propagates the
            # exception so the whole run fails loudly instead of hiding
            # a broken User Story 2 path. MCPAbortError / MCPSkipCaseError
            # / CancelledError already propagate naturally.
            rebuttal_results = None
            any_trial_succeeded = any(t.error is None for t in trials)
            if case.multi_turn_script and any_trial_succeeded:
                review_result = await call_start_review(
                    session, case.bundle, case.case_id,
                    max_retries=max_retries,
                )
                mt_session_id = review_result.get("session_id", "")
                mt_findings = _parse_findings(review_result)

                mt_graded = await grade_all_findings(
                    findings=mt_findings,
                    expected_findings=case.expected_findings,
                    case_description=case.description,
                    grader_model=grader_model,
                    line_tolerance=line_tolerance,
                    prompt_template=prompt_template,
                    rubric=rubric,
                    few_shot_examples=few_shot_examples,
                    max_retries=max_retries,
                )

                rebuttal_results = await _run_multi_turn(
                    session=session,
                    case=case,
                    session_id=mt_session_id,
                    grader_results=mt_graded,
                    verbose=verbose,
                )

            # Dual-metric: run fixed-version trials
            dual_metric_results = None
            if (
                case.dual_metric is not None
                and case.dual_metric.fixed_bundle is not None
            ):
                _log(verbose, f"Case {case.case_id}: running {num_trials} fixed-version trial(s)...")
                fixed_trials: list[TrialResult] = []
                for trial_num in range(1, num_trials + 1):
                    fixed_trial, _ = await _run_single_trial(
                        case=case,
                        session=session,
                        trial_number=trial_num,
                        grader_model=grader_model,
                        line_tolerance=line_tolerance,
                        prompt_template=prompt_template,
                        rubric=rubric,
                        few_shot_examples=few_shot_examples,
                        max_retries=max_retries,
                        verbose=verbose,
                        bundle_override=case.dual_metric.fixed_bundle,
                    )
                    fixed_trials.append(fixed_trial)

                dual_metric_results = DualMetricResult(
                    vulnerable_results=list(trials),
                    fixed_results=fixed_trials,
                )

            return (
                CaseResult(
                    case_id=case.case_id,
                    trials=trials,
                    pass_at_1=pass_at_1,
                    pass_at_k=pass_at_k,
                    rebuttal_results=rebuttal_results,
                    dual_metric_results=dual_metric_results,
                ),
                case_model_name,
            )
        except MCPSkipCaseError as exc:
            _log(verbose, f"Case {case.case_id}: skipped ({exc})")
            return None


async def run_eval(
    cases: list[GoldenCase],
    session: ClientSession,
    grader_model: str = DEFAULT_GRADER_MODEL,
    num_trials: int = 3,
    line_tolerance: int = 5,
    thresholds: dict[str, float] | None = None,
    prompt_template: str | None = None,
    rubric: str | None = None,
    few_shot_examples: list[dict] | None = None,
    max_retries: int = 3,
    grader_prompt_version: str = "unknown",
    verbose: bool = False,
    concurrency: int = 5,
) -> EvalRun:
    """Run the complete eval harness.

    For each case x trial:
    1. Call start_review via MCP -> get findings
    2. Grade all findings via pipeline -> get GraderResults
    3. If multi-turn: resolve finding IDs, run discuss turns, record rebuttal results
    4. Compute trial metrics
    5. Aggregate across trials -> CaseResult with pass@1/pass@k

    Cases are executed concurrently (up to *concurrency* at a time).
    Trials within each case remain sequential.

    Returns a complete EvalRun with aggregate metrics and pass/fail.
    """
    effective_thresholds = thresholds if thresholds is not None else DEFAULT_THRESHOLDS
    start_time = time.monotonic()
    run_id = str(uuid.uuid4())

    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        _run_single_case(
            case=case,
            session=session,
            semaphore=semaphore,
            num_trials=num_trials,
            grader_model=grader_model,
            line_tolerance=line_tolerance,
            prompt_template=prompt_template,
            rubric=rubric,
            few_shot_examples=few_shot_examples,
            max_retries=max_retries,
            verbose=verbose,
        )
        for case in cases
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    case_results: list[CaseResult] = []
    model_evaluated = "unknown"
    for case, result in zip(cases, results):
        if isinstance(result, MCPAbortError):
            raise result  # propagate abort
        if isinstance(result, Exception):
            # Any exception that escaped _run_single_case (grader crash,
            # multi-turn failure, dual-metric crash, etc.) indicates a harness
            # bug or infrastructure failure. Swallowing here would silently
            # drop the case and produce a misleading PASS on the remaining
            # cases — fail the whole run so the operator sees the error.
            logger.error(
                "Case %s failed with %s: %s",
                case.case_id, type(result).__name__, result,
                exc_info=result,
            )
            raise result
        if result is not None:
            case_result, model_name = result
            case_results.append(case_result)
            if model_evaluated == "unknown" and model_name is not None:
                model_evaluated = model_name

    # Aggregate metrics
    agg = aggregate_metrics(case_results, effective_thresholds)
    pass_fail = check_thresholds(agg, effective_thresholds)

    duration = time.monotonic() - start_time

    return EvalRun(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc),
        model_evaluated=model_evaluated,
        grader_model=grader_model,
        grader_prompt_version=grader_prompt_version,
        num_trials=num_trials,
        line_tolerance=line_tolerance,
        cases=case_results,
        aggregate=agg,
        pass_fail=pass_fail,
        duration_seconds=duration,
    )
