"""RED tests for the eval runner -- case x trial orchestration (T010).

All MCP interactions and grading pipeline calls are mocked.
Real scorer functions are used (they are deterministic pure computation).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from eval.models import (
    CaseResult,
    DualMetricConfig,
    DualMetricResult,
    EvalRun,
    ExpectedFinding,
    FindingStatus,
    GoldenCase,
    GoldenCaseSource,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
    RebuttalResult,
    TrialResult,
    TurnScript,
)
from server.models import (
    Category,
    Finding,
    Location,
    ReviewBundle,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    *,
    finding_id: str = "F-001",
    rule_id: str = "sql-injection",
    severity: Severity = Severity.BUG,
    category: Category = Category.SECURITY,
    file: str = "src/main.py",
    start_line: int = 10,
    end_line: int = 15,
    status: FindingStatus = FindingStatus.OPEN,
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
        status=status,
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


def _make_grader_result(
    *,
    verdict: GraderVerdict = GraderVerdict.MATCH,
    matched_expected_id: str | None = "EF-001",
    actual_finding_id: str = "F-001",
    tier: int = 1,
    confidence: GraderConfidence = GraderConfidence.HIGH,
) -> GraderResult:
    return GraderResult(
        tier=tier,
        verdict=verdict,
        confidence=confidence,
        matched_expected_id=matched_expected_id,
        actual_finding_id=actual_finding_id,
    )


def _make_golden_case(
    *,
    case_id: str = "case-001",
    expected_findings: list[ExpectedFinding] | None = None,
    multi_turn_script: list[TurnScript] | None = None,
) -> GoldenCase:
    return GoldenCase(
        case_id=case_id,
        description="SQL injection in query builder",
        source=GoldenCaseSource.HAND_CURATED,
        tags=["security", "python"],
        bundle=ReviewBundle(
            diff="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new",
            files={"main.py": "print('hello')"},
        ),
        expected_findings=expected_findings or [_make_expected()],
        multi_turn_script=multi_turn_script,
    )


def _make_mcp_review_response(
    *,
    session_id: str = "sess-001",
    findings: list[dict] | None = None,
) -> dict:
    """Build a dict matching what call_start_review returns."""
    if findings is None:
        f = _make_finding()
        findings = [f.model_dump(mode="json")]
    return {
        "session_id": session_id,
        "model": "copilot-gpt-4",
        "findings": findings,
        "finding_count": len(findings),
        "severity_summary": {"BUG": len(findings)},
    }


def _make_mcp_summary_response(
    *,
    session_id: str = "sess-001",
    findings: list[dict] | None = None,
) -> dict:
    """Build a dict matching what call_get_review_summary returns."""
    if findings is None:
        findings = []
    return {
        "session_id": session_id,
        "status": "completed",
        "model": "copilot-gpt-4",
        "round_count": 2,
        "findings": findings,
        "finding_count": len(findings),
        "by_severity": {},
        "by_category": {},
        "by_status": {},
    }


def _default_thresholds() -> dict[str, float]:
    return {
        "precision": 0.70,
        "recall": 0.60,
        "severity_accuracy": 0.80,
        "category_accuracy": 0.70,
        "fp_rate": 0.20,
        "rebuttal_accuracy": 0.75,
        "snr": 3.0,
    }


# ===========================================================================
# TestResolveFindingId
# ===========================================================================


class TestResolveFindingId:
    """resolve_finding_id maps target_expected_id to actual finding_id."""

    def test_match_found(self) -> None:
        from eval.runner import resolve_finding_id

        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-002",
            ),
        ]
        result = resolve_finding_id(grader_results, "EF-001")
        assert result == "F-001"

    def test_partial_match_found(self) -> None:
        from eval.runner import resolve_finding_id

        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.PARTIAL_MATCH,
                matched_expected_id="EF-002",
                actual_finding_id="F-005",
            ),
        ]
        result = resolve_finding_id(grader_results, "EF-002")
        assert result == "F-005"

    def test_not_found_returns_none(self) -> None:
        from eval.runner import resolve_finding_id

        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-001",
            ),
        ]
        result = resolve_finding_id(grader_results, "EF-999")
        assert result is None

    def test_multiple_matches_picks_first(self) -> None:
        from eval.runner import resolve_finding_id

        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-AAA",
            ),
            _make_grader_result(
                verdict=GraderVerdict.PARTIAL_MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-BBB",
            ),
        ]
        result = resolve_finding_id(grader_results, "EF-001")
        assert result == "F-AAA"

    def test_empty_results_returns_none(self) -> None:
        from eval.runner import resolve_finding_id

        result = resolve_finding_id([], "EF-001")
        assert result is None


# ===========================================================================
# TestSingleTurnRunEval
# ===========================================================================


class TestSingleTurnRunEval:
    """Single-turn flow: start_review -> grade -> score -> CaseResult."""

    async def test_single_case_single_trial_produces_case_result(self) -> None:
        from eval.runner import run_eval

        case = _make_golden_case()
        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        assert isinstance(result, EvalRun)
        assert len(result.cases) == 1
        case_result = result.cases[0]
        assert case_result.case_id == "case-001"
        assert len(case_result.trials) == 1
        assert case_result.trials[0].trial_number == 1
        assert case_result.trials[0].metrics.recall == 1.0
        assert case_result.trials[0].metrics.precision == 1.0

    async def test_multiple_trials_per_case(self) -> None:
        from eval.runner import run_eval

        case = _make_golden_case()
        f1 = _make_finding(finding_id="F-001")
        f2 = _make_finding(finding_id="F-002")
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-002",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[
                    f1.model_dump(mode="json"),
                    f2.model_dump(mode="json"),
                ]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=3,
                thresholds=_default_thresholds(),
            )

        assert len(result.cases[0].trials) == 3
        for i, trial in enumerate(result.cases[0].trials):
            assert trial.trial_number == i + 1

        # MCP and grading should have been called 3 times
        assert mock_start_review.call_count == 3
        assert mock_grade.call_count == 3


# ===========================================================================
# TestPassAtComputation
# ===========================================================================


class TestPassAtComputation:
    """pass@1 and pass@k computation across trials."""

    async def test_pass_at_1_all_match_in_trial_1(self) -> None:
        """When trial 1 matches all expected findings, pass@1 is all True."""
        from eval.runner import run_eval

        case = _make_golden_case()
        f1 = _make_finding(finding_id="F-001")
        f2 = _make_finding(finding_id="F-002")
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-002",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[
                    f1.model_dump(mode="json"),
                    f2.model_dump(mode="json"),
                ]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=2,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.pass_at_1 == {"EF-001": True}
        assert case_result.pass_at_k == {"EF-001": True}

    async def test_pass_at_1_miss_pass_at_k_hit(self) -> None:
        """Trial 1 misses a finding, but trial 2 finds it -> pass@k True, pass@1 False."""
        from eval.runner import run_eval

        case = _make_golden_case()
        f1 = _make_finding(finding_id="F-001")
        f2 = _make_finding(finding_id="F-002")

        # Trial 1: no match for EF-001, plus a novel finding
        grader_results_miss = [
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-001",
            ),
            _make_grader_result(
                verdict=GraderVerdict.NOVEL_VALID,
                matched_expected_id=None,
                actual_finding_id="F-002",
            ),
        ]
        # Trial 2: match for EF-001, plus a no_match
        grader_results_hit = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-002",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[
                    f1.model_dump(mode="json"),
                    f2.model_dump(mode="json"),
                ]
            )
        )
        mock_grade = AsyncMock(side_effect=[grader_results_miss, grader_results_hit])

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=2,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.pass_at_1 == {"EF-001": False}
        assert case_result.pass_at_k == {"EF-001": True}


# ===========================================================================
# TestErroredTrialHandling
# ===========================================================================


class TestErroredTrialHandling:
    """When >50% of findings have grading_error, trial.error is set."""

    async def test_majority_grading_error_sets_trial_error(self) -> None:
        from eval.runner import run_eval

        case = _make_golden_case()
        f1 = _make_finding(finding_id="F-001")
        f2 = _make_finding(finding_id="F-002")

        # Both findings get grading_error -> 100% error rate
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.GRADING_ERROR,
                matched_expected_id=None,
                actual_finding_id="F-001",
            ),
            _make_grader_result(
                verdict=GraderVerdict.GRADING_ERROR,
                matched_expected_id=None,
                actual_finding_id="F-002",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[
                    f1.model_dump(mode="json"),
                    f2.model_dump(mode="json"),
                ]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        trial = result.cases[0].trials[0]
        assert trial.error is not None
        assert "grading_error" in trial.error.lower() or "grading" in trial.error.lower()

    async def test_minority_grading_error_no_trial_error(self) -> None:
        from eval.runner import run_eval

        case = _make_golden_case()
        f1 = _make_finding(finding_id="F-001")
        f2 = _make_finding(finding_id="F-002")
        f3 = _make_finding(finding_id="F-003")

        # 1 out of 3 is grading_error -> 33%, below 50%
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-002",
            ),
            _make_grader_result(
                verdict=GraderVerdict.GRADING_ERROR,
                matched_expected_id=None,
                actual_finding_id="F-003",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[
                    f1.model_dump(mode="json"),
                    f2.model_dump(mode="json"),
                    f3.model_dump(mode="json"),
                ]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        trial = result.cases[0].trials[0]
        assert trial.error is None

    async def test_mcp_call_failure_records_trial_error(self) -> None:
        """MCP call failure is caught and recorded as trial error."""
        from eval.runner import run_eval

        case = _make_golden_case()

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(side_effect=RuntimeError("Connection refused"))

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", AsyncMock()),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        trial = result.cases[0].trials[0]
        assert trial.error is not None
        assert "Connection refused" in trial.error


# ===========================================================================
# TestMultiTurnFlow
# ===========================================================================


class TestMultiTurnFlow:
    """Multi-turn: resolve finding ID, discuss, check rebuttal results."""

    async def test_multi_turn_resolves_and_discusses(self) -> None:
        from eval.runner import run_eval

        script = [
            TurnScript(
                turn_number=1,
                rebuttal_message_template="I disagree with finding {finding_id} because it is a false positive.",
                target_expected_id="EF-001",
                expected_status_after=FindingStatus.DISMISSED,
                is_valid_rebuttal=True,
            ),
        ]
        case = _make_golden_case(multi_turn_script=script)

        finding = _make_finding(finding_id="F-001")
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        # After discuss, the finding should be dismissed
        dismissed_finding = _make_finding(
            finding_id="F-001", status=FindingStatus.DISMISSED
        )
        summary_response = _make_mcp_summary_response(
            findings=[dismissed_finding.model_dump(mode="json")]
        )

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_discuss = AsyncMock(return_value={
            "response": "Finding dismissed.",
            "updated_findings": [dismissed_finding.model_dump(mode="json")],
            "finding_count_by_status": {"dismissed": 1},
        })
        mock_summary = AsyncMock(return_value=summary_response)
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.call_discuss", mock_discuss),
            patch("eval.runner.call_get_review_summary", mock_summary),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.rebuttal_results is not None
        assert len(case_result.rebuttal_results) == 1

        rebuttal = case_result.rebuttal_results[0]
        assert rebuttal.turn_number == 1
        assert rebuttal.target_expected_id == "EF-001"
        assert rebuttal.actual_finding_id == "F-001"
        assert rebuttal.expected_status == FindingStatus.DISMISSED
        assert rebuttal.actual_status == FindingStatus.DISMISSED
        assert rebuttal.correct is True
        assert rebuttal.finding_not_found is False

        # Verify discuss was called with the formatted message
        mock_discuss.assert_called_once()
        call_args = mock_discuss.call_args
        # The message should have {finding_id} replaced
        assert "F-001" in call_args[0][2] or "F-001" in call_args[1].get("message", "")

    async def test_multi_turn_status_checked_after_each_turn(self) -> None:
        """Per-turn status snapshot — F12 regression guard.

        Turn 1 dismisses F-001 correctly; Turn 2 reopens it (simulating a
        rebuttal to the rebuttal). A single final snapshot would judge both
        turns against the reopened state and wrongly score turn 1 as
        incorrect. Per FR-007 / spec.md:38-50 the harness must compare
        ``expected_status_after`` against the status **right after that
        turn**, which requires calling ``get_review_summary`` between turns.
        """
        from eval.runner import run_eval

        script = [
            TurnScript(
                turn_number=1,
                rebuttal_message_template="Finding {finding_id} is false.",
                target_expected_id="EF-001",
                expected_status_after=FindingStatus.DISMISSED,
                is_valid_rebuttal=True,
            ),
            TurnScript(
                turn_number=2,
                rebuttal_message_template="Actually reopen {finding_id}.",
                target_expected_id="EF-001",
                expected_status_after=FindingStatus.OPEN,
                is_valid_rebuttal=False,
            ),
        ]
        case = _make_golden_case(multi_turn_script=script)

        finding_open = _make_finding(finding_id="F-001", status=FindingStatus.OPEN)
        finding_dismissed = _make_finding(
            finding_id="F-001", status=FindingStatus.DISMISSED
        )
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding_open.model_dump(mode="json")]
            )
        )
        mock_discuss = AsyncMock(return_value={"response": "ok"})

        # Two summaries, one after each turn: first DISMISSED, then OPEN.
        summary_after_turn_1 = _make_mcp_summary_response(
            findings=[finding_dismissed.model_dump(mode="json")]
        )
        summary_after_turn_2 = _make_mcp_summary_response(
            findings=[finding_open.model_dump(mode="json")]
        )
        mock_summary = AsyncMock(
            side_effect=[summary_after_turn_1, summary_after_turn_2]
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.call_discuss", mock_discuss),
            patch("eval.runner.call_get_review_summary", mock_summary),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.rebuttal_results is not None
        assert len(case_result.rebuttal_results) == 2

        turn1 = next(r for r in case_result.rebuttal_results if r.turn_number == 1)
        turn2 = next(r for r in case_result.rebuttal_results if r.turn_number == 2)

        # Turn 1 should be judged against the post-turn-1 snapshot (DISMISSED).
        assert turn1.actual_status == FindingStatus.DISMISSED
        assert turn1.correct is True

        # Turn 2 should be judged against the post-turn-2 snapshot (OPEN).
        assert turn2.actual_status == FindingStatus.OPEN
        assert turn2.correct is True

        # And get_review_summary must have been called after each turn.
        assert mock_summary.call_count == 2

    async def test_multi_turn_summary_exception_surfaces_as_run_failure(
        self,
    ) -> None:
        """F13 regression: failures in the multi-turn path must NOT be
        silently converted to ``rebuttal_results=None``. A RuntimeError
        from ``get_review_summary`` has to bubble up so ``run_eval`` fails
        the whole run (see FR-007 / spec.md:38-50 + F4's propagation
        contract in ``run_eval``).
        """
        from eval.runner import run_eval

        script = [
            TurnScript(
                turn_number=1,
                rebuttal_message_template="Disagree with {finding_id}.",
                target_expected_id="EF-001",
                expected_status_after=FindingStatus.DISMISSED,
                is_valid_rebuttal=True,
            ),
        ]
        case = _make_golden_case(multi_turn_script=script)

        finding = _make_finding(finding_id="F-001")
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_discuss = AsyncMock(return_value={"response": "ok"})
        mock_summary = AsyncMock(side_effect=RuntimeError("summary blew up"))
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.call_discuss", mock_discuss),
            patch("eval.runner.call_get_review_summary", mock_summary),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            with pytest.raises(RuntimeError, match="summary blew up"):
                await run_eval(
                    cases=[case],
                    session=mock_session,
                    num_trials=1,
                    thresholds=_default_thresholds(),
                )

    async def test_multi_turn_finding_not_found_skips_discuss(self) -> None:
        """When target finding not matched in grading, skip discuss, record finding_not_found."""
        from eval.runner import run_eval

        script = [
            TurnScript(
                turn_number=1,
                rebuttal_message_template="I disagree with finding {finding_id}.",
                target_expected_id="EF-999",  # Not matched
                expected_status_after=FindingStatus.DISMISSED,
                is_valid_rebuttal=True,
            ),
        ]
        case = _make_golden_case(multi_turn_script=script)

        finding = _make_finding(finding_id="F-001")
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_discuss = AsyncMock()
        mock_summary = AsyncMock(return_value=_make_mcp_summary_response())
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.call_discuss", mock_discuss),
            patch("eval.runner.call_get_review_summary", mock_summary),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.rebuttal_results is not None
        assert len(case_result.rebuttal_results) == 1

        rebuttal = case_result.rebuttal_results[0]
        assert rebuttal.finding_not_found is True
        assert rebuttal.actual_finding_id is None
        assert rebuttal.correct is False

        # discuss should NOT have been called for this turn
        mock_discuss.assert_not_called()

    async def test_multi_turn_runs_when_first_trial_errors_but_later_succeeds(
        self,
    ) -> None:
        """A transient failure on trial 1 must not skip multi-turn grading
        when a later trial succeeds."""
        from eval.runner import run_eval

        script = [
            TurnScript(
                turn_number=1,
                rebuttal_message_template="Disagree with {finding_id}.",
                target_expected_id="EF-001",
                expected_status_after=FindingStatus.DISMISSED,
                is_valid_rebuttal=True,
            ),
        ]
        case = _make_golden_case(multi_turn_script=script)

        finding = _make_finding(finding_id="F-001")
        dismissed_finding = _make_finding(
            finding_id="F-001", status=FindingStatus.DISMISSED
        )
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        call_count = 0

        async def start_review_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Transient MCP timeout")
            return _make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(side_effect=start_review_side_effect)
        mock_discuss = AsyncMock(return_value={
            "response": "Finding dismissed.",
            "updated_findings": [dismissed_finding.model_dump(mode="json")],
            "finding_count_by_status": {"dismissed": 1},
        })
        mock_summary = AsyncMock(return_value=_make_mcp_summary_response(
            findings=[dismissed_finding.model_dump(mode="json")]
        ))
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.call_discuss", mock_discuss),
            patch("eval.runner.call_get_review_summary", mock_summary),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=2,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.trials[0].error is not None
        assert case_result.trials[1].error is None
        assert case_result.rebuttal_results is not None
        assert len(case_result.rebuttal_results) == 1
        assert case_result.rebuttal_results[0].correct is True


# ===========================================================================
# TestEvalRunAggregate
# ===========================================================================


class TestEvalRunAggregate:
    """EvalRun has correct aggregate metrics, pass/fail, and metadata."""

    async def test_eval_run_has_aggregate_metrics(self) -> None:
        from eval.runner import run_eval

        case = _make_golden_case()
        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        assert result.aggregate is not None
        assert result.aggregate.precision.mean == 1.0
        assert result.aggregate.recall.mean == 1.0
        assert result.num_trials == 1
        assert result.line_tolerance == 5
        assert result.duration_seconds >= 0
        assert result.run_id  # UUID string, non-empty
        assert result.timestamp is not None

    async def test_pass_fail_based_on_thresholds(self) -> None:
        """pass_fail should be True when all metrics pass thresholds."""
        from eval.runner import run_eval

        case = _make_golden_case()
        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        # Perfect match should pass all thresholds
        assert result.pass_fail is True

    async def test_eval_run_model_evaluated(self) -> None:
        """model_evaluated field should reflect what MCP returns."""
        from eval.runner import run_eval

        case = _make_golden_case()
        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        review_response = _make_mcp_review_response(
            findings=[finding.model_dump(mode="json")]
        )

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(return_value=review_response)
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        assert result.model_evaluated == "copilot-gpt-4"


# ===========================================================================
# TestVerboseMode
# ===========================================================================


class TestVerboseMode:
    """Verbose mode prints progress to stderr without crashing."""

    async def test_verbose_does_not_crash(self) -> None:
        from eval.runner import run_eval

        case = _make_golden_case()
        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            # Should not raise
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                verbose=True,
                thresholds=_default_thresholds(),
            )

        assert isinstance(result, EvalRun)


# ===========================================================================
# TestDualMetricExecution
# ===========================================================================


class TestDualMetricExecution:
    """Dual-metric flow: vulnerable trials + fixed-bundle trials."""

    async def test_dual_metric_populates_results(self) -> None:
        """When dual_metric has a fixed_bundle, dual_metric_results is populated."""
        from eval.runner import run_eval

        fixed_bundle = ReviewBundle(
            diff="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-vuln\n+fixed",
            files={"main.py": "print('fixed')"},
        )
        case = _make_golden_case()
        case = case.model_copy(
            update={
                "dual_metric": DualMetricConfig(
                    vulnerable_dir="bundle",
                    fixed_dir="bundle-fixed",
                    fixed_bundle=fixed_bundle,
                ),
            },
        )

        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=2,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.dual_metric_results is not None
        assert isinstance(case_result.dual_metric_results, DualMetricResult)

        # 2 vulnerable trials + 2 fixed trials = 4 calls to start_review
        assert mock_start_review.call_count == 4
        assert mock_grade.call_count == 4

    async def test_vulnerable_results_equal_main_trials(self) -> None:
        """dual_metric_results.vulnerable_results should equal the main trials."""
        from eval.runner import run_eval

        fixed_bundle = ReviewBundle(
            diff="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-vuln\n+fixed",
            files={"main.py": "print('fixed')"},
        )
        case = _make_golden_case()
        case = case.model_copy(
            update={
                "dual_metric": DualMetricConfig(
                    vulnerable_dir="bundle",
                    fixed_dir="bundle-fixed",
                    fixed_bundle=fixed_bundle,
                ),
            },
        )

        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=2,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.dual_metric_results is not None

        # vulnerable_results should be a copy of the main trials
        assert len(case_result.dual_metric_results.vulnerable_results) == 2
        for vuln_trial, main_trial in zip(
            case_result.dual_metric_results.vulnerable_results,
            case_result.trials,
        ):
            assert vuln_trial.trial_number == main_trial.trial_number
            assert vuln_trial.metrics == main_trial.metrics

    async def test_fixed_results_from_fixed_bundle(self) -> None:
        """dual_metric_results.fixed_results are from the fixed bundle trials."""
        from eval.runner import run_eval

        fixed_bundle = ReviewBundle(
            diff="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-vuln\n+fixed",
            files={"main.py": "print('fixed')"},
        )
        case = _make_golden_case()
        case = case.model_copy(
            update={
                "dual_metric": DualMetricConfig(
                    vulnerable_dir="bundle",
                    fixed_dir="bundle-fixed",
                    fixed_bundle=fixed_bundle,
                ),
            },
        )

        vuln_finding = _make_finding(finding_id="F-001")
        fixed_finding = _make_finding(finding_id="F-FIX-001")

        vuln_response = _make_mcp_review_response(
            findings=[vuln_finding.model_dump(mode="json")]
        )
        fixed_response = _make_mcp_review_response(
            findings=[fixed_finding.model_dump(mode="json")]
        )

        vuln_graded = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]
        fixed_graded = [
            _make_grader_result(
                verdict=GraderVerdict.NO_MATCH,
                matched_expected_id=None,
                actual_finding_id="F-FIX-001",
            ),
        ]

        mock_session = AsyncMock()
        # First call is vulnerable trial, second is fixed trial (1 trial each)
        mock_start_review = AsyncMock(side_effect=[vuln_response, fixed_response])
        mock_grade = AsyncMock(side_effect=[vuln_graded, fixed_graded])

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.dual_metric_results is not None
        assert len(case_result.dual_metric_results.fixed_results) == 1

        fixed_trial = case_result.dual_metric_results.fixed_results[0]
        assert fixed_trial.trial_number == 1
        # Fixed trial should have the fixed finding, not the vulnerable one
        assert len(fixed_trial.findings) == 1
        assert fixed_trial.findings[0].finding_id == "F-FIX-001"

        # F9 regression guard: grader must see no expected findings for the
        # fixed bundle — the fixed version is clean, every finding on it is a
        # false positive. Previously the runner passed case.expected_findings
        # for both bundles, so correctly-silent fixed trials scored precision
        # 1.0 (vacuous) while hallucinating trials got "MATCH" credit.
        fixed_call_kwargs = mock_grade.call_args_list[1].kwargs
        assert fixed_call_kwargs["expected_findings"] == []

    async def test_no_dual_metric_results_when_config_is_none(self) -> None:
        """When case.dual_metric is None, dual_metric_results remains None."""
        from eval.runner import run_eval

        case = _make_golden_case()  # No dual_metric by default

        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            )
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        case_result = result.cases[0]
        assert case_result.dual_metric_results is None

        # Only 1 trial, no extra calls for fixed bundle
        assert mock_start_review.call_count == 1


# ===========================================================================
# TestMCPErrorPropagation (H-4)
# ===========================================================================


class TestMCPErrorPropagation:
    """MCPAbortError aborts the run; MCPSkipCaseError skips the case."""

    async def test_abort_error_propagates_from_trial(self) -> None:
        """MCPAbortError in start_review must propagate, not be swallowed."""
        from eval.mcp_client import MCPAbortError
        from eval.runner import run_eval

        case = _make_golden_case()
        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            side_effect=MCPAbortError("MCP non-retryable error: auth_failed"),
        )

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", AsyncMock()),
        ):
            with pytest.raises(MCPAbortError, match="auth_failed"):
                await run_eval(
                    cases=[case],
                    session=mock_session,
                    num_trials=1,
                    thresholds=_default_thresholds(),
                )

    async def test_skip_error_excludes_case_from_results(self) -> None:
        """MCPSkipCaseError should skip that case; other cases still run."""
        from eval.mcp_client import MCPSkipCaseError
        from eval.runner import run_eval

        case_skip = _make_golden_case(case_id="case-skip")
        case_ok = _make_golden_case(case_id="case-ok")

        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        review_response = _make_mcp_review_response(
            findings=[finding.model_dump(mode="json")],
        )

        call_count = 0

        async def start_review_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise MCPSkipCaseError("MCP skip case: content_denied")
            return review_response

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(side_effect=start_review_side_effect)
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case_skip, case_ok],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        # Only case-ok should appear in results
        assert len(result.cases) == 1
        assert result.cases[0].case_id == "case-ok"

    async def test_abort_error_propagates_from_multi_turn(self) -> None:
        """MCPAbortError during multi-turn discuss must propagate."""
        from eval.mcp_client import MCPAbortError
        from eval.runner import run_eval

        script = [
            TurnScript(
                turn_number=1,
                rebuttal_message_template="Disagree with {finding_id}.",
                target_expected_id="EF-001",
                expected_status_after=FindingStatus.DISMISSED,
                is_valid_rebuttal=True,
            ),
        ]
        case = _make_golden_case(multi_turn_script=script)

        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[finding.model_dump(mode="json")]
            ),
        )
        mock_discuss = AsyncMock(
            side_effect=MCPAbortError("MCP non-retryable error: unavailable"),
        )
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.call_discuss", mock_discuss),
            patch("eval.runner.call_get_review_summary", AsyncMock()),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            with pytest.raises(MCPAbortError, match="unavailable"):
                await run_eval(
                    cases=[case],
                    session=mock_session,
                    num_trials=1,
                    thresholds=_default_thresholds(),
                )

    async def test_skip_error_during_multi_turn_skips_case(self) -> None:
        """MCPSkipCaseError during multi-turn should skip that case."""
        from eval.mcp_client import MCPSkipCaseError
        from eval.runner import run_eval

        script = [
            TurnScript(
                turn_number=1,
                rebuttal_message_template="Disagree with {finding_id}.",
                target_expected_id="EF-001",
                expected_status_after=FindingStatus.DISMISSED,
                is_valid_rebuttal=True,
            ),
        ]
        case_mt = _make_golden_case(case_id="case-mt", multi_turn_script=script)
        case_ok = _make_golden_case(case_id="case-ok")

        finding = _make_finding()
        grader_results = [
            _make_grader_result(
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            ),
        ]

        review_response = _make_mcp_review_response(
            findings=[finding.model_dump(mode="json")]
        )

        call_count = 0

        async def start_review_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # 1st call: case-mt trial, 2nd: case-mt multi-turn (skip here)
            if call_count == 2:
                raise MCPSkipCaseError("content_denied")
            return review_response

        mock_session = AsyncMock()
        mock_start_review = AsyncMock(side_effect=start_review_side_effect)
        mock_grade = AsyncMock(return_value=grader_results)

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.call_discuss", AsyncMock()),
            patch("eval.runner.call_get_review_summary", AsyncMock()),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            result = await run_eval(
                cases=[case_mt, case_ok],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        # case-mt should be skipped, case-ok should succeed
        assert len(result.cases) == 1
        assert result.cases[0].case_id == "case-ok"

    async def test_generic_exception_still_records_trial_error(self) -> None:
        """Non-MCP exceptions (RuntimeError etc.) still become trial errors."""
        from eval.runner import run_eval

        case = _make_golden_case()
        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            side_effect=RuntimeError("Connection refused"),
        )

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", AsyncMock()),
        ):
            result = await run_eval(
                cases=[case],
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        # Generic errors still become trial errors (not abort/skip)
        assert len(result.cases) == 1
        assert result.cases[0].trials[0].error is not None
        assert "Connection refused" in result.cases[0].trials[0].error

    async def test_grader_crash_propagates_not_silently_dropped(self) -> None:
        """Crashes above the trial's MCP boundary must abort the run.

        _run_single_trial converts start_review exceptions into trial errors,
        but crashes from grade_all_findings, multi-turn, dual-metric, or
        pass-computation bubble up to _run_single_case with no local handler.
        Those must propagate out of run_eval rather than being swallowed by
        the gather() error handler (which would silently exclude the case
        while reporting PASS on any remaining cases).
        """
        from eval.runner import run_eval

        case = _make_golden_case()
        mock_session = AsyncMock()
        mock_start_review = AsyncMock(
            return_value=_make_mcp_review_response(
                findings=[_make_finding().model_dump(mode="json")],
            ),
        )
        mock_grade = AsyncMock(side_effect=RuntimeError("grader blew up"))

        with (
            patch("eval.runner.call_start_review", mock_start_review),
            patch("eval.runner.grade_all_findings", mock_grade),
        ):
            with pytest.raises(RuntimeError, match="grader blew up"):
                await run_eval(
                    cases=[case],
                    session=mock_session,
                    num_trials=1,
                    thresholds=_default_thresholds(),
                )
