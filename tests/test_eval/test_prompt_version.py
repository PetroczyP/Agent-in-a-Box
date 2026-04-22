"""RED tests for prompt version manager (T008).

Tests VERSION.lock workflow: hash computation, clean/dirty detection,
consistency check recording, and prompt acceptance with .accepted/ copies.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from eval.prompt_version import (
    PromptDirtyError,
    accept_prompt,
    check_prompt_version,
    compute_prompt_hash,
    load_accepted_prompt_files,
    load_current_prompt_files,
    record_flip_rate,
    run_consistency_check,
    run_full_consistency_check,
)


# --- Fixtures ---


TEMPLATE_CONTENT = "You are a code review grader.\nEvaluate the finding.\n"
RUBRIC_CONTENT = "# Rubric\n\n- Match: same rule, same file, same line\n"
EXAMPLES_CONTENT = json.dumps(
    [{"input": "example1", "output": "match"}], indent=2
)


@pytest.fixture
def grader_dir(tmp_path: Path) -> Path:
    """Create a grader directory with the three prompt files."""
    d = tmp_path / "grader"
    d.mkdir()
    (d / "prompt_template.txt").write_text(TEMPLATE_CONTENT, encoding="utf-8")
    (d / "rubric.md").write_text(RUBRIC_CONTENT, encoding="utf-8")
    (d / "few_shot_examples.json").write_text(EXAMPLES_CONTENT, encoding="utf-8")
    return d


@pytest.fixture
def expected_hash() -> str:
    """The SHA-256 hash of the concatenated prompt files (first 12 hex chars)."""
    combined = TEMPLATE_CONTENT + RUBRIC_CONTENT + EXAMPLES_CONTENT
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:12]


# --- Hash computation ---


class TestComputePromptHash:
    def test_returns_first_12_hex_chars(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        result = compute_prompt_hash(grader_dir)
        assert result == expected_hash
        assert len(result) == 12

    def test_concatenation_order_matters(self, grader_dir: Path) -> None:
        """Hash must be template + rubric + examples, not any other order."""
        # Compute with the correct order
        correct = compute_prompt_hash(grader_dir)

        # Now swap template and rubric content
        (grader_dir / "prompt_template.txt").write_text(
            RUBRIC_CONTENT, encoding="utf-8"
        )
        (grader_dir / "rubric.md").write_text(TEMPLATE_CONTENT, encoding="utf-8")
        swapped = compute_prompt_hash(grader_dir)

        assert correct != swapped

    def test_hash_changes_on_content_change(self, grader_dir: Path) -> None:
        original = compute_prompt_hash(grader_dir)
        (grader_dir / "rubric.md").write_text("changed rubric", encoding="utf-8")
        changed = compute_prompt_hash(grader_dir)
        assert original != changed


# --- Clean state ---


class TestCheckPromptVersionClean:
    def test_clean_state_returns_hash(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """Hash matches VERSION.lock -> returns hash."""
        lock = {
            "hash": expected_hash,
            "accepted_at": "2026-03-31T14:00:00Z",
            "checked_hash": None,
            "checked_at": None,
            "flip_rate": None,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        result = check_prompt_version(grader_dir)
        assert result == expected_hash


# --- Dirty state ---


class TestCheckPromptVersionDirty:
    def test_dirty_state_raises_prompt_dirty_error(
        self, grader_dir: Path
    ) -> None:
        """Hash differs from VERSION.lock -> raises PromptDirtyError."""
        lock = {
            "hash": "stale_hash_00",
            "accepted_at": "2026-03-31T14:00:00Z",
            "checked_hash": None,
            "checked_at": None,
            "flip_rate": None,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        with pytest.raises(PromptDirtyError) as exc_info:
            check_prompt_version(grader_dir)

        # Error message should mention old and new hashes
        msg = str(exc_info.value)
        assert "stale_hash_00" in msg
        assert compute_prompt_hash(grader_dir) in msg


# --- First-time setup (auto-initialize) ---


class TestCheckPromptVersionFirstTime:
    def test_no_lock_file_auto_initializes(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """No VERSION.lock -> auto-initialize: create lock + .accepted/."""
        assert not (grader_dir / "VERSION.lock").exists()

        result = check_prompt_version(grader_dir)
        assert result == expected_hash

        # VERSION.lock created
        lock_path = grader_dir / "VERSION.lock"
        assert lock_path.exists()
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        assert lock["hash"] == expected_hash
        assert lock["accepted_at"] is not None
        assert lock["checked_hash"] is None
        assert lock["checked_at"] is None
        assert lock["flip_rate"] is None

    def test_first_time_copies_to_accepted(
        self, grader_dir: Path
    ) -> None:
        """Auto-initialize creates .accepted/ with copies of prompt files."""
        check_prompt_version(grader_dir)

        accepted = grader_dir / ".accepted"
        assert accepted.is_dir()
        assert (accepted / "prompt_template.txt").read_text(
            encoding="utf-8"
        ) == TEMPLATE_CONTENT
        assert (accepted / "rubric.md").read_text(
            encoding="utf-8"
        ) == RUBRIC_CONTENT
        assert (accepted / "few_shot_examples.json").read_text(
            encoding="utf-8"
        ) == EXAMPLES_CONTENT


# --- Consistency check ---


class TestRunConsistencyCheck:
    def test_writes_checked_hash_and_timestamp(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """run_consistency_check records checked_hash and checked_at."""
        # Set up a VERSION.lock first
        lock = {
            "hash": expected_hash,
            "accepted_at": "2026-03-31T14:00:00Z",
            "checked_hash": None,
            "checked_at": None,
            "flip_rate": None,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        run_consistency_check(grader_dir, expected_hash)

        updated = json.loads(
            (grader_dir / "VERSION.lock").read_text(encoding="utf-8")
        )
        assert updated["checked_hash"] == expected_hash
        assert updated["checked_at"] is not None
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(updated["checked_at"])

    def test_preserves_existing_lock_fields(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """Other VERSION.lock fields remain unchanged."""
        lock = {
            "hash": expected_hash,
            "accepted_at": "2026-03-31T14:00:00Z",
            "checked_hash": None,
            "checked_at": None,
            "flip_rate": None,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        run_consistency_check(grader_dir, expected_hash)

        updated = json.loads(
            (grader_dir / "VERSION.lock").read_text(encoding="utf-8")
        )
        assert updated["hash"] == expected_hash
        assert updated["accepted_at"] == "2026-03-31T14:00:00Z"
        assert updated["flip_rate"] is None


# --- Accept prompt ---


class TestAcceptPrompt:
    def test_accept_with_valid_checked_hash(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """accept_prompt with matching checked_hash -> success."""
        lock = {
            "hash": "old_hash_0000",
            "accepted_at": "2026-03-30T10:00:00Z",
            "checked_hash": expected_hash,
            "checked_at": "2026-03-31T14:00:00Z",
            "flip_rate": 0.05,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        result = accept_prompt(grader_dir)
        assert result == expected_hash

    def test_accept_updates_version_lock(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """accept_prompt updates hash and clears checked fields."""
        lock = {
            "hash": "old_hash_0000",
            "accepted_at": "2026-03-30T10:00:00Z",
            "checked_hash": expected_hash,
            "checked_at": "2026-03-31T14:00:00Z",
            "flip_rate": 0.05,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        accept_prompt(grader_dir)

        updated = json.loads(
            (grader_dir / "VERSION.lock").read_text(encoding="utf-8")
        )
        assert updated["hash"] == expected_hash
        assert updated["accepted_at"] is not None
        # accepted_at should be updated (different from the old one)
        assert updated["accepted_at"] != "2026-03-30T10:00:00Z"
        # Checked fields must be cleared
        assert updated["checked_hash"] is None
        assert updated["checked_at"] is None
        assert updated["flip_rate"] is None

    def test_accept_copies_files_to_accepted(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """accept_prompt copies current prompt files to .accepted/."""
        lock = {
            "hash": "old_hash_0000",
            "accepted_at": "2026-03-30T10:00:00Z",
            "checked_hash": expected_hash,
            "checked_at": "2026-03-31T14:00:00Z",
            "flip_rate": 0.05,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        accept_prompt(grader_dir)

        accepted = grader_dir / ".accepted"
        assert accepted.is_dir()
        assert (accepted / "prompt_template.txt").read_text(
            encoding="utf-8"
        ) == TEMPLATE_CONTENT
        assert (accepted / "rubric.md").read_text(
            encoding="utf-8"
        ) == RUBRIC_CONTENT
        assert (accepted / "few_shot_examples.json").read_text(
            encoding="utf-8"
        ) == EXAMPLES_CONTENT

    def test_accept_overwrites_old_accepted(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """accept_prompt overwrites existing .accepted/ files."""
        # Create old .accepted/ with stale content
        accepted = grader_dir / ".accepted"
        accepted.mkdir()
        (accepted / "prompt_template.txt").write_text(
            "old template", encoding="utf-8"
        )

        lock = {
            "hash": "old_hash_0000",
            "accepted_at": "2026-03-30T10:00:00Z",
            "checked_hash": expected_hash,
            "checked_at": "2026-03-31T14:00:00Z",
            "flip_rate": 0.05,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        accept_prompt(grader_dir)

        assert (accepted / "prompt_template.txt").read_text(
            encoding="utf-8"
        ) == TEMPLATE_CONTENT

    def test_accept_with_stale_checked_hash_raises(
        self, grader_dir: Path
    ) -> None:
        """accept_prompt with checked_hash != current computed hash -> ValueError."""
        lock = {
            "hash": "old_hash_0000",
            "accepted_at": "2026-03-30T10:00:00Z",
            "checked_hash": "stale_check0",
            "checked_at": "2026-03-31T14:00:00Z",
            "flip_rate": 0.05,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        with pytest.raises(ValueError, match="consistency check"):
            accept_prompt(grader_dir)

    def test_accept_with_null_checked_hash_raises(
        self, grader_dir: Path
    ) -> None:
        """accept_prompt with checked_hash=null -> ValueError."""
        lock = {
            "hash": "old_hash_0000",
            "accepted_at": "2026-03-30T10:00:00Z",
            "checked_hash": None,
            "checked_at": None,
            "flip_rate": None,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        with pytest.raises(ValueError, match="consistency check"):
            accept_prompt(grader_dir)


# --- Record flip rate ---


class TestRecordFlipRate:
    def test_writes_flip_rate_to_lock(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        """record_flip_rate updates only the flip_rate field."""
        lock = {
            "hash": expected_hash,
            "accepted_at": "2026-03-31T14:00:00Z",
            "checked_hash": expected_hash,
            "checked_at": "2026-03-31T15:00:00Z",
            "flip_rate": None,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        record_flip_rate(grader_dir, 0.12)

        updated = json.loads(
            (grader_dir / "VERSION.lock").read_text(encoding="utf-8")
        )
        assert updated["flip_rate"] == pytest.approx(0.12)
        # Other fields unchanged
        assert updated["hash"] == expected_hash
        assert updated["checked_hash"] == expected_hash

    def test_overwrites_existing_flip_rate(
        self, grader_dir: Path, expected_hash: str
    ) -> None:
        lock = {
            "hash": expected_hash,
            "accepted_at": "2026-03-31T14:00:00Z",
            "checked_hash": expected_hash,
            "checked_at": "2026-03-31T15:00:00Z",
            "flip_rate": 0.5,
        }
        (grader_dir / "VERSION.lock").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        record_flip_rate(grader_dir, 0.02)

        updated = json.loads(
            (grader_dir / "VERSION.lock").read_text(encoding="utf-8")
        )
        assert updated["flip_rate"] == pytest.approx(0.02)


# --- Load prompt files ---


class TestLoadPromptFiles:
    def test_load_accepted_returns_files(self, grader_dir: Path) -> None:
        """load_accepted_prompt_files returns contents from .accepted/."""
        accepted = grader_dir / ".accepted"
        accepted.mkdir()
        (accepted / "prompt_template.txt").write_text("old template", encoding="utf-8")
        (accepted / "rubric.md").write_text("old rubric", encoding="utf-8")
        (accepted / "few_shot_examples.json").write_text(
            json.dumps([{"a": 1}]), encoding="utf-8"
        )

        template, rubric, examples = load_accepted_prompt_files(grader_dir)
        assert template == "old template"
        assert rubric == "old rubric"
        assert examples == [{"a": 1}]

    def test_load_accepted_returns_none_when_no_dir(
        self, grader_dir: Path
    ) -> None:
        """load_accepted_prompt_files returns (None, None, None) if no .accepted/."""
        template, rubric, examples = load_accepted_prompt_files(grader_dir)
        assert template is None
        assert rubric is None
        assert examples is None

    def test_load_current_returns_files(self, grader_dir: Path) -> None:
        """load_current_prompt_files returns contents from grader_dir."""
        template, rubric, examples = load_current_prompt_files(grader_dir)
        assert template == TEMPLATE_CONTENT
        assert rubric == RUBRIC_CONTENT
        assert examples == json.loads(EXAMPLES_CONTENT)


# --- Full consistency check ---


class TestRunFullConsistencyCheck:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_accepted_dir(
        self, grader_dir: Path
    ) -> None:
        """First run (no .accepted/) returns 0.0 flip rate."""
        from eval.models import (
            ExpectedFinding,
            GoldenCase,
            GoldenCaseSource,
        )
        from server.models import Category, ReviewBundle, Severity

        case = GoldenCase(
            case_id="c1",
            description="test case",
            source=GoldenCaseSource.HAND_CURATED,
            tags=["test"],
            bundle=ReviewBundle(diff="diff", files={"a.py": "code"}),
            expected_findings=[
                ExpectedFinding(
                    expected_id="EF-001",
                    rule_id="R001",
                    severity=Severity.BUG,
                    category=Category.SECURITY,
                    file="a.py",
                    approximate_line=1,
                    description="A bug",
                ),
            ],
        )

        rate = await run_full_consistency_check(
            cases=[case], grader_dir=grader_dir
        )
        assert rate == 0.0

    @pytest.mark.asyncio
    async def test_no_flips_returns_zero(self, grader_dir: Path) -> None:
        """When old and new verdicts agree, flip_rate is 0.0."""
        from unittest.mock import AsyncMock, patch

        from eval.models import (
            ExpectedFinding,
            GoldenCase,
            GoldenCaseSource,
            GraderConfidence,
            GraderResult,
            GraderVerdict,
        )
        from server.models import Category, ReviewBundle, Severity

        # Set up .accepted/ so we don't short-circuit
        accepted = grader_dir / ".accepted"
        accepted.mkdir()
        (accepted / "prompt_template.txt").write_text(
            TEMPLATE_CONTENT, encoding="utf-8"
        )
        (accepted / "rubric.md").write_text(RUBRIC_CONTENT, encoding="utf-8")
        (accepted / "few_shot_examples.json").write_text(
            EXAMPLES_CONTENT, encoding="utf-8"
        )

        case = GoldenCase(
            case_id="c1",
            description="test case",
            source=GoldenCaseSource.HAND_CURATED,
            tags=["test"],
            bundle=ReviewBundle(diff="diff", files={"a.py": "code"}),
            expected_findings=[
                ExpectedFinding(
                    expected_id="EF-001",
                    rule_id="R001",
                    severity=Severity.BUG,
                    category=Category.SECURITY,
                    file="a.py",
                    approximate_line=1,
                    description="A bug",
                ),
            ],
        )

        same_result = GraderResult(
            tier=2,
            verdict=GraderVerdict.MATCH,
            actual_finding_id="synth-EF-001",
            matched_expected_id="EF-001",
            confidence=GraderConfidence.HIGH,
            reasoning="Matched",
        )

        mock_grade = AsyncMock(return_value=same_result)

        with patch(
            "eval.graders.model_grader.grade_finding", mock_grade
        ):
            rate = await run_full_consistency_check(
                cases=[case], grader_dir=grader_dir
            )

        assert rate == 0.0
        # Called twice per expected finding + twice per noise finding:
        # 1 expected (old+new) + 1 generic noise (old+new) = 4 calls
        assert mock_grade.call_count == 4

    @pytest.mark.asyncio
    async def test_flip_detected(self, grader_dir: Path) -> None:
        """When old and new verdicts differ, flip_rate reflects the flip."""
        from unittest.mock import AsyncMock, patch

        from eval.models import (
            ExpectedFinding,
            GoldenCase,
            GoldenCaseSource,
            GraderConfidence,
            GraderResult,
            GraderVerdict,
        )
        from server.models import Category, ReviewBundle, Severity

        accepted = grader_dir / ".accepted"
        accepted.mkdir()
        (accepted / "prompt_template.txt").write_text(
            TEMPLATE_CONTENT, encoding="utf-8"
        )
        (accepted / "rubric.md").write_text(RUBRIC_CONTENT, encoding="utf-8")
        (accepted / "few_shot_examples.json").write_text(
            EXAMPLES_CONTENT, encoding="utf-8"
        )

        case = GoldenCase(
            case_id="c1",
            description="test",
            source=GoldenCaseSource.HAND_CURATED,
            tags=["test"],
            bundle=ReviewBundle(diff="d", files={"a.py": "c"}),
            expected_findings=[
                ExpectedFinding(
                    expected_id="EF-001",
                    rule_id="R001",
                    severity=Severity.BUG,
                    category=Category.SECURITY,
                    file="a.py",
                    approximate_line=1,
                    description="A bug",
                ),
                ExpectedFinding(
                    expected_id="EF-002",
                    rule_id="R002",
                    severity=Severity.WARN,
                    category=Category.CORRECTNESS,
                    file="b.py",
                    approximate_line=10,
                    description="A warning",
                ),
            ],
        )

        match_result = GraderResult(
            tier=2,
            verdict=GraderVerdict.MATCH,
            actual_finding_id="synth-EF-001",
            matched_expected_id="EF-001",
            confidence=GraderConfidence.HIGH,
            reasoning="Same",
        )
        no_match_result = GraderResult(
            tier=2,
            verdict=GraderVerdict.NO_MATCH,
            actual_finding_id="synth-EF-001",
            matched_expected_id=None,
            confidence=GraderConfidence.HIGH,
            reasoning="Different",
        )

        # EF-001: old=MATCH, new=MATCH (no flip)
        # EF-002: old=MATCH, new=NO_MATCH (flip!)
        # noise: old=NO_MATCH, new=NO_MATCH (no flip)
        mock_grade = AsyncMock(
            side_effect=[
                match_result, match_result,          # EF-001: old, new
                match_result, no_match_result,       # EF-002: old, new
                no_match_result, no_match_result,    # noise: old, new
            ]
        )

        with patch(
            "eval.graders.model_grader.grade_finding", mock_grade
        ):
            rate = await run_full_consistency_check(
                cases=[case], grader_dir=grader_dir
            )

        # 1 flip out of 3 comparisons (2 expected + 1 noise) = 1/3
        assert rate == pytest.approx(1.0 / 3.0)
        assert mock_grade.call_count == 6


# ===========================================================================
# TestConsistencyCheckNoiseFindings (M-2)
# ===========================================================================


class TestConsistencyCheckNoiseFindings:
    """Consistency check must include synthetic noise findings to exercise
    the novel_valid vs no_match grading boundary."""

    @pytest.mark.asyncio
    async def test_clean_code_cases_contribute_noise_comparisons(
        self, grader_dir: Path
    ) -> None:
        """Clean-code cases (no expected findings) must still generate
        noise finding comparisons."""
        from unittest.mock import AsyncMock, patch

        from eval.models import (
            GoldenCase,
            GoldenCaseSource,
            GraderConfidence,
            GraderResult,
            GraderVerdict,
        )
        from server.models import ReviewBundle

        accepted = grader_dir / ".accepted"
        accepted.mkdir()
        (accepted / "prompt_template.txt").write_text(
            TEMPLATE_CONTENT, encoding="utf-8"
        )
        (accepted / "rubric.md").write_text(RUBRIC_CONTENT, encoding="utf-8")
        (accepted / "few_shot_examples.json").write_text(
            EXAMPLES_CONTENT, encoding="utf-8"
        )

        # Clean-code case: no expected findings
        clean_case = GoldenCase(
            case_id="clean-001",
            description="Clean code, no issues",
            source=GoldenCaseSource.HAND_CURATED,
            tags=["clean"],
            bundle=ReviewBundle(diff="d", files={"a.py": "c"}),
            expected_findings=[],
            expected_non_findings=["sql-injection"],
        )

        same_result = GraderResult(
            tier=2,
            verdict=GraderVerdict.NO_MATCH,
            actual_finding_id="noise-clean-001-0",
            matched_expected_id=None,
            confidence=GraderConfidence.HIGH,
            reasoning="Noise",
        )

        mock_grade = AsyncMock(return_value=same_result)

        with patch(
            "eval.graders.model_grader.grade_finding", mock_grade
        ):
            rate = await run_full_consistency_check(
                cases=[clean_case], grader_dir=grader_dir
            )

        # Clean-code case should trigger at least 1 noise comparison
        assert mock_grade.call_count >= 2  # old + new for at least 1 noise finding

    @pytest.mark.asyncio
    async def test_noise_flip_detected_on_non_clean_case(
        self, grader_dir: Path
    ) -> None:
        """A prompt change that flips a noise finding verdict should be caught."""
        from unittest.mock import AsyncMock, patch

        from eval.models import (
            ExpectedFinding,
            GoldenCase,
            GoldenCaseSource,
            GraderConfidence,
            GraderResult,
            GraderVerdict,
        )
        from server.models import Category, ReviewBundle, Severity

        accepted = grader_dir / ".accepted"
        accepted.mkdir()
        (accepted / "prompt_template.txt").write_text(
            TEMPLATE_CONTENT, encoding="utf-8"
        )
        (accepted / "rubric.md").write_text(RUBRIC_CONTENT, encoding="utf-8")
        (accepted / "few_shot_examples.json").write_text(
            EXAMPLES_CONTENT, encoding="utf-8"
        )

        case = GoldenCase(
            case_id="c1",
            description="test case with noise",
            source=GoldenCaseSource.HAND_CURATED,
            tags=["test"],
            bundle=ReviewBundle(diff="d", files={"a.py": "c"}),
            expected_findings=[
                ExpectedFinding(
                    expected_id="EF-001",
                    rule_id="R001",
                    severity=Severity.BUG,
                    category=Category.SECURITY,
                    file="a.py",
                    approximate_line=1,
                    description="A real bug",
                ),
            ],
        )

        # Expected finding: stable (no flip)
        match_result = GraderResult(
            tier=2,
            verdict=GraderVerdict.MATCH,
            actual_finding_id="synth-EF-001",
            matched_expected_id="EF-001",
            confidence=GraderConfidence.HIGH,
            reasoning="Same",
        )
        # Noise finding: old=no_match, new=novel_valid (flip!)
        noise_old = GraderResult(
            tier=2,
            verdict=GraderVerdict.NO_MATCH,
            actual_finding_id="noise-c1-0",
            matched_expected_id=None,
            confidence=GraderConfidence.HIGH,
            reasoning="Noise before",
        )
        noise_new = GraderResult(
            tier=2,
            verdict=GraderVerdict.NOVEL_VALID,
            actual_finding_id="noise-c1-0",
            matched_expected_id=None,
            confidence=GraderConfidence.HIGH,
            reasoning="Noise after",
        )

        # Order: expected_old, expected_new, noise_old, noise_new
        mock_grade = AsyncMock(
            side_effect=[
                match_result, match_result,  # expected finding: no flip
                noise_old, noise_new,        # noise finding: flip!
            ]
        )

        with patch(
            "eval.graders.model_grader.grade_finding", mock_grade
        ):
            rate = await run_full_consistency_check(
                cases=[case], grader_dir=grader_dir
            )

        # 1 flip out of 2 comparisons (1 expected + 1 noise) = 0.5
        assert rate == pytest.approx(0.5)
        assert mock_grade.call_count == 4
