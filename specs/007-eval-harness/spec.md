# Feature Specification: AgentinaBox — Eval Harness

**Feature Branch**: `007-eval-harness`
**Created**: 2026-03-13
**Status**: Draft
**Depends on**: 001-ai-code-reviewer

## Why This Exists

Without an eval system, we cannot answer "is the reviewer any good?" We can only vibe-check individual reviews. This spec defines a repeatable, measurable evaluation framework that:

- Proves the reviewer finds real issues (recall)
- Proves the reviewer doesn't invent fake issues (precision)
- Catches regressions when we change prompts, models, or bundle formats
- Provides the evidence needed to publish AgentinaBox as a credible tool

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Eval Suite Against Golden Cases (Priority: P1)

A developer changes the reviewer's system prompt or switches the underlying model. Before committing, they run the eval suite — a set of curated diffs with known-correct expected findings. The harness sends each case through `start_review`, compares the returned findings against expected findings, and produces a scorecard with precision, recall, severity accuracy, and category accuracy metrics.

**Why this priority**: This is the core eval capability. Without it, every prompt change is a gamble.

**Independent Test**: Can be tested by running the eval suite with a known model and verifying the scorecard matches expected baseline metrics.

**Acceptance Scenarios**:

1. **Given** a set of 20+ golden test cases with expected findings, **When** a developer runs the eval suite, **Then** each case is sent through `start_review` and the returned findings are compared against expected findings using fingerprint matching.
2. **Given** the eval suite completes, **When** results are displayed, **Then** a scorecard shows: precision, recall, severity accuracy, category accuracy, false positive rate, and per-case pass/fail.
3. **Given** precision drops below the configured threshold (default: 70%), **When** the eval suite finishes, **Then** the run is marked as FAILED with a clear indication of which cases caused the regression.

---

### User Story 2 - Grade Multi-Turn Discussion Quality (Priority: P2)

A developer wants to verify that the reviewer handles rebuttals correctly — accepting valid arguments and standing firm on real bugs. The eval suite includes multi-turn test cases where a scripted "Claude Code" submits rebuttals. The harness grades whether the reviewer appropriately changed or maintained finding statuses.

**Why this priority**: The multi-turn loop is AgentinaBox's core differentiator. If the reviewer blindly agrees with every rebuttal, or never accepts any, the tool is useless.

**Independent Test**: Can be tested by running a multi-turn eval case where a valid rebuttal is submitted, and verifying the reviewer dismisses the challenged finding.

**Acceptance Scenarios**:

1. **Given** a multi-turn test case where the rebuttal is valid, **When** the eval runs the full `start_review` → `discuss` → `get_review_summary` loop, **Then** the challenged finding is dismissed or downgraded.
2. **Given** a multi-turn test case where the rebuttal is invalid (the bug is real), **When** the eval runs the loop, **Then** the reviewer stands firm and the finding status remains `open`.
3. **Given** the eval suite includes both valid and invalid rebuttals, **When** results are displayed, **Then** a "rebuttal accuracy" metric shows the percentage of correct rebuttal decisions.

---

### User Story 3 - Measure False Positive Rate on Clean Code (Priority: P3)

A developer wants to verify the reviewer doesn't invent phantom issues. The eval suite includes cases of well-written, correct code. The harness measures how many findings the reviewer produces on clean code — these are all false positives.

**Why this priority**: A reviewer that produces too many false positives trains developers to ignore it. False positive rate is the single most important metric for trust.

**Independent Test**: Can be tested by submitting 5 clean diffs and verifying the reviewer returns zero BUG/WARN findings (NITs are acceptable).

**Acceptance Scenarios**:

1. **Given** 5+ clean code test cases with no known issues, **When** the eval runs, **Then** the false positive rate for BUG/WARN findings is below 20%.
2. **Given** a clean code case where the reviewer produces a BUG finding, **When** inspected, **Then** the case is flagged as a false positive in the scorecard with the full finding details for human review.

---

### User Story 4 - Regression Testing on CI (Priority: P4)

The eval suite can be run as part of the CI pipeline. When a PR changes the reviewer's system prompt, bundle format, or finding parser, the eval suite runs automatically. If metrics drop below thresholds, the build fails.

**Why this priority**: Automated regression prevention is what makes the eval system durable rather than a one-time check.

**Independent Test**: Can be tested by running the eval suite in CI mode and verifying it returns exit code 0 on passing and exit code 1 on failure.

**Acceptance Scenarios**:

1. **Given** the eval suite is configured with metric thresholds, **When** run with `--ci` flag, **Then** it exits with code 0 if all thresholds pass and code 1 if any threshold fails.
2. **Given** a PR changes the reviewer system prompt, **When** CI runs the eval suite, **Then** the scorecard is posted as a PR comment showing before/after metrics.

---

### Edge Cases

- How does the eval handle non-deterministic model responses (same input, different findings)?
- What happens when the model returns findings not in the expected set but that are still valid?
- How are "partially correct" findings scored (right issue, wrong line number)?
- What happens when the Copilot API is rate-limited during an eval run?

## Requirements *(mandatory)*

### Functional Requirements

#### Golden Test Cases

- **FR-001**: The eval harness MUST support a library of golden test cases, each containing: a review bundle (diff + files + rules), expected findings (with `rule_id`, severity, category, and approximate location), and optionally a set of expected non-findings (things the reviewer should NOT flag)
- **FR-002**: Golden test cases MUST include at minimum: (a) 10+ cases with known bugs/issues, (b) 5+ cases with clean code (no issues), (c) 5+ cases testing specific review dimensions (security, design, tests, etc.)
- **FR-003**: Each golden test case MUST be stored as a self-contained fixture (directory with diff, files, expected.json, and optional metadata)

#### Metrics

- **FR-004**: The harness MUST compute and report these metrics per eval run:

  | Metric | Definition | Default threshold |
  |--------|-----------|-------------------|
  | Precision | Found findings that match expected / total found findings | >= 70% |
  | Recall | Expected findings that were found / total expected findings | >= 60% |
  | Severity accuracy | Findings with correct severity / total matched findings | >= 80% |
  | Category accuracy | Findings with correct review dimension / total matched findings | >= 70% |
  | False positive rate (BUG/WARN) | BUG/WARN findings on clean code cases / total clean code cases | <= 20% |
  | Rebuttal accuracy | Correct rebuttal decisions / total rebuttal cases | >= 75% |

- **FR-005**: Finding matching MUST use fingerprint-based comparison (not exact string match). A finding "matches" an expected finding if the `rule_id` matches and the `primary_location` file matches and the line number is within a configurable tolerance (default: +/- 5 lines)

#### Multi-Turn Evaluation

- **FR-006**: The harness MUST support multi-turn test cases that script a sequence of `start_review` → `discuss` (with predefined rebuttal messages) → `get_review_summary` calls
- **FR-007**: Multi-turn cases MUST specify expected finding status changes after each rebuttal (e.g., "after rebuttal to F-002, expected status = dismissed")

#### Execution and Reporting

- **FR-008**: The harness MUST run against a live AgentinaBox instance (not mocked). Eval results reflect actual model behavior.
- **FR-009**: The harness MUST produce a scorecard in both human-readable (markdown table) and machine-readable (JSON) format
- **FR-010**: The harness MUST support a `--ci` mode that exits with code 0/1 based on threshold pass/fail
- **FR-011**: The harness MUST handle non-deterministic model responses by supporting multiple eval runs (configurable, default: 3) and reporting metrics as averages with standard deviation
- **FR-012**: The harness MUST support configurable metric thresholds that can be overridden per project or per CI pipeline

#### Robustness

- **FR-013**: The harness MUST handle rate limiting by backing off and retrying (with a maximum retry count), not by failing the entire eval run
- **FR-014**: The harness MUST report which specific cases passed/failed, not just aggregate metrics, so developers can diagnose regressions

### Key Entities

- **Golden Test Case**: A curated input/expected-output pair. Contains: case ID, description, review bundle (diff + files + rules), expected findings (list of `{ rule_id, severity, category, file, approximate_line }`), expected non-findings (optional), and multi-turn script (optional).
- **Eval Run**: A single execution of the full test suite. Contains: timestamp, model used, number of cases, aggregate metrics, per-case results, and pass/fail status.
- **Scorecard**: The output of an eval run. Contains aggregate metrics, per-case breakdown, per-metric pass/fail against thresholds, and comparison to previous run (if available).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The eval suite runs all 20+ golden cases and produces a scorecard within 15 minutes
- **SC-002**: The eval suite correctly identifies a regression when the reviewer system prompt is degraded (e.g., removing the severity classification instruction causes severity accuracy to drop below threshold)
- **SC-003**: The false positive rate on clean code cases is measurably below 20% with the default model
- **SC-004**: A developer can add a new golden test case by creating a directory with a diff and expected.json — no code changes required
- **SC-005**: The eval suite can run in CI and post results as a PR comment
