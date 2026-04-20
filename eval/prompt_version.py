"""Prompt version manager for the eval harness.

Manages the grader prompt versioning workflow:
- Computes SHA-256 hash of prompt files (template + rubric + examples)
- Detects dirty state (prompt changed but not accepted)
- Runs consistency check: grades findings with old vs new prompts
- Records flip_rate and per-finding diffs
- Accepts new prompt baseline with .accepted/ copies

VERSION.lock format:
{
    "hash": "a1b2c3d4e5f6",
    "accepted_at": "2026-03-31T14:00:00Z",
    "checked_hash": null,
    "checked_at": null,
    "flip_rate": null
}
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eval.models import ExpectedFinding, GoldenCase, GraderResult

# Prompt files read in fixed order for deterministic hashing.
PROMPT_FILES = ("prompt_template.txt", "rubric.md", "few_shot_examples.json")


class PromptDirtyError(Exception):
    """Raised when the grader prompt has changed but hasn't been accepted."""

    pass


def compute_prompt_hash(grader_dir: Path) -> str:
    """Compute SHA-256 hash of prompt files.

    Reads prompt_template.txt, rubric.md, and few_shot_examples.json
    as UTF-8 text, concatenates in that fixed order, and returns the
    first 12 characters of the hex digest.
    """
    combined = ""
    for filename in PROMPT_FILES:
        combined += (grader_dir / filename).read_text(encoding="utf-8")
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:12]


def _read_lock(grader_dir: Path) -> dict:
    """Read VERSION.lock as a dict."""
    return json.loads(
        (grader_dir / "VERSION.lock").read_text(encoding="utf-8")
    )


def _write_lock(grader_dir: Path, lock: dict) -> None:
    """Write VERSION.lock as pretty-printed JSON."""
    (grader_dir / "VERSION.lock").write_text(
        json.dumps(lock, indent=2) + "\n", encoding="utf-8"
    )


def _copy_prompt_files_to_accepted(grader_dir: Path) -> None:
    """Copy the three prompt files into .accepted/ directory."""
    accepted = grader_dir / ".accepted"
    accepted.mkdir(exist_ok=True)
    for filename in PROMPT_FILES:
        shutil.copy2(grader_dir / filename, accepted / filename)


def _initialize_lock(grader_dir: Path, prompt_hash: str) -> None:
    """Create VERSION.lock and .accepted/ for the first time."""
    lock = {
        "hash": prompt_hash,
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "checked_hash": None,
        "checked_at": None,
        "flip_rate": None,
    }
    _write_lock(grader_dir, lock)
    _copy_prompt_files_to_accepted(grader_dir)


def check_prompt_version(grader_dir: Path) -> str:
    """Check if grader prompt is clean (matches VERSION.lock).

    Returns the prompt hash if clean.
    Raises PromptDirtyError if hash doesn't match.
    Auto-initializes VERSION.lock on first run (no lock file exists).
    """
    computed = compute_prompt_hash(grader_dir)
    lock_path = grader_dir / "VERSION.lock"

    if not lock_path.exists():
        _initialize_lock(grader_dir, computed)
        return computed

    lock = _read_lock(grader_dir)
    if lock["hash"] != computed:
        raise PromptDirtyError(
            f"Grader prompt has changed since last acceptance. "
            f"Locked hash: {lock['hash']}, current hash: {computed}. "
            f"Run a consistency check and then accept the prompt."
        )

    return computed


def run_consistency_check(grader_dir: Path, computed_hash: str) -> None:
    """Record that a consistency check has been performed.

    Writes checked_hash and checked_at to VERSION.lock.
    Called after run_full_consistency_check completes the actual comparison.
    """
    lock = _read_lock(grader_dir)
    lock["checked_hash"] = computed_hash
    lock["checked_at"] = datetime.now(timezone.utc).isoformat()
    _write_lock(grader_dir, lock)


def record_flip_rate(grader_dir: Path, flip_rate: float) -> None:
    """Write the measured flip_rate into VERSION.lock."""
    lock = _read_lock(grader_dir)
    lock["flip_rate"] = flip_rate
    _write_lock(grader_dir, lock)


