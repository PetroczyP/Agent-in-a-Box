# Feature Specification: AgentinaBox — Eval Harness

**Feature Branch**: `007-eval-harness`
**Created**: 2026-03-13
**Status**: Draft
**Depends on**: 001-ai-code-reviewer
**Interacts with**: 012-multi-dimension-review (dimension coverage metric validates multi-persona effectiveness)

> **Note**: Feedback harvesting (originally User Story 5 in this spec) has been moved to spec 003 (Review Dashboard). Spec 007 is self-contained with no external dependencies beyond spec 001.

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

1. **Given** a set of 20+ golden test cases with expected findings, **When** a developer runs the eval suite, **Then** each case is sent through `start_review` and the returned findings are graded using the multi-tier pipeline (deterministic fingerprint matching first, then model-based grading for unmatched findings).
2. **Given** the eval suite completes, **When** results are displayed, **Then** a scorecard shows: precision, recall, severity accuracy, category accuracy, false positive rate, SNR, novel finding count, and per-case pass/fail.
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

**Independent Test**: Can be tested by submitting 5 clean diffs and verifying the reviewer returns zero BUG findings (WARNs and NITs are acceptable — WARN-level design observations on clean code are expected reviewer behavior).

**Acceptance Scenarios**:

1. **Given** 5+ clean code test cases with no known issues, **When** the eval runs, **Then** the false positive rate for BUG findings is below 20%. WARN findings on clean code are tracked separately as `warn_rate` (informational, no threshold gate).
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
- How are dual-metric cases scored when the reviewer correctly detects the bug in the vulnerable version but also flags the fixed version? → The "fixed" run is a false positive, reducing precision. Both sub-results contribute independently to aggregate metrics.

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
  | Precision | Matched findings / (matched + no_match findings). Excludes `novel_valid` from both numerator and denominator — they are real findings, not noise. | >= 70% |
  | Recall | Expected findings that were matched (via Tier 1 or Tier 2) / total expected findings | >= 60% |
  | Severity accuracy | Adjacency-weighted severity score / unique matched expected findings. Adjacent mismatches (BUG↔WARN, WARN↔NIT) score 0.5; two-step (BUG↔NIT) scores 0.0. When multiple actuals match one expected, best score per expected ID is kept. See Design Note DN-001. | >= 80% |
  | Category accuracy | Correct category / unique matched expected findings. When multiple actuals match one expected, best score per expected ID is kept. | >= 70% |
  | False positive rate (BUG) | BUG findings on clean code cases / total clean code cases. WARN findings on clean code are expected reviewer behavior and tracked separately as `warn_rate` (informational). | <= 20% |
  | Rebuttal accuracy | Correct rebuttal decisions / total rebuttal cases | >= 75% |
  | Signal-to-Noise Ratio (SNR) | (matched + novel_valid) / no_match findings. Novel findings are signal, not noise. | >= 3.0 (internal target; calibrate after initial eval runs) |
  | Novel finding count | Number of `novel_valid` findings across all cases (informational — tracked separately, not gated) | (informational) |
  | pass@1 | % of expected findings caught on the first trial (no retry) | (informational) |

- **FR-005**: Finding matching MUST use fingerprint-based comparison (not exact string match). A finding "matches" an expected finding if the `rule_id` matches and the `primary_location` file matches and the line number is within a configurable tolerance (default: +/- 5 lines)

#### Multi-Turn Evaluation

- **FR-006**: The harness MUST support multi-turn test cases that script a sequence of `start_review` → `discuss` (with predefined rebuttal messages) → `get_review_summary` calls
- **FR-007**: Multi-turn cases MUST specify expected finding status changes after each rebuttal (e.g., "after rebuttal to F-002, expected status = dismissed")

#### Execution and Reporting

