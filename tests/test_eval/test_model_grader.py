"""Tests for the Tier 2 model-based grader (T004).

All tests use mocked Anthropic API -- no real API calls are ever made.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eval.graders.model_grader import build_grader_prompt, grade_finding
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
    message: str = "SQL injection vulnerability",
    evidence: str = "User input directly in query",
) -> Finding:
    return Finding(
        finding_id=finding_id,
        rule_id=rule_id,
        severity=severity,
        category=category,
        message=message,
        primary_location=Location(file=file, start_line=start_line, end_line=end_line),
        fingerprint="fp-hash",
        confidence="high",
        evidence=evidence,
    )


def _make_expected(
    *,
    expected_id: str = "EF-001",
    rule_id: str = "sql-injection",
    severity: Severity = Severity.BUG,
    category: Category = Category.SECURITY,
    file: str = "src/main.py",
    approximate_line: int = 10,
    description: str = "SQL injection in query builder",
) -> ExpectedFinding:
    return ExpectedFinding(
        expected_id=expected_id,
        rule_id=rule_id,
        severity=severity,
        category=category,
        file=file,
        approximate_line=approximate_line,
        description=description,
    )


def _mock_api_response(text: str) -> MagicMock:
    """Build a mock Anthropic API response with given text content."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# --- Tests ---


class TestMatchVerdict:
    """API returns match verdict -> correct GraderResult."""

    async def test_match_verdict_returns_correct_result(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "match",
            "confidence": "high",
            "matched_expected_id": "EF-001",
            "reasoning": "Same SQL injection issue",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="SQL injection test case",
            )

        assert isinstance(result, GraderResult)
        assert result.verdict == GraderVerdict.MATCH
        assert result.confidence == GraderConfidence.HIGH
        assert result.matched_expected_id == "EF-001"
        assert result.reasoning == "Same SQL injection issue"
        assert result.actual_finding_id == "F-001"
        assert result.tier == 2


class TestNovelValidVerdict:
    """API returns novel_valid verdict -> correct GraderResult with no matched_expected_id."""

    async def test_novel_valid_verdict_returns_correct_result(self) -> None:
        finding = _make_finding(
            finding_id="F-002",
            rule_id="null-deref",
            message="Potential null dereference",
        )
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "novel_valid",
            "confidence": "medium",
            "matched_expected_id": None,
            "reasoning": "Real issue not in expected set",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="SQL injection test case",
            )

        assert result.verdict == GraderVerdict.NOVEL_VALID
        assert result.confidence == GraderConfidence.MEDIUM
        assert result.matched_expected_id is None
        assert result.actual_finding_id == "F-002"
        assert result.tier == 2


class TestNoMatchVerdict:
    """API returns no_match verdict -> matched_expected_id is None."""

    async def test_no_match_verdict_has_no_matched_id(self) -> None:
        finding = _make_finding(finding_id="F-003")
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "no_match",
            "confidence": "high",
            "matched_expected_id": None,
            "reasoning": "Not a real issue",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.verdict == GraderVerdict.NO_MATCH
        assert result.matched_expected_id is None
        assert result.tier == 2


class TestPartialMatchVerdict:
    """API returns partial_match -> matched_expected_id is set."""

    async def test_partial_match_has_matched_id(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "partial_match",
            "confidence": "medium",
            "matched_expected_id": "EF-001",
            "reasoning": "Related but different severity",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.verdict == GraderVerdict.PARTIAL_MATCH
        assert result.matched_expected_id == "EF-001"
        assert result.tier == 2


class TestAPIFailureAfterRetries:
    """API failure after max retries -> grading_error."""

    async def test_api_error_returns_grading_error(self) -> None:
        import anthropic as anthropic_mod

        finding = _make_finding()
        expected = [_make_expected()]

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            # Simulate API error on every call
            mock_client.messages.create = AsyncMock(
                side_effect=anthropic_mod.APIStatusError(
                    message="Internal Server Error",
                    response=MagicMock(status_code=500),
                    body=None,
                )
            )
            mock_anthropic.AsyncAnthropic.return_value = mock_client
            mock_anthropic.APIStatusError = anthropic_mod.APIStatusError
            mock_anthropic.RateLimitError = anthropic_mod.RateLimitError

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
                max_retries=3,
            )

        assert result.verdict == GraderVerdict.GRADING_ERROR
        assert result.confidence == GraderConfidence.LOW
        assert "API error after 3 retries" in result.reasoning
        assert result.tier == 2
        assert result.matched_expected_id is None
        assert result.actual_finding_id == "F-001"


