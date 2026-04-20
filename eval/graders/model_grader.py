"""Tier 2 model-based grader for the eval harness.

Semantic grading of findings via LLM-as-Judge (Anthropic API).
Called for findings that did NOT match in Tier 1 fingerprint grading.
"""

from __future__ import annotations

import asyncio
import json
import logging

import anthropic
import json_repair

from eval.graders import DEFAULT_GRADER_MODEL, MissingGraderCredentialError
from eval.models import (
    ExpectedFinding,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
)
from server.models import Finding

logger = logging.getLogger(__name__)

# HTTP status codes worth retrying: rate limits + transient server errors.
_RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


_DEFAULT_PROMPT_TEMPLATE = """\
## Task
You are evaluating whether a code review finding matches any expected finding,
or whether it represents a novel valid issue or noise.

## Expected Findings
{expected_findings}

## Actual Finding to Grade
{actual_finding}

## Case Context
{case_description}

## Rubric
{rubric}

## Few-Shot Examples
{few_shot_examples}

## Output Format
{output_format}"""

_DEFAULT_RUBRIC = """\
- **match**: The finding describes the same underlying issue as an expected finding, \
regardless of wording differences.
- **partial_match**: The finding addresses a related aspect of an expected issue \
but differs in severity or category.
- **novel_valid**: The finding describes a real, actionable code issue that is NOT \
in the expected set. The issue would be worth flagging in a real review.
- **no_match**: The finding is noise -- not a real issue, or too vague to be actionable."""

_DEFAULT_FEW_SHOT_EXAMPLES = [
    {
        "finding": "SQL injection in build_query() via unsanitized user input",
        "expected": "EF-001: SQL injection in query builder (security, BUG)",
        "verdict": "match",
        "reasoning": "Same underlying SQL injection issue, matching rule and location.",
    },
    {
        "finding": "Potential XSS in template rendering (severity: WARN, category: security)",
        "expected": "EF-002: XSS vulnerability in template (severity: BUG, category: security)",
        "verdict": "partial_match",
        "reasoning": "Same XSS issue but severity differs (WARN vs BUG).",
    },
    {
        "finding": "Memory leak in connection pool -- connections not closed on error path",
        "expected": "EF-001: SQL injection in query builder",
        "verdict": "novel_valid",
        "reasoning": "Real resource leak issue not covered by any expected finding.",
    },
    {
        "finding": "Consider using a constant for the string 'utf-8'",
        "expected": "EF-001: SQL injection in query builder",
        "verdict": "no_match",
        "reasoning": "Stylistic suggestion, not a real code issue. Too vague to be actionable.",
    },
]

_OUTPUT_FORMAT = """\
Respond with ONLY a JSON object (no markdown, no explanation outside the JSON):
{
  "verdict": "match" | "partial_match" | "novel_valid" | "no_match",
  "confidence": "high" | "medium" | "low",
  "matched_expected_id": "EF-001" | null,
  "reasoning": "Brief explanation"
}"""


def _format_expected_findings(expected_findings: list[ExpectedFinding]) -> str:
    """Format expected findings into a readable list for the prompt."""
    lines = []
    for ef in expected_findings:
        lines.append(
            f"- {ef.expected_id}: {ef.description}\n"
            f"  Rule: {ef.rule_id} | Severity: {ef.severity.value} | "
            f"Category: {ef.category.value}\n"
            f"  File: {ef.file} | Line: ~{ef.approximate_line}"
        )
    return "\n".join(lines)


def _format_actual_finding(finding: Finding) -> str:
    """Format the actual finding for the prompt."""
    return (
        f"- Finding ID: {finding.finding_id}\n"
        f"- Rule ID: {finding.rule_id}\n"
        f"- Severity: {finding.severity.value}\n"
        f"- Category: {finding.category.value}\n"
        f"- File: {finding.primary_location.file}\n"
        f"- Line: {finding.primary_location.start_line}\n"
        f"- Message: {finding.message}\n"
        f"- Evidence: {finding.evidence}"
    )


def _format_few_shot_examples(examples: list[dict]) -> str:
    """Format few-shot examples into a readable block."""
    lines = []
    for i, ex in enumerate(examples, 1):
        lines.append(f"Example {i}:")
        for key, value in ex.items():
            lines.append(f"  {key}: {value}")
        lines.append("")
    return "\n".join(lines)


def build_grader_prompt(
    finding: Finding,
    expected_findings: list[ExpectedFinding],
    case_description: str,
    prompt_template: str | None = None,
    rubric: str | None = None,
    few_shot_examples: list[dict] | None = None,
) -> str:
    """Build the grader prompt from template + finding + expected findings.

    If prompt_template, rubric, or few_shot_examples are None, sensible defaults
    are used (matching the structure from grader-contract.md).
    """
    template = prompt_template or _DEFAULT_PROMPT_TEMPLATE
    rubric_text = rubric or _DEFAULT_RUBRIC
    examples = few_shot_examples or _DEFAULT_FEW_SHOT_EXAMPLES

    return template.format(
        expected_findings=_format_expected_findings(expected_findings),
        actual_finding=_format_actual_finding(finding),
        case_description=case_description,
        rubric=rubric_text,
        few_shot_examples=_format_few_shot_examples(examples),
        output_format=_OUTPUT_FORMAT,
    )