- **FR-008**: The harness MUST run against a live AgentinaBox instance (not mocked). Eval results reflect actual model behavior.
- **FR-009**: The harness MUST produce a scorecard in both human-readable (markdown table) and machine-readable (JSON) format
- **FR-010**: The harness MUST support a `--ci` mode that exits with code 0/1 based on threshold pass/fail
- **FR-011**: The harness MUST handle non-deterministic model responses by supporting multiple eval runs (configurable, default: 3) and reporting metrics as means with standard error of the mean (SEM) alongside the 95% CI bounds defined in FR-016
- **FR-012**: The harness MUST support configurable metric thresholds that can be overridden per project or per CI pipeline
- **FR-012a**: In `--ci` mode, the harness MUST output the scorecard as a markdown-formatted string suitable for posting as a GitHub PR comment. The output MUST include a before/after comparison when a previous baseline run exists. The harness is NOT responsible for the GitHub API call itself — the CI pipeline (e.g., GitHub Actions workflow) posts the comment using the harness output.

#### Robustness

- **FR-013**: The harness MUST handle rate limiting by backing off and retrying (with a maximum retry count), not by failing the entire eval run
- **FR-014**: The harness MUST report which specific cases passed/failed, not just aggregate metrics, so developers can diagnose regressions

#### Dual-Metric Testing

- **FR-015**: For golden cases sourced from bug-fix PRs, the harness MUST support dual-metric testing: the vulnerable version (pre-fix diff) is tested for recall (should detect the bug) AND the fixed version (post-fix diff) is tested for false-positive suppression (should NOT flag it). Both sub-results contribute independently to aggregate metrics.

#### Statistical Reporting

- **FR-016**: When multiple trials are run (FR-011), the harness MUST report SEM alongside averages for all numeric metrics. For threshold comparisons, the harness MUST use the tail of a 95% confidence interval that is most conservative for the threshold direction, not the raw mean, to ensure statistical confidence in pass/fail decisions: metrics with lower-bound (`>=`) semantics — precision, recall, severity_accuracy, category_accuracy, SNR, rebuttal_accuracy, pass@k — compare the **lower** CI bound against the threshold; metrics with upper-bound (`<=`) semantics — fp_rate — compare the **upper** CI bound against the threshold. CI method varies by metric type: Wilson score interval for Bernoulli proportions (fp_rate, rebuttal_accuracy, pass@k), BCa bootstrap for per-trial rate aggregations (precision, recall, severity_accuracy, category_accuracy, SNR). Both the CI method and the tail used for thresholding MUST be recorded in the metric output (`method` field).
- **FR-017**: The harness MUST report both pass@1 (found on first trial) and pass@3 (found in at least one of 3 trials) for each expected finding. The gap between pass@1 and pass@3 indicates review reliability.

#### Multi-Tier Grading

- **FR-018**: The harness MUST implement a multi-tier grading pipeline. Each reviewer finding is graded by tiers in order; the first tier that produces a definitive result wins:

  | Tier | Grader type | What it handles | Speed |
  |------|------------|-----------------|-------|
  | 1 | Deterministic (code-based) | Fingerprint matches (FR-005): `rule_id` + file + line tolerance. For matched findings, severity and category accuracy are computed directly by comparing the matched pair — no Tier 2 involvement. | Fast, reproducible |
  | 2 | Model-based (LLM-as-Judge) | Findings that do NOT match any expected finding via fingerprint: same issue described differently, valid findings not in expected set, entirely spurious findings. | Slower, non-deterministic |

  **Routing rule**: Tier 1 runs on all findings first. A finding that matches via fingerprint is resolved entirely by Tier 1 (including severity/category accuracy). Only findings with zero fingerprint matches are forwarded to Tier 2.

- **FR-019**: The model-based grader (Tier 2) MUST use a structured evaluation prompt containing: (a) the golden case's expected findings with descriptions, (b) the reviewer's actual finding text and location, (c) a rubric with explicit scoring criteria and 3+ few-shot examples covering match, partial match, and no-match scenarios, and (d) required output format (structured JSON with `verdict`, `confidence`, and `reasoning` fields).