class TestRateLimitRetry:
    """Rate limit error -> retries with backoff, succeeds on later attempt."""

    async def test_rate_limit_then_success(self) -> None:
        import anthropic as anthropic_mod

        finding = _make_finding()
        expected = [_make_expected()]
        success_response = _mock_api_response(json.dumps({
            "verdict": "match",
            "confidence": "high",
            "matched_expected_id": "EF-001",
            "reasoning": "Matched after retry",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=[
                    anthropic_mod.RateLimitError(
                        message="Rate limited",
                        response=MagicMock(status_code=429),
                        body=None,
                    ),
                    success_response,
                ]
            )
            mock_anthropic.AsyncAnthropic.return_value = mock_client
            mock_anthropic.APIStatusError = anthropic_mod.APIStatusError
            mock_anthropic.RateLimitError = anthropic_mod.RateLimitError

            with patch("eval.graders.model_grader.asyncio.sleep", new_callable=AsyncMock):
                result = await grade_finding(
                    finding=finding,
                    expected_findings=expected,
                    case_description="Test case",
                )

        assert result.verdict == GraderVerdict.MATCH
        assert result.matched_expected_id == "EF-001"


class TestJSONParseFailureReprompt:
    """Invalid JSON -> re-prompt once -> still invalid -> grading_error."""

    async def test_invalid_json_reprompt_then_error(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        # Both responses are invalid JSON
        bad_response_1 = _mock_api_response("This is not JSON at all")
        bad_response_2 = _mock_api_response("Still not JSON {broken")

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=[bad_response_1, bad_response_2]
            )
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.verdict == GraderVerdict.GRADING_ERROR
        assert result.confidence == GraderConfidence.LOW
        assert "Invalid grader response after retry" in result.reasoning
        assert result.tier == 2

    async def test_invalid_json_reprompt_then_success(self) -> None:
        """Invalid JSON first time, valid JSON on re-prompt -> success."""
        finding = _make_finding()
        expected = [_make_expected()]
        bad_response = _mock_api_response("Not valid JSON")
        good_response = _mock_api_response(json.dumps({
            "verdict": "novel_valid",
            "confidence": "low",
            "matched_expected_id": None,
            "reasoning": "Valid on retry",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=[bad_response, good_response]
            )
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.verdict == GraderVerdict.NOVEL_VALID
        assert result.confidence == GraderConfidence.LOW


class TestPromptContent:
    """The built prompt includes expected findings, rubric, and case description."""

    def test_prompt_includes_expected_findings(self) -> None:
        finding = _make_finding()
        expected = [
            _make_expected(expected_id="EF-001", description="SQL injection in query"),
            _make_expected(
                expected_id="EF-002",
                rule_id="xss",
                description="XSS in template",
            ),
        ]

        prompt = build_grader_prompt(
            finding=finding,
            expected_findings=expected,
            case_description="Multi-finding test case",
        )

        assert "EF-001" in prompt
        assert "EF-002" in prompt
        assert "SQL injection in query" in prompt
        assert "XSS in template" in prompt

    def test_prompt_includes_actual_finding(self) -> None:
        finding = _make_finding(
            finding_id="F-042",
            rule_id="buffer-overflow",
            message="Heap overflow in parser",
            evidence="memcpy without bounds check",
        )
        expected = [_make_expected()]

        prompt = build_grader_prompt(
            finding=finding,
            expected_findings=expected,
            case_description="Test case",
        )

        assert "F-042" in prompt
        assert "buffer-overflow" in prompt
        assert "Heap overflow in parser" in prompt
        assert "memcpy without bounds check" in prompt

    def test_prompt_includes_case_description(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]

        prompt = build_grader_prompt(
            finding=finding,
            expected_findings=expected,
            case_description="Python web app with SQL injection vulnerability",
        )

        assert "Python web app with SQL injection vulnerability" in prompt

    def test_prompt_includes_rubric(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]

        prompt = build_grader_prompt(
            finding=finding,
            expected_findings=expected,
            case_description="Test case",
            rubric="Custom rubric: grade strictly",
        )

        assert "Custom rubric: grade strictly" in prompt

    def test_prompt_includes_default_rubric_when_none(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]

        prompt = build_grader_prompt(
            finding=finding,
            expected_findings=expected,
            case_description="Test case",
        )

        # Default rubric should include the verdict definitions
        assert "match" in prompt
        assert "partial_match" in prompt
        assert "novel_valid" in prompt
        assert "no_match" in prompt

    def test_prompt_includes_few_shot_examples(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        examples = [
            {
                "finding": "Buffer overflow in read_input()",
                "verdict": "match",
                "reasoning": "Same underlying issue as EF-003",
            },
        ]

        prompt = build_grader_prompt(
            finding=finding,
            expected_findings=expected,
            case_description="Test case",
            few_shot_examples=examples,
        )

        assert "Buffer overflow in read_input()" in prompt
        assert "Same underlying issue as EF-003" in prompt

    def test_prompt_includes_output_format(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]

        prompt = build_grader_prompt(
            finding=finding,
            expected_findings=expected,
            case_description="Test case",
        )

        assert "JSON" in prompt
        assert "verdict" in prompt

    def test_custom_prompt_template(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]

        prompt = build_grader_prompt(
            finding=finding,
            expected_findings=expected,
            case_description="Test case",
            prompt_template="CUSTOM: {actual_finding}\n{expected_findings}\n{case_description}\n{rubric}\n{few_shot_examples}\n{output_format}",
        )

        assert prompt.startswith("CUSTOM:")


class TestMatchedExpectedIdLogic:
    """matched_expected_id set correctly per verdict type."""

    async def test_match_has_matched_id(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "match",
            "confidence": "high",
            "matched_expected_id": "EF-001",
            "reasoning": "Same issue",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.matched_expected_id == "EF-001"

    async def test_novel_valid_has_no_matched_id(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "novel_valid",
            "confidence": "high",
            "matched_expected_id": None,
            "reasoning": "New finding",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.matched_expected_id is None

    async def test_no_match_has_no_matched_id(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "no_match",
            "confidence": "low",
            "matched_expected_id": None,
            "reasoning": "Noise",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.matched_expected_id is None


class TestTierIsAlwaysTwo:
    """Every GraderResult from Tier 2 grader must have tier=2."""

    async def test_success_result_tier_is_two(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "match",
            "confidence": "high",
            "matched_expected_id": "EF-001",
            "reasoning": "Matched",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.tier == 2

    async def test_grading_error_tier_is_two(self) -> None:
        import anthropic as anthropic_mod

        finding = _make_finding()
        expected = [_make_expected()]

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=anthropic_mod.APIStatusError(
                    message="Server Error",
                    response=MagicMock(status_code=500),
                    body=None,
                )
            )
            mock_anthropic.AsyncAnthropic.return_value = mock_client
            mock_anthropic.APIStatusError = anthropic_mod.APIStatusError
            mock_anthropic.RateLimitError = anthropic_mod.RateLimitError

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
                max_retries=1,
            )

        assert result.tier == 2


class TestAPICallParameters:
    """Verify temperature=0, max_tokens=512, correct model passed."""

    async def test_api_called_with_correct_params(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "match",
            "confidence": "high",
            "matched_expected_id": "EF-001",
            "reasoning": "Matched",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
                grader_model="claude-sonnet-4-6",
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["temperature"] == 0
        assert call_kwargs["max_tokens"] == 512

    async def test_custom_model_passed_through(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        api_response = _mock_api_response(json.dumps({
            "verdict": "match",
            "confidence": "high",
            "matched_expected_id": "EF-001",
            "reasoning": "Matched",
        }))

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
                grader_model="claude-opus-4-6",
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"


class TestMissingAPIKey:
    """Missing ANTHROPIC_API_KEY -> MissingGraderCredentialError raised.

    The exception class is intentionally distinct from ValueError so the
    pipeline can propagate it instead of catching it and converting every
    unmatched finding into a soft GRADING_ERROR (F10). See
    eval-cli.md:84-90 — missing credentials must exit with code 2.
    """

    async def test_missing_api_key_raises_credential_error(self) -> None:
        import anthropic as anthropic_mod

        from eval.graders import MissingGraderCredentialError

        finding = _make_finding()
        expected = [_make_expected()]

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.side_effect = (
                anthropic_mod.AuthenticationError(
                    message="Missing API key",
                    response=MagicMock(status_code=401),
                    body=None,
                )
            )
            mock_anthropic.AuthenticationError = anthropic_mod.AuthenticationError

            with pytest.raises(
                MissingGraderCredentialError, match="ANTHROPIC_API_KEY"
            ):
                await grade_finding(
                    finding=finding,
                    expected_findings=expected,
                    case_description="Test case",
                )


class TestJsonRepairFallback:
    """json_repair is tried when json.loads fails on otherwise recoverable JSON."""

    async def test_json_repair_fixes_minor_issue(self) -> None:
        finding = _make_finding()
        expected = [_make_expected()]
        # Trailing comma — invalid in strict JSON but repairable
        api_response = _mock_api_response(
            '{"verdict": "match", "confidence": "high", '
            '"matched_expected_id": "EF-001", "reasoning": "Fixed by repair",}'
        )

        with patch("eval.graders.model_grader.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=api_response)
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await grade_finding(
                finding=finding,
                expected_findings=expected,
                case_description="Test case",
            )

        assert result.verdict == GraderVerdict.MATCH
        assert result.reasoning == "Fixed by repair"
