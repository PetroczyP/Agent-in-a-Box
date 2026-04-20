"""Tests for the grading pipeline (T005).

Tier 1 (fingerprint) is used directly — it's deterministic and fast.
Tier 2 (model_grader) is always mocked — no real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from eval.graders.pipeline import grade_all_findings
from eval.models import (
    ExpectedFinding,
    GraderConfidence,
    GraderResult,
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


def _make_tier2_result(
    *,
    finding_id: str,
    verdict: GraderVerdict = GraderVerdict.NOVEL_VALID,
    matched_expected_id: str | None = None,
    confidence: GraderConfidence = GraderConfidence.MEDIUM,
    reasoning: str = "Model grader reasoning",
) -> GraderResult:
    return GraderResult(
        tier=2,
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        matched_expected_id=matched_expected_id,
        actual_finding_id=finding_id,
    )


# --- Tests ---


class TestTier1MatchStopsPipeline:
    """When Tier 1 finds a match, Tier 2 must NOT be called."""

    async def test_tier1_match_skips_tier2(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]

        mock_tier2 = AsyncMock()

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=[finding],
                expected_findings=expected,
                case_description="Test case",
            )

        assert len(results) == 1
        assert results[0].tier == 1
        assert results[0].verdict == GraderVerdict.MATCH
        assert results[0].matched_expected_id == "EF-001"
        mock_tier2.assert_not_called()


class TestTier1MissForwardsToTier2:
    """When Tier 1 returns None, the finding is forwarded to Tier 2."""

    async def test_no_fingerprint_match_calls_tier2(self) -> None:
        finding = _make_finding(rule_id="buffer-overflow")
        expected = [_make_expected(rule_id="sql-injection")]

        tier2_result = _make_tier2_result(
            finding_id="F-001",
            verdict=GraderVerdict.NOVEL_VALID,
        )
        mock_tier2 = AsyncMock(return_value=tier2_result)

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=[finding],
                expected_findings=expected,
                case_description="Test case",
            )

        assert len(results) == 1
        assert results[0].tier == 2
        assert results[0].verdict == GraderVerdict.NOVEL_VALID
        mock_tier2.assert_called_once()

    async def test_tier2_receives_unclaimed_expected_findings(self) -> None:
        """Tier 2 should only see expected findings not yet claimed by Tier 1."""
        # F-001 matches EF-001 via Tier 1; F-002 has no Tier 1 match
        finding_1 = _make_finding(finding_id="F-001", rule_id="sql-injection", start_line=10)
        finding_2 = _make_finding(finding_id="F-002", rule_id="buffer-overflow", start_line=20)

        ef_1 = _make_expected(expected_id="EF-001", rule_id="sql-injection", approximate_line=10)
        ef_2 = _make_expected(
            expected_id="EF-002",
            rule_id="buffer-overflow",
            approximate_line=50,  # Too far for Tier 1 match
            file="src/other.py",
        )

        tier2_result = _make_tier2_result(
            finding_id="F-002",
            verdict=GraderVerdict.NO_MATCH,
        )
        mock_tier2 = AsyncMock(return_value=tier2_result)

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            await grade_all_findings(
                findings=[finding_1, finding_2],
                expected_findings=[ef_1, ef_2],
                case_description="Test case",
            )

        # Tier 2 should have been called with only EF-002 (EF-001 was claimed by Tier 1)
        call_args = mock_tier2.call_args
        tier2_expected_findings = call_args[1].get("expected_findings") or call_args[0][1]
        expected_ids = [ef.expected_id for ef in tier2_expected_findings]
        assert "EF-001" not in expected_ids, "Claimed EF-001 should not be passed to Tier 2"
        assert "EF-002" in expected_ids


class TestClaimedExpectedTracking:
    """Expected findings matched by Tier 1 cannot be matched again."""

    async def test_second_finding_same_expected_goes_to_tier2(self) -> None:
        """Two findings match the same expected. First claims it via Tier 1;
        second must go to Tier 2."""
        finding_1 = _make_finding(finding_id="F-001", start_line=10)
        finding_2 = _make_finding(finding_id="F-002", start_line=12)

        expected = [_make_expected(expected_id="EF-001", approximate_line=10)]

        tier2_result = _make_tier2_result(
            finding_id="F-002",
            verdict=GraderVerdict.NO_MATCH,
        )
        mock_tier2 = AsyncMock(return_value=tier2_result)

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=[finding_1, finding_2],
                expected_findings=expected,
                case_description="Test case",
            )

        assert len(results) == 2
        # First finding: Tier 1 match
        assert results[0].tier == 1
        assert results[0].matched_expected_id == "EF-001"
        # Second finding: forwarded to Tier 2 (expected already claimed)
        assert results[1].tier == 2
        mock_tier2.assert_called_once()


class TestMixedResults:
    """Some findings match Tier 1, others go to Tier 2."""

    async def test_mixed_tier1_and_tier2(self) -> None:
        # F-001: matches EF-001 via Tier 1 (same rule, file, line)
        finding_1 = _make_finding(
            finding_id="F-001", rule_id="sql-injection", start_line=10
        )
        # F-002: different rule_id, no Tier 1 match -> Tier 2
        finding_2 = _make_finding(
            finding_id="F-002", rule_id="xss", start_line=30,
        )
        # F-003: matches EF-002 via Tier 1
        finding_3 = _make_finding(
            finding_id="F-003", rule_id="null-deref", start_line=50,
            file="src/util.py",
        )

        ef_1 = _make_expected(
            expected_id="EF-001", rule_id="sql-injection", approximate_line=10,
        )
        ef_2 = _make_expected(
            expected_id="EF-002", rule_id="null-deref", approximate_line=50,
            file="src/util.py",
        )

        tier2_result = _make_tier2_result(
            finding_id="F-002",
            verdict=GraderVerdict.NOVEL_VALID,
        )
        mock_tier2 = AsyncMock(return_value=tier2_result)

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=[finding_1, finding_2, finding_3],
                expected_findings=[ef_1, ef_2],
                case_description="Test case",
            )

        assert len(results) == 3
        # F-001: Tier 1
        assert results[0].tier == 1
        assert results[0].verdict == GraderVerdict.MATCH
        assert results[0].actual_finding_id == "F-001"
        # F-002: Tier 2
        assert results[1].tier == 2
        assert results[1].verdict == GraderVerdict.NOVEL_VALID
        assert results[1].actual_finding_id == "F-002"
        # F-003: Tier 1
        assert results[2].tier == 1
        assert results[2].verdict == GraderVerdict.MATCH
        assert results[2].actual_finding_id == "F-003"
        # Tier 2 called only for F-002
        mock_tier2.assert_called_once()


class TestTier2ClaimsExpectedIds:
    """A Tier 2 match/partial_match must prevent later findings from
    re-matching the same expected finding."""

    async def test_second_finding_cannot_reclaim_tier2_match(self) -> None:
        finding_1 = _make_finding(finding_id="F-001", rule_id="semantic-dup-a")
        finding_2 = _make_finding(finding_id="F-002", rule_id="semantic-dup-b")
        expected = [_make_expected(expected_id="EF-001", rule_id="sql-injection")]

        tier2_results = [
            _make_tier2_result(
                finding_id="F-001",
                verdict=GraderVerdict.MATCH,
                matched_expected_id="EF-001",
            ),
            _make_tier2_result(
                finding_id="F-002",
                verdict=GraderVerdict.NO_MATCH,
            ),
        ]
        mock_tier2 = AsyncMock(side_effect=tier2_results)

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            await grade_all_findings(
                findings=[finding_1, finding_2],
                expected_findings=expected,
                case_description="Test case",
            )

        second_call_expected = mock_tier2.await_args_list[1].kwargs["expected_findings"]
        assert [ef.expected_id for ef in second_call_expected] == []

    async def test_partial_match_also_claims(self) -> None:
        finding_1 = _make_finding(finding_id="F-001", rule_id="semantic-dup-a")
        finding_2 = _make_finding(finding_id="F-002", rule_id="semantic-dup-b")
        expected = [_make_expected(expected_id="EF-001", rule_id="sql-injection")]

        tier2_results = [
            _make_tier2_result(
                finding_id="F-001",
                verdict=GraderVerdict.PARTIAL_MATCH,
                matched_expected_id="EF-001",
            ),
            _make_tier2_result(
                finding_id="F-002",
                verdict=GraderVerdict.NO_MATCH,
            ),
        ]
        mock_tier2 = AsyncMock(side_effect=tier2_results)

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            await grade_all_findings(
                findings=[finding_1, finding_2],
                expected_findings=expected,
                case_description="Test case",
            )

        second_call_expected = mock_tier2.await_args_list[1].kwargs["expected_findings"]
        assert [ef.expected_id for ef in second_call_expected] == []


class TestTier2GradingErrorReturnsResult:
    """Tier 2 API failure returns grading_error, not an exception."""

    async def test_tier2_error_produces_grading_error_result(self) -> None:
        finding = _make_finding(rule_id="unknown-rule")
        expected = [_make_expected(rule_id="sql-injection")]

        error_result = GraderResult(
            tier=2,
            verdict=GraderVerdict.GRADING_ERROR,
            confidence=GraderConfidence.LOW,
            reasoning="API error after 3 retries",
            matched_expected_id=None,
            actual_finding_id="F-001",
        )
        mock_tier2 = AsyncMock(return_value=error_result)

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=[finding],
                expected_findings=expected,
                case_description="Test case",
            )

        assert len(results) == 1
        assert results[0].verdict == GraderVerdict.GRADING_ERROR
        assert results[0].tier == 2

    async def test_tier2_exception_produces_grading_error_result(self) -> None:
        """If Tier 2 raises an unexpected exception, pipeline catches it
        and returns grading_error instead of propagating."""
        finding = _make_finding(rule_id="unknown-rule")
        expected = [_make_expected(rule_id="sql-injection")]

        mock_tier2 = AsyncMock(side_effect=RuntimeError("Connection failed"))

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=[finding],
                expected_findings=expected,
                case_description="Test case",
            )

        assert len(results) == 1
        assert results[0].verdict == GraderVerdict.GRADING_ERROR
        assert results[0].confidence == GraderConfidence.LOW
        assert "Connection failed" in (results[0].reasoning or "")
        assert results[0].actual_finding_id == "F-001"
        assert results[0].tier == 2

    async def test_missing_grader_credential_propagates(self) -> None:
        """MissingGraderCredentialError must abort the run, not per-finding error.

        Regression guard for F10: the spec/CLI contract treats a missing
        ANTHROPIC_API_KEY as a harness configuration error with exit 2.
        Previously the pipeline caught the auth ``ValueError`` and silently
        downgraded every unmatched finding to ``GRADING_ERROR`` — producing
        a completed run that excluded the unmatched findings from scoring.
        """
        from eval.graders import MissingGraderCredentialError

        finding = _make_finding(rule_id="unknown-rule")
        expected = [_make_expected(rule_id="sql-injection")]

        mock_tier2 = AsyncMock(
            side_effect=MissingGraderCredentialError("ANTHROPIC_API_KEY is not set")
        )

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            with pytest.raises(
                MissingGraderCredentialError, match="ANTHROPIC_API_KEY"
            ):
                await grade_all_findings(
                    findings=[finding],
                    expected_findings=expected,
                    case_description="Test case",
                )


class TestEmptyFindingsReturnsEmpty:
    """Empty findings list produces empty results."""

    async def test_empty_findings(self) -> None:
        mock_tier2 = AsyncMock()

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=[],
                expected_findings=[_make_expected()],
                case_description="Test case",
            )

        assert results == []
        mock_tier2.assert_not_called()


class TestResultsOrderMatchesInput:
    """Results must be in the same order as input findings."""

    async def test_ordering_preserved(self) -> None:
        findings = [
            _make_finding(finding_id="F-003", rule_id="xss", start_line=30),
            _make_finding(finding_id="F-001", rule_id="sql-injection", start_line=10),
            _make_finding(finding_id="F-002", rule_id="null-deref", start_line=50),
        ]
        expected = [
            _make_expected(
                expected_id="EF-001", rule_id="sql-injection", approximate_line=10,
            ),
        ]

        async def mock_tier2_fn(finding, **kwargs):
            return _make_tier2_result(
                finding_id=finding.finding_id,
                verdict=GraderVerdict.NO_MATCH,
            )

        mock_tier2 = AsyncMock(side_effect=mock_tier2_fn)

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=findings,
                expected_findings=expected,
                case_description="Test case",
            )

        assert len(results) == 3
        assert results[0].actual_finding_id == "F-003"  # Tier 2 (no rule match)
        assert results[1].actual_finding_id == "F-001"  # Tier 1 (matches EF-001)
        assert results[2].actual_finding_id == "F-002"  # Tier 2 (no rule match)


class TestPromptParametersPassthrough:
    """Optional prompt parameters are forwarded to Tier 2."""

    async def test_custom_prompt_params_forwarded(self) -> None:
        finding = _make_finding(rule_id="unknown")
        expected = [_make_expected(rule_id="sql-injection")]

        tier2_result = _make_tier2_result(finding_id="F-001")
        mock_tier2 = AsyncMock(return_value=tier2_result)

        custom_template = "Custom prompt: {findings}"
        custom_rubric = "Custom rubric text"
        custom_examples = [{"input": "x", "output": "y"}]

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            await grade_all_findings(
                findings=[finding],
                expected_findings=expected,
                case_description="Test case",
                grader_model="claude-haiku-3",
                prompt_template=custom_template,
                rubric=custom_rubric,
                few_shot_examples=custom_examples,
                max_retries=5,
            )

        mock_tier2.assert_called_once()
        call_kwargs = mock_tier2.call_args[1]
        assert call_kwargs["case_description"] == "Test case"
        assert call_kwargs["grader_model"] == "claude-haiku-3"
        assert call_kwargs["prompt_template"] == custom_template
        assert call_kwargs["rubric"] == custom_rubric
        assert call_kwargs["few_shot_examples"] == custom_examples
        assert call_kwargs["max_retries"] == 5


class TestPartialMatchTier1:
    """Tier 1 partial_match is used as-is (not forwarded to Tier 2)."""

    async def test_partial_match_not_forwarded(self) -> None:
        # severity mismatch -> partial_match from Tier 1
        finding = _make_finding(severity=Severity.WARN)
        expected = [_make_expected(severity=Severity.BUG)]

        mock_tier2 = AsyncMock()

        with patch("eval.graders.pipeline.model_grade", mock_tier2):
            results = await grade_all_findings(
                findings=[finding],
                expected_findings=expected,
                case_description="Test case",
            )

        assert len(results) == 1
        assert results[0].tier == 1
        assert results[0].verdict == GraderVerdict.PARTIAL_MATCH
        mock_tier2.assert_not_called()