- **FR-020**: The model-based grader MUST use a different model than the one being evaluated to avoid self-evaluation bias. The grader model and prompt version MUST be recorded in the eval run metadata for reproducibility.

- **FR-021**: The model-based grader MUST classify each finding into one of: `match` (same issue as expected, regardless of wording), `partial_match` (related but different aspect of the same problem — e.g., correct issue, wrong severity), `novel_valid` (a real issue not in the expected set), or `no_match` (noise / false positive). Scoring contract for each verdict:

  | Verdict | Precision numerator | Precision denominator | Recall numerator | SNR numerator | SNR denominator |
  |---------|--------------------|-----------------------|------------------|---------------|-----------------|
  | `match` | +1 | +1 | +1 | +1 | — |
  | `partial_match` | +1 | +1 | +1 | +1 | — |
  | `novel_valid` | excluded | excluded | — | +1 | — |
  | `no_match` | — | +1 | — | — | +1 |

  Novel findings count is reported as a separate informational metric. Threshold gating uses precision, recall, and SNR — `novel_valid` findings affect only SNR (as signal).

- **FR-022**: The grader prompt and rubric MUST be versioned alongside the golden cases. Changes to the grader prompt trigger an eval run to measure grading consistency before and after the change.

### Key Entities

- **Golden Test Case**: A curated input/expected-output pair. Contains: case ID, description, review bundle (diff + files + rules), expected findings (list of `{ rule_id, severity, category, file, approximate_line }`), expected non-findings (optional), and multi-turn script (optional).
- **Eval Run**: A single execution of the full test suite. Contains: timestamp, model used, number of cases, aggregate metrics, per-case results, and pass/fail status.
- **Scorecard**: The output of an eval run. Contains aggregate metrics, per-case breakdown, per-metric pass/fail against thresholds, and comparison to previous run (if available).
- **Golden Case Source**: Metadata tag indicating where a golden case came from. Values: `hand_curated` (manually written), `bug_fix_pr` (traced from real bug-fix commits), `vulnerability_dataset` (from OpenSSF CVE / OWASP / DiverseVul), `synthetic` (hand-crafted for edge cases).
- **Grader Result**: The output of grading a single finding. Contains: `tier` (1 or 2), `verdict` (match / partial_match / novel_valid / no_match), `confidence` (high / medium / low — Tier 1 is always high), `reasoning` (Tier 2 only), `matched_expected_id` (which expected finding it matched, if any).
- **Grader Prompt**: A versioned prompt template used by the Tier 2 model-based grader. Contains: rubric, scoring criteria, few-shot examples, required output schema. Stored alongside golden cases and tracked in eval run metadata.

### Design Notes