def load_accepted_prompt_files(
    grader_dir: Path,
) -> tuple[str | None, str | None, list[dict] | None]:
    """Load the previously accepted prompt files from .accepted/.

    Returns (prompt_template, rubric, few_shot_examples).
    Returns (None, None, None) if .accepted/ doesn't exist.
    """
    accepted = grader_dir / ".accepted"
    if not accepted.is_dir():
        return None, None, None

    prompt_template = _read_optional_text(accepted / "prompt_template.txt")
    rubric = _read_optional_text(accepted / "rubric.md")
    few_shot_examples = _read_optional_json(accepted / "few_shot_examples.json")
    return prompt_template, rubric, few_shot_examples


def load_current_prompt_files(
    grader_dir: Path,
) -> tuple[str | None, str | None, list[dict] | None]:
    """Load the current (working) prompt files from grader_dir.

    Returns (prompt_template, rubric, few_shot_examples).
    """
    prompt_template = _read_optional_text(grader_dir / "prompt_template.txt")
    rubric = _read_optional_text(grader_dir / "rubric.md")
    few_shot_examples = _read_optional_json(grader_dir / "few_shot_examples.json")
    return prompt_template, rubric, few_shot_examples


def _read_optional_text(path: Path) -> str | None:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def _read_optional_json(path: Path) -> list[dict] | None:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _build_noise_findings(case: GoldenCase) -> list[Finding]:
    """Build synthetic noise findings for a golden case.

    Creates findings that should NOT match any expected finding — used to
    test the novel_valid / no_match grading boundary during consistency checks.

    - If the case has expected_non_findings, creates one noise finding per
      non-finding rule_id.
    - Otherwise, creates a single generic noise finding.

    Clean-code cases (empty expected_findings) always get at least one noise
    finding so they contribute to flip_rate measurement.
    """
    from server.models import Category, Finding, Location, Severity

    noise: list[Finding] = []
    # Determine a file from the case bundle for realistic location
    case_files = list(case.bundle.files.keys()) if case.bundle.files else ["unknown.py"]
    noise_file = case_files[0]

    if case.expected_non_findings:
        for i, rule_id in enumerate(case.expected_non_findings):
            noise.append(Finding(
                finding_id=f"noise-{case.case_id}-{i}",
                rule_id=rule_id,
                severity=Severity.WARN,
                category=Category.CORRECTNESS,
                message=f"Synthetic noise finding for rule {rule_id} — should not match any expected finding.",
                primary_location=Location(
                    file=noise_file,
                    start_line=1,
                    end_line=2,
                ),
                fingerprint=f"noise-fp-{case.case_id}-{i}",
                confidence="medium",
                evidence=f"Noise probe for consistency check (rule: {rule_id})",
            ))
    else:
        noise.append(Finding(
            finding_id=f"noise-{case.case_id}-0",
            rule_id="generic-noise",
            severity=Severity.NIT,
            category=Category.STYLE,
            message="Synthetic noise finding — generic probe that should not match any expected finding.",
            primary_location=Location(
                file=noise_file,
                start_line=1,
                end_line=2,
            ),
            fingerprint=f"noise-fp-{case.case_id}-0",
            confidence="low",
            evidence="Noise probe for consistency check",
        ))

    return noise


