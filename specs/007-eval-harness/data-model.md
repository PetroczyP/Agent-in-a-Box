# Data Model: Eval Harness (007)

**Date**: 2026-03-31
**Source**: spec.md Key Entities + research.md decisions

## Entity Relationship

```
EvalRun 1──* CaseResult
CaseResult 1──* TrialResult
TrialResult 1──* GraderResult
GraderResult *──0..1 ExpectedFinding (matched)
GoldenCase 1──* ExpectedFinding
GoldenCase 0..1──* TurnScript
GoldenCase 0..1── DualMetricConfig
EvalRun 1──1 AggregateMetrics
AggregateMetrics 1──* MetricWithSEM
Scorecard 1──1 EvalRun
Scorecard 0..1──1 ComparisonResult
```

## Entities

### GoldenCase

A curated test case loaded from `eval/fixtures/golden_cases/<case_id>/`. Corresponds to spec Key Entity "Golden Test Case."

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `case_id` | `str` | `meta.json` | Unique case identifier (directory name) |
| `description` | `str` | `meta.json` | Human-readable description of what this case tests |
| `source` | `GoldenCaseSource` | `meta.json` | Origin: `hand_curated`, `bug_fix_pr`, `vulnerability_dataset`, `synthetic` |
| `tags` | `list[str]` | `meta.json` | Categorization tags (e.g., `["security", "python"]`) |
| `bundle` | `ReviewBundle` | `bundle/` dir | The MCP input to send to `start_review` |
| `expected_findings` | `list[ExpectedFinding]` | `expected.json` | What the reviewer should find |
| `expected_non_findings` | `list[str]` | `expected.json` | `rule_id`s that should NOT appear (optional) |
| `multi_turn_script` | `list[TurnScript] \| None` | `script.json` | Discussion sequence for US2 cases (optional) |
| `dual_metric` | `DualMetricConfig \| None` | `meta.json` | For bug-fix PR cases with vulnerable + fixed versions (FR-015) |

### ExpectedFinding

What we expect the reviewer to find. Used by both Tier 1 (fingerprint matching) and Tier 2 (model-based context).

| Field | Type | Description |
|-------|------|-------------|
| `expected_id` | `str` | Unique within case: `EF-001`, `EF-002`, etc. |
| `rule_id` | `str` | Expected issue class (e.g., `sql-injection`) |
| `severity` | `Severity` | Expected severity: `BUG`, `WARN`, `NIT` |
| `category` | `Category` | Expected review dimension |
| `file` | `str` | Expected file path |
| `approximate_line` | `int` | Expected line number (Tier 1 uses +/- tolerance) |
| `description` | `str` | Human-readable description (provided to Tier 2 grader as context) |

### TurnScript

A scripted discussion turn for multi-turn eval cases (US2, FR-006/FR-007).

| Field | Type | Description |
|-------|------|-------------|
| `turn_number` | `int` | 1-based order within the script |
| `rebuttal_message_template` | `str` | Message template with `{finding_id}` placeholder, sent via `discuss` |
| `target_expected_id` | `str` | Which expected finding the rebuttal targets (e.g., `EF-001`) — stable across trials |
| `expected_status_after` | `FindingStatus` | Expected finding status after this turn |
| `is_valid_rebuttal` | `bool` | Whether the rebuttal is legitimately correct (for rebuttal accuracy) |

**Runtime resolution**: The reviewer assigns `finding_id` values (e.g., `F-001`) sequentially during parsing, so the same underlying issue may receive different IDs across trials. Scripts therefore reference the stable `target_expected_id`. After `start_review`, the runner:
1. Runs the **full grading pipeline** (Tier 1 fingerprint matching, then Tier 2 semantic grading for unmatched findings per FR-018) to classify all findings
2. Resolves `target_expected_id` → actual `finding_id` via the `matched_expected_id` field in any `GraderResult` with verdict `match` or `partial_match` (regardless of tier)
3. Substitutes the resolved `finding_id` into `rebuttal_message_template`
4. If the target expected finding was not matched by either tier in this trial, the turn is skipped and recorded as `finding_not_found` in `RebuttalResult`

