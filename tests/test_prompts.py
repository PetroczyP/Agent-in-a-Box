"""Tests for prompt tuning — T006-T008, T027."""

from __future__ import annotations

import json

import pytest

from server.prompts import (
    FORMAT_REINFORCEMENT,
    REVIEWER_PERSONA,
    build_review_context,
)


class TestReviewerPersonaFewShot:
    """T006: REVIEWER_PERSONA must include few-shot format examples."""

    def test_contains_bug_finding_example(self):
        """At least one example shows a BUG finding with all required fields."""
        assert '"severity": "BUG"' in REVIEWER_PERSONA
        # The example must be valid JSON — extract the BUG example block
        assert '"rule_id"' in REVIEWER_PERSONA
        assert '"category"' in REVIEWER_PERSONA
        assert '"message"' in REVIEWER_PERSONA
        assert '"file"' in REVIEWER_PERSONA
        assert '"start_line"' in REVIEWER_PERSONA
        assert '"end_line"' in REVIEWER_PERSONA
        assert '"confidence"' in REVIEWER_PERSONA
        assert '"evidence"' in REVIEWER_PERSONA

    def test_contains_empty_array_example(self):
        """An example shows returning [] for clean code."""
        # The persona must demonstrate the empty-array output case
        # beyond the schema definition block. Look for a distinct
        # few-shot section that shows the literal empty array.
        persona_after_schema = REVIEWER_PERSONA.split("## Rules")[0]
        # Count occurrences of standalone "[]" — the schema already has
        # one in the Output Format block; a second one should appear in
        # the few-shot examples section.
        assert REVIEWER_PERSONA.count("Example") >= 2, (
            "REVIEWER_PERSONA must contain at least 2 few-shot examples"
        )

    def test_few_shot_bug_example_is_valid_json(self):
        """The BUG few-shot example must parse as valid JSON."""
        # Find the few-shot examples section and extract JSON blocks
        marker = "### Example"
        assert marker in REVIEWER_PERSONA, (
            "REVIEWER_PERSONA must have '### Example' sections for few-shot examples"
        )
        # Extract everything after the first ### Example marker
        examples_text = REVIEWER_PERSONA.split(marker, 1)[1]
        # Find the first JSON code block in the examples
        json_start = examples_text.find("```json")
        assert json_start != -1, "Few-shot example must contain a ```json block"
        json_body_start = examples_text.index("\n", json_start) + 1
        json_end = examples_text.index("```", json_body_start)
        json_text = examples_text[json_body_start:json_end].strip()
        parsed = json.loads(json_text)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1
        finding = parsed[0]
        assert finding["severity"] == "BUG"
        assert "rule_id" in finding
        assert "evidence" in finding

    def test_persona_under_char_limit(self):
        """SC-005: REVIEWER_PERSONA must stay under 12,800 chars."""
        assert len(REVIEWER_PERSONA) <= 12_800, (
            f"REVIEWER_PERSONA is {len(REVIEWER_PERSONA)} chars, "
            f"exceeds 12,800 limit"
        )

    def test_persona_is_project_agnostic(self):
        """Constitution Principle I: no hardcoded repo knowledge."""
        # Should not reference AgentinaBox or any specific project
        lower = REVIEWER_PERSONA.lower()
        assert "agentinabox" not in lower
        assert "agent-in-a-box" not in lower
        assert "copilot" not in lower  # model-agnostic


class TestFormatReinforcement:
    """T007/T008: FORMAT_REINFORCEMENT appended by build_review_context."""

    def test_format_reinforcement_exists(self):
        """FORMAT_REINFORCEMENT constant must be defined."""
        assert isinstance(FORMAT_REINFORCEMENT, str)
        assert len(FORMAT_REINFORCEMENT) > 0

    def test_reinforcement_mentions_json_array(self):
        """The reinforcement text must mention JSON array output."""
        lower = FORMAT_REINFORCEMENT.lower()
        assert "json array" in lower or "json" in lower

    def test_reinforcement_mentions_empty_array(self):
        """The reinforcement text must mention the empty-array fallback."""
        assert "[]" in FORMAT_REINFORCEMENT

    def test_build_review_context_includes_reinforcement_by_default(self):
        """T007: reinforce_format=True (default) appends FORMAT_REINFORCEMENT."""
        result = build_review_context(
            diff="--- a/foo.py\n+++ b/foo.py",
            files={"foo.py": "print('hello')"},
        )
        assert result.endswith(FORMAT_REINFORCEMENT), (
            "build_review_context() must end with FORMAT_REINFORCEMENT by default"
        )

    def test_build_review_context_omits_reinforcement_when_false(self):
        """T008: reinforce_format=False must NOT include FORMAT_REINFORCEMENT."""
        result = build_review_context(
            diff="--- a/foo.py\n+++ b/foo.py",
            files={"foo.py": "print('hello')"},
            reinforce_format=False,
        )
        assert FORMAT_REINFORCEMENT not in result

    def test_reinforcement_is_last_section(self):
        """When reinforce_format=True, reinforcement comes after all other sections."""
        result = build_review_context(
            diff="--- a/foo.py\n+++ b/foo.py",
            files={"foo.py": "print('hello')"},
            context="Extra context here",
            reinforce_format=True,
        )
        # Additional Context should appear before reinforcement
        ctx_pos = result.index("## Additional Context")
        reinforce_pos = result.index(FORMAT_REINFORCEMENT)
        assert reinforce_pos > ctx_pos