async def run_full_consistency_check(
    cases: list[GoldenCase],
    grader_dir: Path,
    grader_model: str | None = None,
    max_retries: int = 3,
    verbose: bool = False,
) -> float:
    """Run the full old-vs-new prompt consistency evaluation.

    For each golden case's expected findings:
    1. Constructs synthetic Finding objects from expected findings
    2. Grades each with old prompt (from .accepted/) -> verdict_old
    3. Grades each with new prompt (from working files) -> verdict_new
    4. Compares verdicts, reports flips

    Returns the flip_rate (0.0 to 1.0).
    """
    from eval.graders import DEFAULT_GRADER_MODEL
    from eval.graders.model_grader import grade_finding
    from eval.models import (
        ExpectedFinding,
        GraderVerdict,
    )
    from server.models import Category, Finding, Location, Severity

    if grader_model is None:
        grader_model = DEFAULT_GRADER_MODEL

    old_template, old_rubric, old_examples = load_accepted_prompt_files(grader_dir)
    new_template, new_rubric, new_examples = load_current_prompt_files(grader_dir)

    if old_template is None and old_rubric is None and old_examples is None:
        if verbose:
            print("No .accepted/ directory found — first consistency check.", file=sys.stderr)
        return 0.0

    total_comparisons = 0
    total_flips = 0
    flip_details: list[dict] = []

    for case in cases:
        # --- Grade expected findings (match/partial_match stability) ---
        for ef in case.expected_findings:
            synthetic = Finding(
                finding_id=f"synth-{ef.expected_id}",
                rule_id=ef.rule_id,
                severity=ef.severity,
                category=ef.category,
                message=ef.description,
                primary_location=Location(
                    file=ef.file,
                    start_line=ef.approximate_line,
                    end_line=ef.approximate_line + 1,
                ),
                fingerprint=f"synth-fp-{ef.expected_id}",
                confidence="high",
                evidence=ef.description,
            )

            old_result = await grade_finding(
                finding=synthetic,
                expected_findings=case.expected_findings,
                case_description=case.description,
                grader_model=grader_model,
                prompt_template=old_template,
                rubric=old_rubric,
                few_shot_examples=old_examples,
                max_retries=max_retries,
            )

            new_result = await grade_finding(
                finding=synthetic,
                expected_findings=case.expected_findings,
                case_description=case.description,
                grader_model=grader_model,
                prompt_template=new_template,
                rubric=new_rubric,
                few_shot_examples=new_examples,
                max_retries=max_retries,
            )

            total_comparisons += 1
            if old_result.verdict != new_result.verdict:
                total_flips += 1
                flip_details.append({
                    "case_id": case.case_id,
                    "finding_id": f"synth-{ef.expected_id}",
                    "old_verdict": old_result.verdict.value,
                    "new_verdict": new_result.verdict.value,
                })

        # --- Grade synthetic noise findings (novel_valid / no_match boundary) ---
        # Exercises how the grader handles unmatched findings — critical for
        # detecting prompt changes that affect FP classification.
        noise_findings = _build_noise_findings(case)
        for nf in noise_findings:
            old_result = await grade_finding(
                finding=nf,
                expected_findings=case.expected_findings,
                case_description=case.description,
                grader_model=grader_model,
                prompt_template=old_template,
                rubric=old_rubric,
                few_shot_examples=old_examples,
                max_retries=max_retries,
            )

            new_result = await grade_finding(
                finding=nf,
                expected_findings=case.expected_findings,
                case_description=case.description,
                grader_model=grader_model,
                prompt_template=new_template,
                rubric=new_rubric,
                few_shot_examples=new_examples,
                max_retries=max_retries,
            )

            total_comparisons += 1
            if old_result.verdict != new_result.verdict:
                total_flips += 1
                flip_details.append({
                    "case_id": case.case_id,
                    "finding_id": nf.finding_id,
                    "old_verdict": old_result.verdict.value,
                    "new_verdict": new_result.verdict.value,
                })

    flip_rate = total_flips / total_comparisons if total_comparisons > 0 else 0.0

    # Report results
    if verbose or flip_details:
        print(f"\nConsistency check: {total_comparisons} comparisons, "
              f"{total_flips} flips ({flip_rate:.1%})", file=sys.stderr)
        for flip in flip_details:
            print(
                f"  FLIP: {flip['case_id']}/{flip['finding_id']}: "
                f"{flip['old_verdict']} -> {flip['new_verdict']}",
                file=sys.stderr,
            )

    return flip_rate


def accept_prompt(grader_dir: Path) -> str:
    """Accept the current grader prompt as the new baseline.

    Gate: checked_hash in VERSION.lock must match current computed hash.
    - Copies current prompt files to .accepted/
    - Updates VERSION.lock: hash = computed, clears checked fields

    Returns the new hash.
    Raises ValueError if checked_hash doesn't match (must run consistency
    check first).
    """
    computed = compute_prompt_hash(grader_dir)
    lock = _read_lock(grader_dir)

    if lock["checked_hash"] is None or lock["checked_hash"] != computed:
        raise ValueError(
            "Cannot accept prompt: no valid consistency check recorded. "
            "Run a consistency check first (checked_hash must match "
            f"current computed hash {computed})."
        )

    _copy_prompt_files_to_accepted(grader_dir)

    lock["hash"] = computed
    lock["accepted_at"] = datetime.now(timezone.utc).isoformat()
    lock["checked_hash"] = None
    lock["checked_at"] = None
    lock["flip_rate"] = None
    _write_lock(grader_dir, lock)

    return computed
