"""Grading pipeline: Tier 1 -> Tier 2 routing.

For each finding, tries the deterministic fingerprint grader first.
Only forwards to the model-based grader when Tier 1 returns no match.
Tracks claimed expected IDs to prevent double-counting.
"""

from __future__ import annotations

import asyncio
import logging

import anthropic

from eval.graders import DEFAULT_GRADER_MODEL
from eval.graders.fingerprint import grade_finding as fingerprint_grade
from eval.graders.model_grader import grade_finding as model_grade
from eval.models import (
    ExpectedFinding,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
)
from server.models import Finding

logger = logging.getLogger(__name__)


async def grade_all_findings(
    findings: list[Finding],
    expected_findings: list[ExpectedFinding],
    case_description: str,
    grader_model: str = DEFAULT_GRADER_MODEL,
    line_tolerance: int = 5,
    prompt_template: str | None = None,
    rubric: str | None = None,
    few_shot_examples: list[dict] | None = None,
    max_retries: int = 3,
) -> list[GraderResult]:
    """Grade all findings through the two-tier pipeline.

    For each finding:
    1. Try Tier 1 (fingerprint match)
    2. If no match, forward to Tier 2 (model-based)

    Tracks claimed expected IDs to prevent double-counting.
    Returns one GraderResult per finding (same order as input).
    """
    claimed_expected_ids: set[str] = set()
    results: list[GraderResult] = []

    for finding in findings:
        tier1_result = fingerprint_grade(
            finding=finding,
            expected_findings=expected_findings,
            line_tolerance=line_tolerance,
            claimed_expected_ids=claimed_expected_ids,
        )

        if tier1_result is not None:
            results.append(tier1_result)
            continue

        unclaimed_expected = [
            ef for ef in expected_findings
            if ef.expected_id not in claimed_expected_ids
        ]

        try:
            tier2_result = await model_grade(
                finding=finding,
                expected_findings=unclaimed_expected,
                case_description=case_description,
                grader_model=grader_model,
                prompt_template=prompt_template,
                rubric=rubric,
                few_shot_examples=few_shot_examples,
                max_retries=max_retries,
            )
            results.append(tier2_result)
            if (
                tier2_result.verdict
                in (GraderVerdict.MATCH, GraderVerdict.PARTIAL_MATCH)
                and tier2_result.matched_expected_id is not None
            ):
                claimed_expected_ids.add(tier2_result.matched_expected_id)
        except asyncio.CancelledError:
            raise
        except (anthropic.APIError, ValueError, RuntimeError) as exc:
            logger.warning(
                "Tier 2 grading failed for finding %s: %s",
                finding.finding_id, exc,
            )
            results.append(
                GraderResult(
                    tier=2,
                    verdict=GraderVerdict.GRADING_ERROR,
                    confidence=GraderConfidence.LOW,
                    reasoning=f"Tier 2 error: {exc}",
                    matched_expected_id=None,
                    actual_finding_id=finding.finding_id,
                )
            )

    return results
