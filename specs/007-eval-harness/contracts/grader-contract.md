# Grader Contract: Eval Harness (007)

## Overview

The grading pipeline classifies each reviewer finding using a two-tier system (FR-018). Tier 1 is deterministic; Tier 2 is model-based.

## Tier 1: Fingerprint Grader

**Module**: `eval/graders/fingerprint.py`
**Speed**: Fast, deterministic, reproducible

### Interface

```python
def grade_finding(
    finding: Finding,
    expected_findings: list[ExpectedFinding],
    line_tolerance: int = 5,
) -> GraderResult | None:
    """Attempt to match a finding via fingerprint.

    Returns GraderResult if a match is found, None if no match
    (finding should be forwarded to Tier 2).
    """
```

### Matching Algorithm (FR-005)

A finding matches an expected finding if ALL conditions are true:
1. `finding.rule_id == expected.rule_id`
2. `finding.primary_location.file == expected.file`
3. `abs(finding.primary_location.start_line - expected.approximate_line) <= line_tolerance`

**On match**:
- `verdict`: `match` if severity AND category match; `partial_match` if either differs
- `confidence`: always `high`
- `matched_expected_id`: the expected finding's ID
- Severity/category accuracy computed directly from the matched pair

**On no match**:
- Returns `None` — finding is forwarded to Tier 2

### Multiple Match Resolution

If a finding matches multiple expected findings, select the one with the smallest line distance. Ties broken by expected finding order.

If an expected finding is matched by multiple actual findings, the first match wins. Subsequent matches for the same expected finding are forwarded to Tier 2 (they may be duplicates or novel findings).

## Tier 2: Model-Based Grader

**Module**: `eval/graders/model_grader.py`
**Speed**: Slower (API call), non-deterministic

### Interface

```python
async def grade_finding(
    finding: Finding,
    expected_findings: list[ExpectedFinding],
    case_description: str,
    grader_model: str = "claude-sonnet-4-6",
) -> GraderResult:
    """Grade a finding using LLM-as-Judge.

    Called only for findings that did NOT match in Tier 1.
    Always returns a GraderResult (never None).
    """
```

### Grader Prompt Structure (FR-019)

The prompt sent to the grader model contains these sections:

```
## Task
You are evaluating whether a code review finding matches any expected finding,
or whether it represents a novel valid issue or noise.

## Expected Findings
{list of expected findings with IDs, descriptions, file, line, severity, category}

## Actual Finding to Grade
- Finding ID: {finding.finding_id}
- Rule ID: {finding.rule_id}
- Severity: {finding.severity}
- Category: {finding.category}
- File: {finding.primary_location.file}
- Line: {finding.primary_location.start_line}
- Message: {finding.message}
- Evidence: {finding.evidence}

## Case Context
{case_description}

## Rubric
- **match**: The finding describes the same underlying issue as an expected finding,
  regardless of wording differences.
- **partial_match**: The finding addresses a related aspect of an expected issue
  but differs in severity or category.
- **novel_valid**: The finding describes a real, actionable code issue that is NOT
  in the expected set. The issue would be worth flagging in a real review.
- **no_match**: The finding is noise — not a real issue, or too vague to be actionable.

## Few-Shot Examples
{3+ examples covering match, partial_match, novel_valid, and no_match}

## Output Format
Respond with ONLY a JSON object:
{
  "verdict": "match" | "partial_match" | "novel_valid" | "no_match",
  "confidence": "high" | "medium" | "low",
  "matched_expected_id": "EF-001" | null,
  "reasoning": "Brief explanation"
}
```

### Prompt Storage and Versioning (FR-022)

```
eval/fixtures/grader/
├── prompt_template.txt    # The prompt template with {placeholders}
├── rubric.md              # Detailed rubric (included in prompt)
├── few_shot_examples.json # 3+ labeled examples
├── VERSION.lock           # JSON: accepted hash + timestamp
└── .accepted/             # Snapshot of last-accepted prompt files
    ├── prompt_template.txt
    ├── rubric.md
    └── few_shot_examples.json
```

**Version computation**: `SHA-256(prompt_template + rubric + few_shot_examples)[:12]`

**VERSION.lock format**:
```json
{
  "hash": "a1b2c3d4e5f6",
  "accepted_at": "2026-03-31T14:00:00Z",
  "checked_hash": null,
  "checked_at": null,
  "flip_rate": null
}
```

