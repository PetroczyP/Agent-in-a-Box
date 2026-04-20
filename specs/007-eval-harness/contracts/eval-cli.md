# Eval CLI Contract: Eval Harness (007)

## Entry Point

```bash
python -m eval [OPTIONS]
```

The eval harness is invoked as a Python module from the host machine (not inside Docker).

## Options

| Flag | Type | Default | Description | FR |
|------|------|---------|-------------|-----|
| `--trials` | `int` | `3` | Number of trials per golden case | FR-011 |
| `--ci` | `flag` | `false` | CI mode: exit 0/1, output markdown scorecard | FR-010, FR-012a |
| `--grader-model` | `str` | `claude-sonnet-4-6` | Model for Tier 2 grading | FR-020 |
| `--thresholds` | `path` | `eval/fixtures/thresholds.json` | Custom threshold file | FR-012 |
| `--baseline` | `path` | `None` | Previous run JSON for comparison | FR-012a |
| `--cases` | `str` | `all` | Comma-separated case IDs to run (e.g., `case-001,case-003`) | — |
| `--container` | `str` | auto-detect | Docker container name/ID for the reviewer | — |
| `--output-dir` | `path` | `eval/results/` | Where to write result files | FR-009 |
| `--line-tolerance` | `int` | `5` | Line number tolerance for fingerprint matching | FR-005 |
| `--max-retries` | `int` | `3` | Max retries per case on rate limit/timeout | FR-013 |
| `--prompt-consistency-check` | `flag` | `false` | Run old-vs-new grader prompt comparison (FR-022) | FR-022 |
| `--accept-prompt` | `flag` | `false` | Accept current grader prompt as new baseline (FR-022) | FR-022 |
| `--verbose` | `flag` | `false` | Print per-case progress to stderr | — |
| `--concurrency` | `int` | `5` | Max concurrent case executions | — |
| `--strict` | `flag` | `false` | Strict mode: inconclusive (`wilson_insufficient_n`) metrics fail the `--ci` gate. Default: inconclusive metrics surface on the scorecard (rendered as INCONCLUSIVE) and emit a stderr warning but do not flip the exit code. See DN-003 and spec 014 SH-007. | DN-003 |

## Exit Codes

| Code | Meaning | When |
|------|---------|------|
| `0` | All thresholds pass | `--ci` mode, all metrics meet thresholds (non-strict: inconclusive metrics are skipped; strict: zero inconclusive and all pass) |
| `1` | Threshold failure | `--ci` mode, one or more metrics below threshold; or in `--strict` mode one or more metrics are inconclusive (`wilson_insufficient_n`) |
| `2` | Runtime error | Container not running, no API key, fixture load error |

In non-CI mode, exit code is always `0` unless a runtime error occurs (`2`).

Inconclusive metrics always emit a stderr warning listing the affected metrics, regardless of `--strict`, so CI log scrapers can detect corpus-maturity gaps without parsing markdown.

## Output Files

Each run produces two files in `--output-dir`:

| File | Format | Description |
|------|--------|-------------|
| `run-{timestamp}.json` | JSON | Full `EvalRun` serialized. Machine-readable. Used as `--baseline` input. |
| `scorecard-{timestamp}.md` | Markdown | Human-readable scorecard table. In `--ci` mode, also printed to stdout for PR comment capture. |

## Thresholds File Format

```json
{
  "precision": 0.70,
  "recall": 0.60,
  "severity_accuracy": 0.80,
  "category_accuracy": 0.70,
  "fp_rate": 0.20,
  "rebuttal_accuracy": 0.75,
  "snr": 3.0
}
```

`fp_rate` uses `<=` comparison (lower is better). All others use `>=` (higher is better).
Threshold comparison uses `ci_lower` per FR-016. CI method varies by metric: Wilson score for Bernoulli proportions (fp_rate, rebuttal_accuracy), BCa bootstrap for rate aggregations (precision, recall, severity/category accuracy, SNR). See the `method` field in each metric for the specific CI method used.

## Container Auto-Detection

When `--container` is not provided, the CLI runs:
```bash
docker compose ps --format json
```
and selects the first running container from the project's compose file. If no container is found, exits with code `2` and a clear error message.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For Tier 2 | API key for the Tier 2 grader model |
| `EVAL_CONTAINER` | No | Alternative to `--container` flag |

## Errors

| Condition | Behavior |
|-----------|----------|
| Container not running | Exit code 2: "No running AgentinaBox container found" |
| `ANTHROPIC_API_KEY` not set | Exit code 2: "ANTHROPIC_API_KEY required for Tier 2 grading" |
| Fixtures directory missing | Exit code 2: "No golden cases found in eval/fixtures/golden_cases/" |
| Case ID not found | Exit code 2: "Case not found: {case_id}" |
| MCP connection failure | Retry per FR-013, then exit code 2 |
| Grader API failure | Retry per FR-013, then `GraderResult(verdict="grading_error")` — excluded from all metrics. If >50% of a trial's findings are grading_error, the trial is marked as errored. |
| Grader prompt changed | Exit code 2: "Grader prompt changed. Run --prompt-consistency-check" (FR-022) |