def _parse_grader_response(text: str) -> dict | None:
    """Parse JSON from the grader response, using json_repair as fallback.

    Returns the parsed dict or None if parsing fails completely.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    try:
        repaired = json_repair.repair_json(text, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
    except (ValueError, TypeError) as exc:
        logger.warning("json_repair failed on grader response: %s", exc)

    return None


def _validate_grader_response(data: dict) -> bool:
    """Check that the parsed response has the required fields with valid values."""
    valid_verdicts = {"match", "partial_match", "novel_valid", "no_match"}
    valid_confidences = {"high", "medium", "low"}

    verdict = data.get("verdict")
    confidence = data.get("confidence")

    if verdict not in valid_verdicts:
        return False
    if confidence not in valid_confidences:
        return False
    return True


def _build_grader_result(data: dict, finding: Finding) -> GraderResult:
    """Build a GraderResult from the parsed and validated response dict."""
    verdict = GraderVerdict(data["verdict"])
    confidence = GraderConfidence(data["confidence"])
    matched_id = data.get("matched_expected_id")
    reasoning = data.get("reasoning")

    # Enforce: novel_valid and no_match must not have matched_expected_id
    if verdict in (GraderVerdict.NOVEL_VALID, GraderVerdict.NO_MATCH):
        matched_id = None

    return GraderResult(
        tier=2,
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        matched_expected_id=matched_id,
        actual_finding_id=finding.finding_id,
    )


def _grading_error(finding: Finding, reasoning: str) -> GraderResult:
    """Build a grading_error result for infrastructure failures."""
    return GraderResult(
        tier=2,
        verdict=GraderVerdict.GRADING_ERROR,
        confidence=GraderConfidence.LOW,
        reasoning=reasoning,
        matched_expected_id=None,
        actual_finding_id=finding.finding_id,
    )


def _extract_response_text(response: object) -> str:
    """Pull the first text block out of an Anthropic message response."""
    content = getattr(response, "content", None)
    if not content:
        raise ValueError("Anthropic response has no content")
    text = getattr(content[0], "text", None)
    if not isinstance(text, str):
        raise ValueError(f"Anthropic response content[0] has no text: {content[0]!r}")
    return text


def _is_retryable_status(exc: anthropic.APIStatusError) -> bool:
    """Return True if an APIStatusError status code should trigger backoff."""
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    return status in _RETRYABLE_STATUS_CODES


def _build_anthropic_client() -> anthropic.AsyncAnthropic:
    """Construct an AsyncAnthropic client, raising on missing credentials.

    Some SDK versions raise AuthenticationError at construction when the
    API key is missing; others defer until the first request. We surface
    both as ``MissingGraderCredentialError`` — distinct from ValueError so
    the pipeline does not downgrade the auth failure into a per-finding
    GRADING_ERROR (see F10 / eval-cli.md:84-90).
    """
    try:
        return anthropic.AsyncAnthropic()
    except anthropic.AuthenticationError as exc:
        raise MissingGraderCredentialError(
            "ANTHROPIC_API_KEY is not set. "
            "Set the environment variable before running the eval harness."
        ) from exc


async def grade_finding(
    finding: Finding,
    expected_findings: list[ExpectedFinding],
    case_description: str,
    grader_model: str = DEFAULT_GRADER_MODEL,
    prompt_template: str | None = None,
    rubric: str | None = None,
    few_shot_examples: list[dict] | None = None,
    max_retries: int = 3,
) -> GraderResult:
    """Grade a finding using LLM-as-Judge (Tier 2).

    Called only for findings that did NOT match in Tier 1.
    Always returns a GraderResult (never None).
    On API failure after retries: returns GraderResult(verdict="grading_error").
    """
    prompt = build_grader_prompt(
        finding=finding,
        expected_findings=expected_findings,
        case_description=case_description,
        prompt_template=prompt_template,
        rubric=rubric,
        few_shot_examples=few_shot_examples,
    )

    client = _build_anthropic_client()

    response_text: str | None = None
    last_error: str | None = None

    for attempt in range(max_retries):
        try:
            response = await client.messages.create(
                model=grader_model,
                max_tokens=512,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = _extract_response_text(response)
            break
        except anthropic.RateLimitError as exc:
            wait_time = 2 ** attempt
            logger.warning(
                "Rate limited (attempt %d/%d), waiting %ds: %s",
                attempt + 1, max_retries, wait_time, exc,
            )
            last_error = str(exc)
            await asyncio.sleep(wait_time)
        except anthropic.APIStatusError as exc:
            last_error = str(exc)
            if not _is_retryable_status(exc):
                logger.error(
                    "Non-retryable API error (attempt %d/%d): %s",
                    attempt + 1, max_retries, exc,
                )
                break
            logger.warning(
                "Retryable API error (attempt %d/%d): %s",
                attempt + 1, max_retries, exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    if response_text is None:
        return _grading_error(
            finding,
            f"API error after {max_retries} retries: {last_error}",
        )

    parsed = _parse_grader_response(response_text)
    if parsed is not None and _validate_grader_response(parsed):
        return _build_grader_result(parsed, finding)

    logger.info("Invalid JSON response, re-prompting once")
    try:
        retry_response = await client.messages.create(
            model=grader_model,
            max_tokens=512,
            temperature=0,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text},
                {
                    "role": "user",
                    "content": "Respond with ONLY valid JSON. "
                    "No markdown, no explanation outside the JSON object.",
                },
            ],
        )
        retry_text = _extract_response_text(retry_response)
        retry_parsed = _parse_grader_response(retry_text)
        if retry_parsed is not None and _validate_grader_response(retry_parsed):
            return _build_grader_result(retry_parsed, finding)
    except asyncio.CancelledError:
        raise
    except (anthropic.APIError, ValueError) as exc:
        logger.warning("Re-prompt attempt failed: %s", exc)

    return _grading_error(finding, "Invalid grader response after retry")