### DualMetricConfig

Configuration for dual-metric testing (FR-015). References two bundle directories within the case directory.

| Field | Type | Description |
|-------|------|-------------|
| `vulnerable_dir` | `str` | Subdirectory name containing the vulnerable version bundle |
| `fixed_dir` | `str` | Subdirectory name containing the fixed version bundle |

### GraderResult

Output of grading a single reviewer finding. Corresponds to spec Key Entity "Grader Result."

| Field | Type | Description |
|-------|------|-------------|
| `tier` | `int` | Which grader produced this: `1` (fingerprint) or `2` (model-based) |
| `verdict` | `GraderVerdict` | `match`, `partial_match`, `novel_valid`, `no_match`, or `grading_error` |
| `confidence` | `GraderConfidence` | `high`, `medium`, `low` (Tier 1 always `high`) |
| `reasoning` | `str \| None` | Tier 2 only: model's explanation for the verdict |
| `matched_expected_id` | `str \| None` | Which expected finding it matched (e.g., `EF-001`), if any |
| `actual_finding_id` | `str` | The reviewer finding ID this grades (e.g., `F-001`) |

### TrialResult

Results from a single trial run of one golden case.

| Field | Type | Description |
|-------|------|-------------|
| `trial_number` | `int` | 1-based trial index |
| `findings` | `list[Finding]` | Raw findings from the reviewer |
| `graded` | `list[GraderResult]` | Grading result for each finding |
| `metrics` | `TrialMetrics` | Computed metrics for this trial |
| `error` | `str \| None` | Error message if the trial failed (rate limit exhaustion, timeout) |

### TrialMetrics

Per-trial computed metrics (before aggregation).

| Field | Type | Description |
|-------|------|-------------|
| `precision` | `float` | matched / (matched + no_match). Excludes novel_valid per FR-021. |
| `recall` | `float` | matched expected / total expected |
| `severity_accuracy` | `float` | Adjacency-weighted severity score / total matched (unique per expected ID). Adjacent mismatches (BUG↔WARN, WARN↔NIT) score 0.5; two-step (BUG↔NIT) scores 0.0. When multiple actuals match one expected, best score per expected ID is kept. |
| `category_accuracy` | `float` | Correct category / total matched (unique per expected ID). When multiple actuals match one expected, best score per expected ID is kept. |
| `snr` | `float` | (matched + novel_valid) / no_match per FR-004 |
| `novel_count` | `int` | Count of novel_valid findings |
| `grading_error_count` | `int` | Count of findings with grading_error verdict (excluded from all metrics) |
| `finding_count` | `int` | Total findings from reviewer |
| `severity_pairs` | `list[list[str]]` | Deduped (expected, actual) severity label pairs for kappa computation |

### CaseResult

Aggregated results for a single golden case across all trials.

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | `str` | Golden case ID |
| `trials` | `list[TrialResult]` | Individual trial results |
| `pass_at_1` | `dict[str, bool]` | Per expected finding: found on first trial? Key = `expected_id` |
| `pass_at_k` | `dict[str, bool]` | Per expected finding: found in any trial? Key = `expected_id` |
| `rebuttal_results` | `list[RebuttalResult] \| None` | For multi-turn cases only |
| `dual_metric_results` | `DualMetricResult \| None` | For dual-metric cases only |

### RebuttalResult

Result of a single rebuttal turn in a multi-turn case.