- **DN-001 (Severity Scoring Methodology)**: Exact-match severity scoring was rejected because human inter-rater agreement on code review severity is low (Cohen's κ ≈ 0.162 per Quantum Software Engineering studies; DeepCRCEval treats severity as "supplementary and less reliable"). The adjacency-weighted approach (BUG↔WARN = 0.5, BUG↔NIT = 0.0) models severity as an ordinal scale, consistent with standard practice for ordinal classification tasks. Quadratic-weighted Cohen's kappa (`severity_qwk`) is reported as an informational companion metric. This follows the methodology used by SWR-Bench (ICSE 2025) and DeepCRCEval (2024) which both avoid hard severity matching.

- **DN-002 (CI Methodology)**: Normal-approximation CIs (mean ± 1.96 × SEM) fail for small samples and bounded proportions. Wilson score intervals (Brown, Cai & DasGupta 2001) provide correct coverage for Bernoulli outcomes even at n < 20. BCa bootstrap (Efron & Tibshirani 1993) handles the bounded [0,1] nature of rate metrics without distributional assumptions. The Inspect AI eval framework (Anthropic/UK AISI) uses a similar hybrid approach.

- **DN-003 (Rebuttal Accuracy Minimum Sample Size — B′ coordinator-ratified 2026-04-18)**: Wilson CI for threshold gating requires sufficient observations. When even a perfect score (n/n) at the current sample size cannot produce `ci_lower >= threshold`, the metric is tagged `method="wilson_insufficient_n"`. For the default 0.75 threshold, **12+ all-correct observations** are needed for Wilson CI to clear the gate (at n=12, `ci_lower ≈ 0.758`; at n=11, `ci_lower ≈ 0.741`). The prior "14+" figure was incorrect and was corrected during the release-phase escalation. With only 2 multi-turn golden cases, the current fixture corpus cannot satisfy this requirement.

  **Semantics (B′ hybrid)**: The metric's natural `passes_threshold` flag is preserved (typically False at small n) — `passes_threshold` is **not** force-set to True. The scorecard renders the row as **INCONCLUSIVE** (never PASS) so humans reading the scorecard see the corpus-maturity state clearly. `check_thresholds(..., strict=False)` (default) treats `wilson_insufficient_n` as non-fatal, allowing small-corpus runs to pass the `--ci` gate; `check_thresholds(..., strict=True)` (opt-in via `--strict` CLI flag) treats it as a fail. The CLI also writes a stderr warning whenever an inconclusive metric is present so CI log scrapers can detect the corpus-maturity gap without parsing markdown. Rationale: keeps the scorecard honest (inconclusive ≠ PASS), defers release blocking on corpus maturity to spec 014 SH-007, and provides a strict toggle once the corpus grows. This behavior was escalated to and ratified by the coordinator in the release-phase builder/judge loop (Round 13).

## Research & Best Practices (Design Guidance)

*This section captures industry research to inform the design and planning phases. These are not requirements — they are inputs for whoever builds this spec.*

### Golden Case Sourcing Strategy

The hardest part of an eval harness is curating high-quality golden cases. Research shows three complementary sourcing approaches:

**1. Real bug-fix PRs (recommended primary source)**
The [Greptile benchmark](https://www.greptile.com/benchmarks) uses 50 real-world PRs from 5 open-source repos, tracing bug-fix commits back to the commits that introduced the bugs. This is the gold standard because the bugs are real, the context is realistic, and anyone can verify them. Our harness should adopt this approach:
- Select 5+ well-known open-source Python projects with clean commit histories
- For each, find 5-10 bug-fix commits and reconstruct the "before" diff (the commit that introduced the bug)
- Each case has a verifiable ground truth: the bug-fix commit IS the answer key
- Filter: exclude extremely large diffs or single-file-only changes

**2. Known vulnerability datasets (for security dimension)**
- [OpenSSF CVE Benchmark](https://github.com/ossf-cve-benchmark/ossf-cve-benchmark): 200+ real CVEs with pre-patch and post-patch variants. Used by [DeepSource's benchmark](https://deepsource.com/benchmarks) (165 JS/TS vulnerabilities). We can adapt the Python-relevant subset.
- [OWASP Benchmark](https://owasp.org/www-project-benchmark/): Test suite for vulnerability detection tools. Java-focused but the methodology (known true positives + known false positives) is directly applicable.
- [DiverseVul](https://arxiv.org/pdf/2304.00409): 18,945 vulnerable functions spanning 150 CWEs. Academic dataset, useful for sampling specific vulnerability classes.

**3. Synthetic cases (for edge cases and specific dimensions)**
Hand-crafted diffs targeting specific review dimensions that are hard to find in the wild:
- Off-by-one errors (correctness)
- Race conditions (correctness)
- Bare `except: pass` (correctness + maintainability)
- Hardcoded secrets (security)
- N+1 query patterns (performance)
- Missing test for new code path (tests)
- Clean code with no issues (false positive testing)

### Grading Methodology

Research from [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), [OpenAI](https://developers.openai.com/api/docs/guides/evaluation-best-practices), and [Martian](https://withmartian.com/post/code-review-bench-v0) converges on three complementary grading approaches:

**1. Deterministic matching (primary grader)**
Fingerprint-based comparison — our FR-005 already specifies this. Compare `rule_id` + file + approximate line. This handles the "did it find the known bug?" question.

**2. LLM-as-Judge (secondary grader for nuance)**
For cases where the reviewer finds the right issue but describes it differently than expected, or finds a valid issue we didn't anticipate. The [Martian Code Review Benchmark](https://codereview.withmartian.com/) uses this approach: an LLM judge asks "do these describe the same underlying issue?" — different wording is fine, only substance matters.
- Use the most capable available model as judge (not the same model being evaluated)
- Provide a clear rubric with scoring criteria (research shows [question-specific rubrics outperform general rubrics](https://arxiv.org/html/2503.23989v1))
- Store results per judge model to control for judge bias
- Important: [OpenAI's eval guide](https://developers.openai.com/api/docs/guides/evaluation-best-practices) warns about "grader hacking" — a model may exploit weaknesses in the judge. Cross-check with deterministic graders.

**3. Human review (calibration and edge cases)**
Periodically sample eval results for human review to calibrate the automated graders. Especially important for:
- Cases where deterministic and LLM-judge disagree
- New golden cases before they're added to the suite
- False positives that automated graders miss

### Metric Design

Beyond our current FR-004 metrics, research suggests tracking:

| Additional Metric | Source | Why It Matters |
|---|---|---|
| **pass@1** | [OpenAI evals](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | Does the reviewer find the issue on the first try? (vs. pass@3 across multiple runs). Critical for CI/CD where you get one shot. |
| **Acceptance rate** | [CodeRabbit framework](https://www.coderabbit.ai/blog/framework-for-evaluating-ai-code-review-tools) | % of AI comments that result in a code change. Measures signal quality, not just detection. |
| **Dimension coverage** | Spec 012 | Of the 6 review dimensions, how many does the reviewer produce findings in? (Directly validates multi-dimension review) |
| **Time-to-finding** | [Greptile benchmark](https://www.greptile.com/benchmarks) | Wall-clock time from `start_review` to findings. Important for developer experience. |
| **Finding specificity** | [DeepSource benchmark](https://deepsource.com/benchmarks) | Does the finding point to the exact line, or a vague region? Measured by line-number accuracy within tolerance. |

### Nondeterminism Handling

LLMs are nondeterministic. The same input can produce different findings across runs. Research suggests:

- **Multiple trials per case**: FR-011 already specifies this (default: 3 runs, report average + stddev). [Anthropic's eval guide](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) calls this distinguishing a "task" from a "trial."
- **pass@k scoring**: Report both pass@1 (found on first try) and pass@3 (found in at least one of 3 tries). The gap between them indicates review reliability.
- **Transcript logging**: Record the full model response for every trial, not just the parsed findings. When a case fails, the transcript is essential for debugging whether the issue is in the model, the prompt, or the parser. ([Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents): "Always read the transcripts.")

### SARIF Fingerprint Matching

Since our findings are SARIF-inspired, the matching algorithm should follow [SARIF spec guidance](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html):
- Primary match: `fingerprint` field (hash of `rule_id` + normalized code at location)
- Fallback: `partialFingerprints` — match on `rule_id` + file + line range tolerance
- Support fingerprint versioning: if the fingerprint algorithm changes, old golden cases should still match via the fallback

### Open-Source Benchmarks to Leverage

These existing benchmarks can be adapted or used directly:

| Benchmark | What It Provides | How We'd Use It |
|---|---|---|
| [Martian Code Review Bench](https://github.com/withmartian/code-review-benchmark) | 200K+ PRs, LLM-judge prompts, evaluation pipeline, open-source | Adapt their judge prompts and matching methodology. Consider contributing AgentinaBox results to their leaderboard. |
| [Greptile Benchmark](https://www.greptile.com/benchmarks) | 50 PRs from 5 repos with known bugs, transparent methodology | Study their case selection criteria and bug-catch scoring methodology. |
| [OpenSSF CVE Benchmark](https://github.com/ossf-cve-benchmark/ossf-cve-benchmark) | 200+ real CVEs with pre/post-patch code | Extract Python-relevant cases for our security golden cases. |
| [DeepSource Benchmark](https://deepsource.com/benchmarks) | 165 JS/TS vulnerabilities, dual-metric evaluation (detection + false positive suppression) | Adapt their dual-metric approach: test both that we catch the bug AND that we don't flag the fixed version. |

### Recent Benchmarks (2025-2026)

Research published after the initial draft provides additional context:

| Benchmark | Key Finding | Implication for Us |
|---|---|---|
| [CR-Bench](https://arxiv.org/abs/2603.11078) (March 2026) | 584 defects from SWE-Bench. SNR collapses when models are pressured to find more issues (GPT-5.2: 5.11 → 1.95 under Reflexion). Best F1 ~8.83% on blind defect discovery. | SNR is critical — a noisy reviewer trains developers to ignore it. Blind defect discovery in full PRs is much harder than injected-issue benchmarks. |
| [Qodo Benchmark](https://www.qodo.ai/blog/how-we-built-a-real-world-benchmark-for-ai-code-review/) | 100 PRs with 580 injected issues. Best F1 achieved was 60.1%. | Injected-issue benchmarks show higher F1 than blind discovery. Our thresholds (70% precision, 60% recall) are ambitious but achievable with known-issue golden cases. |
| [Inspect AI](https://inspect.aisi.org.uk/) (UK AI Security Institute) | Task/Solver/Scorer architecture with Docker sandbox. MIT licensed. | Validates our Dataset → Runner → Scorer separation of concerns. We don't need the full framework but should follow the pattern. |

### Design Principles (from Anthropic's eval guide)

These principles from [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) should guide our design:

1. **Start early, don't wait for perfection** — Ship with 20 golden cases, grow to 100+ over time
2. **Source tasks from real-world failures** — When a review misses a real bug in production, add that case to the suite
3. **Define unambiguous success criteria** — Each golden case must have a clear pass/fail definition, not a subjective judgment
4. **Combine multiple types of graders** — Deterministic matching + LLM-as-Judge + periodic human review
5. **Ensure tasks are sufficiently challenging** — If the suite passes at 100%, the cases are too easy. Target 70-85% pass rate for a well-tuned system
6. **Continuously iterate** — The eval suite is a living artifact, not a one-time deliverable
7. **Always read the transcripts** — When diagnosing failures, the full model response matters more than the parsed metrics

### CI/CD Integration Pattern

Based on [CodeRabbit's framework](https://www.coderabbit.ai/blog/framework-for-evaluating-ai-code-review-tools) and [OpenAI's eval flywheel](https://developers.openai.com/cookbook/examples/evaluation/building_resilient_prompts_using_an_evaluation_flywheel/):

```
PR changes prompt/parser/model config
  → CI triggers eval suite (--ci mode)
  → Scorecard posted as PR comment (before/after comparison)
  → If any threshold fails → build fails
  → If pass → scorecard archived for trend tracking
```

Treat prompts like code: version them, track ownership, require eval approval for changes that affect reviewer behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The eval suite runs all 20+ golden cases and produces a scorecard within 30 minutes
- **SC-002**: The eval suite correctly identifies a regression when the reviewer system prompt is degraded (e.g., removing the severity classification instruction causes severity accuracy to drop below threshold)
- **SC-003**: The false positive rate on clean code cases is measurably below 20% with the default model
- **SC-004**: A developer can add a new golden test case by creating a directory with a diff and expected.json — no code changes required
- **SC-005**: The eval suite can run in CI and post results as a PR comment