The `checked_hash` field records which prompt hash has been consistency-checked. This ties adoption to a completed comparison, preventing `--accept-prompt` from bypassing the FR-022 requirement.

#### Versioned-Prompt Workflow

The harness enforces FR-022 through a three-state gating mechanism:

1. **Clean state**: Computed hash of current prompt files matches `VERSION.lock` `hash`. Normal eval runs proceed.

2. **Dirty state (prompt changed)**: Computed hash differs from `VERSION.lock` `hash`. The harness **refuses to run** a normal eval and exits with code 2:
   ```
   Error: Grader prompt changed (current: x1y2z3, accepted: a1b2c3).
   Run: python -m eval --prompt-consistency-check
   ```

3. **Consistency check** (`--prompt-consistency-check` flag):
   - Loads the **previous** prompt from `.accepted/` and the **current** prompt from the working files
   - Runs all golden cases through the Tier 2 grader **twice**: once with the old prompt, once with the new prompt
   - Compares verdicts finding-by-finding
   - Reports the **verdict flip rate** (% of findings where old and new prompts disagree)
   - Outputs a per-finding diff showing which verdicts changed and in which direction
   - **Writes `checked_hash`** to `VERSION.lock`: sets `checked_hash` to the computed hash of the current prompt files, `checked_at` to the current timestamp, and `flip_rate` to the measured rate
   - Does NOT update `hash` or `.accepted/` — the prompt is checked but not yet adopted

4. **Adoption** (`--accept-prompt` flag):
   - **Gate**: Reads `VERSION.lock` and verifies `checked_hash == computed_hash` (current prompt files). If they don't match, refuses with:
     ```
     Error: No consistency check found for current prompt (hash: x1y2z3).
     Run: python -m eval --prompt-consistency-check first.
     ```
     This prevents skipping the comparison — if the developer edits the prompt again after the check, `checked_hash` no longer matches and adoption is blocked until the check is re-run.
   - Copies current prompt files into `.accepted/`
   - Updates `VERSION.lock`: sets `hash` to the computed hash, `accepted_at` to the current timestamp, clears `checked_hash`/`checked_at`/`flip_rate` back to `null`
   - Normal eval can now run again

**First-time setup**: When `VERSION.lock` does not exist (fresh repo), the first `python -m eval` run auto-initializes: copies current files to `.accepted/`, creates `VERSION.lock` with the computed hash, and proceeds normally.

**CI behavior**: In `--ci` mode, a dirty prompt state is a hard failure (exit code 2). Developers must run the consistency check and accept locally before pushing.

### Model Configuration (FR-020)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Model | `claude-sonnet-4-6` (default) | Configurable via `--grader-model` |
| Max tokens | `512` | Structured JSON response is compact |
| Temperature | `0` | Maximize reproducibility |
| API | `anthropic.Anthropic().messages.create()` | Runs on host, not in container |

### Error Handling

| Condition | Behavior |
|-----------|----------|
| API rate limit | Retry with exponential backoff (shared with MCP retries per FR-013) |
| API error (500, etc.) | Retry up to `max_retries`, then return `GraderResult(verdict="grading_error", confidence="low", reasoning="API error after {n} retries: {msg}")` |
| Invalid JSON response | Re-prompt once with "Respond with ONLY valid JSON", then return `GraderResult(verdict="grading_error", confidence="low", reasoning="Invalid grader response after retry")` |
| Missing `ANTHROPIC_API_KEY` | Abort run with exit code 2 |

**Scoring exclusion**: Findings with `verdict="grading_error"` are excluded from **all** metric computations (precision, recall, SNR, severity/category accuracy). They represent infrastructure failures, not model behavior. The `grading_error_count` in `TrialMetrics` tracks how many findings were affected. If >50% of a trial's findings have `grading_error`, the entire trial is marked as errored (`TrialResult.error` is set).

## Grading Pipeline Flow

```
For each finding from the reviewer:
  1. Run Tier 1 (fingerprint match)
     ├─ Match found → Return GraderResult (match or partial_match)
     └─ No match → Continue to step 2
  2. Run Tier 2 (model-based)
     ├─ Success → Return GraderResult (match, partial_match, novel_valid, or no_match)
     └─ API failure after retries → Return GraderResult (grading_error) — excluded from metrics
```

Each expected finding can be matched at most once. The pipeline tracks which expected findings have been claimed to prevent double-counting.