| Field | Type | Description |
|-------|------|-------------|
| `turn_number` | `int` | Which turn in the script |
| `target_expected_id` | `str` | The expected finding being rebutted (e.g., `EF-001`) — stable identity |
| `actual_finding_id` | `str \| None` | The runtime finding_id resolved for this trial (e.g., `F-003`), or `None` if not found |
| `expected_status` | `FindingStatus` | What the status should be |
| `actual_status` | `FindingStatus \| None` | What the status actually was, or `None` if finding not found |
| `correct` | `bool` | Whether expected == actual (always `false` if finding not found) |
| `finding_not_found` | `bool` | `true` if the target expected finding was not matched in this trial |

### DualMetricResult

Results from dual-metric testing (FR-015).

| Field | Type | Description |
|-------|------|-------------|
| `vulnerable_results` | `list[TrialResult]` | Trials against the vulnerable version (test recall) |
| `fixed_results` | `list[TrialResult]` | Trials against the fixed version (test FP suppression) |

### EvalRun

A complete evaluation run. Corresponds to spec Key Entity "Eval Run."

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | UUID4 unique run identifier |
| `timestamp` | `datetime` | UTC timestamp of run start |
| `model_evaluated` | `str` | Model used by the reviewer |
| `grader_model` | `str` | Model used for Tier 2 grading |
| `grader_prompt_version` | `str` | Version hash of grader prompt (FR-022) |
| `num_trials` | `int` | Trials per case |
| `line_tolerance` | `int` | Fingerprint line tolerance (default: 5) |
| `cases` | `list[CaseResult]` | Per-case results |
| `aggregate` | `AggregateMetrics` | Aggregated metrics with SEM |
| `pass_fail` | `bool` | Overall pass/fail against thresholds |
| `duration_seconds` | `float` | Total wall-clock time |

### AggregateMetrics

Aggregated metrics across all cases with statistical reporting (FR-016).

| Field | Type | Description |
|-------|------|-------------|
| `precision` | `MetricWithSEM` | Aggregate precision |
| `recall` | `MetricWithSEM` | Aggregate recall |
| `severity_accuracy` | `MetricWithSEM` | Aggregate severity accuracy |
| `category_accuracy` | `MetricWithSEM` | Aggregate category accuracy |
| `fp_rate` | `MetricWithSEM` | False positive rate on clean cases |
| `warn_rate` | `float` | WARN findings on clean-code cases (informational, not threshold-gated) |
| `rebuttal_accuracy` | `MetricWithSEM \| None` | Present whenever multi-turn cases exist. May carry `method="wilson_insufficient_n"` for small samples (rendered INCONCLUSIVE by the scorecard; non-gating under default `check_thresholds`; treated as fail under `--strict`). See DN-003. |
| `snr` | `MetricWithSEM` | Signal-to-noise ratio |
| `severity_qwk` | `float` | Quadratic-weighted Cohen's kappa for severity classification (informational, not threshold-gated) |
| `novel_count` | `int` | Total `novel_valid` findings across the run (sum of per-trial counts, per FR-004) |
| `pass_at_1_rate` | `float` | % of expected findings caught on first trial |
| `pass_at_k_rate` | `float` | % of expected findings caught in any trial |

### MetricWithSEM

A metric value with statistical error bounds (FR-016).

| Field | Type | Description |
|-------|------|-------------|
| `mean` | `float` | Average across trials |
| `sem` | `float` | Standard error of mean |
| `ci_lower` | `float` | Lower bound of 95% CI (method-dependent: normal-approx, Wilson score, or BCa bootstrap) |
| `ci_upper` | `float` | Upper bound of 95% CI (method-dependent: normal-approx, Wilson score, or BCa bootstrap) |
| `passes_threshold` | `bool` | Whether `ci_lower >= threshold` (for >= thresholds) or `ci_upper <= threshold` (for <= thresholds) |
| `method` | `CIMethod` | CI method used (see `CIMethod` enum below). Default `CIMethod.NORMAL`. |
| `status` (property) | `MetricStatus` | Derived outcome (`PASS`/`FAIL`/`INCONCLUSIVE`). Returns `INCONCLUSIVE` when `method == WILSON_INSUFFICIENT_N`; otherwise derived from `passes_threshold`. |

### Scorecard

The output artifact. Corresponds to spec Key Entity "Scorecard."

| Field | Type | Description |
|-------|------|-------------|
| `run` | `EvalRun` | The complete run data |
| `thresholds` | `dict[str, float]` | Threshold values used |
| `per_case_summary` | `list[CaseSummary]` | Condensed per-case results for display |
| `comparison` | `ComparisonResult \| None` | Delta vs baseline (if `--baseline` provided) |

### CaseSummary

Condensed per-case result for scorecard display (FR-014).

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | `str` | Golden case ID |
| `description` | `str` | Case description |
| `pass_fail` | `bool` | Did this case meet thresholds? |
| `precision` | `float` | Case-level precision |
| `recall` | `float` | Case-level recall |
| `finding_count` | `int` | Total findings produced |
| `expected_count` | `int` | Total expected findings |
| `novel_count` | `int` | Novel valid findings |

### ComparisonResult

Before/after delta for CI PR comments (FR-012a).

| Field | Type | Description |
|-------|------|-------------|
| `baseline_run_id` | `str` | ID of the baseline run |
| `baseline_timestamp` | `datetime` | When baseline was produced |
| `deltas` | `dict[str, MetricDelta]` | Per-metric deltas |
| `regressions` | `list[str]` | Metric names that regressed |
| `improvements` | `list[str]` | Metric names that improved |

### MetricDelta

| Field | Type | Description |
|-------|------|-------------|
| `baseline` | `float` | Previous value |
| `current` | `float` | Current value |
| `delta` | `float` | current - baseline |
| `delta_pct` | `float` | Percentage change |

## Enums

```python
class GoldenCaseSource(str, Enum):
    HAND_CURATED = "hand_curated"
    BUG_FIX_PR = "bug_fix_pr"
    VULNERABILITY_DATASET = "vulnerability_dataset"
    SYNTHETIC = "synthetic"

class GraderVerdict(str, Enum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    NOVEL_VALID = "novel_valid"
    NO_MATCH = "no_match"
    GRADING_ERROR = "grading_error"  # Tier 2 API failure after retries — excluded from all metrics

class GraderConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class CIMethod(str, Enum):
    NORMAL = "normal"                         # mean ± 1.96 × SEM
    WILSON = "wilson"                         # Wilson score interval (proportions, n sufficient)
    BCA = "bca"                               # BCa bootstrap (continuous metrics)
    VACUOUS = "vacuous"                       # metric undefined (e.g., fp_rate with no clean cases)
    WILSON_INSUFFICIENT_N = "wilson_insufficient_n"  # Wilson computed but sample too small to gate

class MetricStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"             # Returned when method == WILSON_INSUFFICIENT_N
```

Reused from `server.models`: `Severity`, `Category`, `FindingStatus`, `Location`, `Finding`, `ReviewBundle`.

**`wilson_insufficient_n` semantics**: scorecard renders the row as `INCONCLUSIVE`; `passes_threshold` reflects the natural Wilson result and is **not** forced; `check_thresholds` treats the metric as non-fatal unless called with `strict=True`.

## Storage

**Golden cases**: Directory-per-case in `eval/fixtures/golden_cases/`. No database. Cases are loaded at runtime by the `loader` module.

**Eval results**: Written to `eval/results/` as JSON files. No persistent storage — results are ephemeral output files. CI may archive these as build artifacts.

**Grader prompt**: Stored in `eval/fixtures/grader/` alongside golden cases. Versioned by content hash (SHA-256 of all prompt files). `VERSION.lock` records the last-accepted hash; `.accepted/` directory holds a snapshot of the last-accepted prompt files for consistency comparison (FR-022). See `grader-contract.md` for the full versioned-prompt workflow.

**Thresholds**: Default thresholds in `eval/fixtures/thresholds.json`. Overridable via `--thresholds` CLI flag (FR-012).
