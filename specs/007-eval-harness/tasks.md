# Tasks: Eval Harness (007)

**Source**: plan.md + spec.md + data-model.md + contracts/
**Generated**: 2026-04-01

## AC Coverage Matrix

| AC | Tasks | What satisfies it |
|----|-------|-------------------|
| AC-1 | T010, T014, T015 | Runner executes cases; T014 curates 20+ fixture library; T015 validates < 30 min live |
| AC-2 | T010, T013, T015 | Integration test degrades prompt; T015 validates regression detection live |
| AC-3 | T006, T014, T015 | Scorer computes FP rate; T014 includes 5+ clean-code cases; T015 measures <20% live |
| AC-4 | T002, T012 | Loader discovers cases by directory structure; no code changes needed to add a case |
| AC-5 | T011, T013 | CLI `--ci` mode exits 0/1; integration test verifies |
| AC-6 | T006, T007, T010 | Runner executes multi-turn scripts; scorer computes rebuttal_accuracy; reporter shows it in scorecard |
| AC-7 | T006, T007 | Scorer computes pass@1/pass@k + SEM; reporter includes them in scorecard |
| AC-8 | T010 | Runner executes dual-metric (vulnerable + fixed) runs |
| AC-9 | T013 | All existing tests pass after harness is added |
| AC-10 | T004, T005 | Model grader uses structured rubric + few-shot; pipeline routes to it |
| AC-11 | T004, T011 | Model grader accepts `--grader-model`; CLI records it in metadata |
| AC-12 | T008, T011 | Prompt version hash recorded in EvalRun; CLI checks VERSION.lock |

## Dependency Graph

```
T001 (models)
├─→ T002 (loader)
├─→ T003 (fingerprint grader)
├─→ T004 (model grader)
├─→ T006 (scorer)
├─→ T008 (prompt version)
└─→ T009 (mcp client)

T003 + T004 ──→ T005 (grading pipeline)
T006 ────────→ T007 (reporter)
T002 + T005 + T006 + T009 ──→ T010 (runner)
T007 + T008 + T010 ─────────→ T011 (cli)
T002 + T008 ─→ T012 (starter fixtures)
T011 + T012 ─→ T013 (integration test)
T012 ────────→ T014 (full fixture library)
T011 + T014 ─→ T015 (live validation run)
```

**Critical path**: T001 → T003/T004 → T005 → T010 → T011 → T013 → T014 → T015

---

## Phase 1: Foundation

### T001: Package scaffolding + Pydantic models

**Goal**: Create the harness package structure and all Pydantic models from data-model.md.

**Files to create**:
- `eval/__init__.py` — package marker
- `eval/__main__.py` — stub entry point (`python -m eval`)
- `eval/models.py` — all 18 entities/enums from data-model.md
- `tests/test_eval/__init__.py` — test package marker
- `tests/test_eval/conftest.py` — shared test fixtures (sample GoldenCase, sample Finding, factory helpers)
- `tests/test_eval/test_models.py` — model validation tests

**TDD checkpoint**:
- RED: Test model instantiation, enum membership, JSON round-trip serialization, validation rejection of invalid data (wrong enum value, missing required field, negative trial_number)
- GREEN: Implement all models. Reuse `Severity`, `Category`, `FindingStatus`, `Location`, `Finding`, `ReviewBundle` from `server.models` via import
- REFACTOR: Extract shared conftest factories

**Dependencies**: None
**ACs**: Foundation for all

---

## Phase 2: Core Modules

All tasks in this phase depend only on T001 and can be implemented in parallel.

### T002: Golden case loader

**Goal**: Load and validate golden cases from the fixtures directory.

**Files to create**:
- `eval/loader.py`
- `tests/test_eval/test_loader.py`

**TDD checkpoint**:
- RED: Test loading a valid case directory (meta.json + expected.json + bundle/); test missing required file raises clear error; test optional script.json and dual_metric loading; test `--cases` filter by case ID
- GREEN: Implement `load_cases(fixtures_dir, case_ids=None) -> list[GoldenCase]`. Walk directories, parse JSON, validate against Pydantic models
- REFACTOR: Ensure SC-004 — adding a new case = creating a directory, no code changes

**Dependencies**: T001
**ACs**: AC-4

### T003: Tier 1 fingerprint grader

**Goal**: Deterministic finding matcher per grader-contract.md.

**Files to create**:
- `eval/graders/__init__.py`
- `eval/graders/fingerprint.py`
- `tests/test_eval/test_fingerprint.py`

**TDD checkpoint**:
- RED: Test exact match (rule_id + file + line within tolerance → `match`); test partial match (rule_id + file + line match, severity differs → `partial_match`); test no match (wrong rule_id → `None`); test line tolerance boundary (exactly at tolerance, one beyond); test multiple-match resolution (smallest line distance wins); test one-expected-to-one-actual constraint (first claim wins)
- GREEN: Implement `grade_finding()` per grader-contract.md interface. Track claimed expected findings
- REFACTOR: Extract match-scoring helper

**Dependencies**: T001
**ACs**: AC-2, AC-10 (Tier 1 part)

### T004: Tier 2 model grader

**Goal**: Anthropic API-based semantic grader per grader-contract.md.

**Files to create**:
- `eval/graders/model_grader.py`
- `tests/test_eval/test_model_grader.py`

**TDD checkpoint**:
- RED: Test with mocked Anthropic API returning valid JSON → correct GraderResult; test `grading_error` on API failure after retries; test JSON parse failure → re-prompt once → `grading_error`; test prompt includes expected findings, rubric, few-shot examples; test `matched_expected_id` set correctly for `match`/`partial_match`
- GREEN: Implement `async grade_finding()` per grader-contract.md. Build prompt from template + expected findings. Parse structured JSON response. Handle retries + error paths
- REFACTOR: Extract prompt builder function for testability

**Dependencies**: T001
**ACs**: AC-10, AC-11

### T006: Scorer (metrics + SEM)

**Goal**: Compute all metrics from grading results per FR-004, FR-016, FR-017, FR-021.

**Files to create**:
- `eval/scorer.py`
- `tests/test_eval/test_scorer.py`

**TDD checkpoint**:
- RED: Test precision formula (excludes `novel_valid` per scoring contract table); test recall formula; test SNR formula; test severity/category accuracy; test MetricWithSEM computation (mean, sem, ci_lower, ci_upper); test threshold comparison uses `ci_lower` not raw mean; test `fp_rate` uses `<=` comparison; test pass@1 and pass@k across trials; test `grading_error` findings excluded from all metrics; test edge cases (zero denominator handling); test `rebuttal_accuracy` computation (correct_count / total from RebuttalResult list across trials); test `rebuttal_accuracy` threshold check (>= 0.75, uses `ci_lower`); test `rebuttal_accuracy` is `None` when no multi-turn cases exist; test `finding_not_found` rebuttals count as incorrect
- GREEN: Implement `compute_trial_metrics()`, `aggregate_metrics()`, `compute_rebuttal_accuracy(case_results) -> MetricWithSEM | None`, `MetricWithSEM.from_values()`, `check_thresholds()` (including `rebuttal_accuracy` threshold when present)
- REFACTOR: Ensure scoring contract table from FR-021 is the single source of truth

**Dependencies**: T001
**ACs**: AC-3, AC-6, AC-7

### T008: Prompt version manager

**Goal**: VERSION.lock + .accepted/ workflow per FR-022 and grader-contract.md.

**Files to create**:
- `eval/prompt_version.py`
- `tests/test_eval/test_prompt_version.py`

**TDD checkpoint**:
- RED: Test hash computation (SHA-256 of prompt_template + rubric + few_shot_examples); test clean state (hash matches VERSION.lock → ok); test dirty state (hash differs → PromptDirtyError); test `--prompt-consistency-check` writes `checked_hash` to VERSION.lock; test `--accept-prompt` with valid `checked_hash` → copies to .accepted/, updates VERSION.lock; test `--accept-prompt` with stale `checked_hash` → rejects; test first-time setup (no VERSION.lock → auto-initialize)
- GREEN: Implement `check_prompt_version()`, `run_consistency_check()`, `accept_prompt()`, `compute_prompt_hash()`
- REFACTOR: Separate state checking from side effects

**Dependencies**: T001
**ACs**: AC-12

### T009: MCP client wrapper

**Goal**: MCP stdio client via docker exec per mcp-transport.md.

**Files to create**:
- `eval/mcp_client.py`
- `tests/test_eval/test_mcp_client.py`

**TDD checkpoint**:
- RED: Test `StdioServerParameters` construction with container name; test `call_tool("start_review", ...)` sends correct arguments; test response parsing (TextContent → JSON → Pydantic model); test error handling (rate_limited → retry, auth_failed → abort, connection lost → abort); test container auto-detection via `docker compose ps --format json`
- GREEN: Implement `connect(container) -> AsyncContextManager[ClientSession]`, `call_start_review()`, `call_discuss()`, `call_get_review_summary()`, `detect_container()`. Use `mcp.client.stdio.stdio_client` + `mcp.client.session.ClientSession`
- REFACTOR: Extract retry logic into shared helper (used by both MCP and Anthropic retries)

**Dependencies**: T001
**ACs**: AC-9 (via correct MCP usage)

---

## Phase 3: Composition

### T005: Grading pipeline

**Goal**: Tier 1 → Tier 2 routing per FR-018.

**Files to create**:
- `eval/graders/pipeline.py`
- `tests/test_eval/test_pipeline.py`

**TDD checkpoint**:
- RED: Test Tier 1 match stops pipeline (no Tier 2 call); test Tier 1 miss forwards to Tier 2; test claimed-expected tracking prevents double-counting (first match wins, second forwarded); test mixed results (some Tier 1, some Tier 2); test all `grading_error` from Tier 2 still returns results (not exception)
- GREEN: Implement `async grade_all_findings(findings, expected_findings, ...) -> list[GraderResult]`. Iterate findings: try Tier 1, if None forward to Tier 2. Track claimed expected IDs
- REFACTOR: Ensure pipeline is stateless between calls (claimed set per invocation)

**Dependencies**: T003, T004
**ACs**: AC-2, AC-10

### T007: Reporter + scorecard

**Goal**: Generate markdown + JSON scorecards per FR-009, FR-012a, FR-014.

**Files to create**:
- `eval/reporter.py`
- `tests/test_eval/test_reporter.py`

**TDD checkpoint**:
- RED: Test markdown scorecard contains all metrics with SEM bounds; test per-case breakdown (FR-014); test JSON output matches EvalRun schema; test baseline comparison (delta computation, regression/improvement detection); test CI-mode markdown includes before/after table; test pass@1/pass@k in scorecard; test `rebuttal_accuracy` included in scorecard with SEM when multi-turn cases present; test `rebuttal_accuracy` row omitted from scorecard when no multi-turn cases
- GREEN: Implement `generate_scorecard(run, thresholds) -> Scorecard`, `render_markdown(scorecard) -> str`, `render_json(scorecard) -> str`, `compare_runs(current, baseline) -> ComparisonResult`. Scorecard includes `rebuttal_accuracy` conditionally
- REFACTOR: Extract markdown table formatting helper

**Dependencies**: T006
**ACs**: AC-6, AC-7, AC-8 (reporting side)

---

## Phase 4: Integration

### T010: Runner (case x trial orchestration)

**Goal**: Orchestrate full harness execution: case loop, trial loop, multi-turn, dual-metric.

**Files to create**:
- `eval/runner.py`
- `tests/test_eval/test_runner.py`

**TDD checkpoint**:
- RED: Test single-turn flow (mocked MCP + grader) → produces CaseResult with trials; test multi-turn finding ID resolution (target_expected_id → actual finding_id via grading results, both Tier 1 and Tier 2 matches); test multi-turn skip when target not found (finding_not_found); test dual-metric runs vulnerable + fixed versions; test retry on rate limit (case retried, not whole run); test errored trial handling (>50% grading_error → trial.error set)
- GREEN: Implement `async run_eval(cases, session, grader_model, num_trials, ...) -> EvalRun`. For each case x trial: call start_review, grade findings, optionally run multi-turn script, compute trial metrics. Aggregate across trials
- REFACTOR: Extract finding ID resolver into testable function

**Dependencies**: T002, T005, T006, T009
**ACs**: AC-1, AC-2, AC-6, AC-8

### T011: CLI + entry point

**Goal**: argparse with 14 flags, 3 exit codes per eval-cli.md. Wire all modules together.

**Files to create/update**:
- `eval/cli.py` — new
- `eval/__main__.py` — update stub to call cli
- `tests/test_eval/test_cli.py` — new

**TDD checkpoint**:
- RED: Test 14 flags parse correctly with defaults; test exit code 0 on all thresholds pass; test exit code 1 on threshold failure; test exit code 2 on runtime error (no container, no API key, bad fixtures); test `--ci` mode prints markdown to stdout; test `--prompt-consistency-check` and `--accept-prompt` invoke prompt_version module; test dirty prompt state → exit code 2 with clear message; test `--baseline` loads previous run for comparison; test `--grader-model` passed through to runner; test `--verbose` enables progress output to stderr
- GREEN: Implement `def main() -> int`. Parse args, load config, check prompt version, connect MCP, run harness, generate scorecard, handle exit codes. Wire loader → runner → scorer → reporter pipeline
- REFACTOR: Keep main() thin — delegate to module functions

**Dependencies**: T007, T008, T010
**ACs**: AC-5, AC-11, AC-12

---

## Phase 5: Validation

### T012: Starter golden case fixtures

**Goal**: Create minimum fixture set for harness testing. Not the full 20+ production suite — enough to validate the pipeline end-to-end.

**Files to create**:
- `eval/fixtures/golden_cases/case-001/` — bug case (known issue, expected finding)
- `eval/fixtures/golden_cases/case-002/` — clean code case (no expected findings)
- `eval/fixtures/golden_cases/case-003/` — multi-turn case (with script.json)
- `eval/fixtures/grader/prompt_template.txt` — initial grader prompt
- `eval/fixtures/grader/rubric.md` — grading rubric
- `eval/fixtures/grader/few_shot_examples.json` — 3+ labeled examples
- `eval/fixtures/thresholds.json` — default thresholds from spec
- `.gitignore` update — add `eval/results/`

**TDD checkpoint**:
- RED: Loader tests from T002 already validate fixture format. Add tests that the starter fixtures load without errors
- GREEN: Create fixture directories with realistic content. Prompt template follows grader-contract.md structure
- REFACTOR: Ensure fixture quality — descriptions are clear, expected findings are unambiguous

**Dependencies**: T002, T008
**ACs**: AC-4

### T013: End-to-end integration test

**Goal**: Full pipeline test validating all ACs. Uses mocked MCP (no live container) for deterministic results.

**Files to create**:
- `tests/test_eval/test_integration.py`

**TDD checkpoint**:
- RED: Test full CLI invocation with mocked MCP → scorecard generated with correct metrics; test `--ci` exit code 0 with passing thresholds; test `--ci` exit code 1 with failing thresholds; test regression detection (swap mock responses to simulate degraded prompt); test multi-turn mock case produces `rebuttal_accuracy` in scorecard with hand-calculated correct value; test existing project tests still pass (`pytest tests/ --ignore=tests/test_eval/test_integration.py`)
- GREEN: Create integration test with comprehensive mock MCP that returns predetermined findings (including multi-turn rebuttal responses). Verify scorecard metrics match hand-calculated values including `rebuttal_accuracy`
- REFACTOR: Extract mock MCP factory for reuse

**Dependencies**: T011, T012
**ACs**: AC-1, AC-2, AC-3, AC-5, AC-9

---

## Phase 6: Calibration

### T014: Full golden case fixture library

**Goal**: Curate the complete 20+ case corpus per FR-002. Expands the 3 starter cases from T012 to the full production set.

**Fixture requirements (FR-002)**:
- 10+ cases with known bugs/issues (security, logic, performance, etc.)
- 5+ cases with clean code (no expected findings — used for FP measurement)
- 5+ cases testing specific review dimensions (security, design, tests, documentation)
- At least 2 multi-turn cases with rebuttal scripts (script.json)
- At least 2 dual-metric cases with vulnerable + fixed versions

**Files to create**:
- `eval/fixtures/golden_cases/case-004/` through `case-020+/` — additional case directories
- Each case: `meta.json`, `expected.json`, `bundle/` (diff + files), optional `script.json`, optional `dual_metric/`

**TDD checkpoint**:
- RED: Loader (T002) validates all fixtures load without errors; verify at least 10 bug cases, 5 clean cases, 5 dimension-specific cases exist; verify at least 2 multi-turn cases with non-empty script.json; verify at least 2 dual-metric cases
- GREEN: Create fixture directories with realistic, representative content sourced from real review scenarios
- REFACTOR: Ensure case descriptions are clear, expected findings are unambiguous, rebuttal scripts have deterministic expected outcomes

**Dependencies**: T012
**ACs**: AC-1, AC-3, AC-4

### T015: Live validation run

**Goal**: Execute the complete harness against a live AgentinaBox Docker instance with the full fixture library and spec-default thresholds. Record the result as acceptance evidence.

**Validation targets**:
- AC-1: 20+ cases produce a scorecard within 30 minutes
- AC-2: Degrading the system prompt causes metric regression (severity_accuracy or recall drops below threshold)
- AC-3: False positive rate (BUG-only) on clean-code cases is measurably below 20%. WARN findings tracked as `warn_rate` (informational).
- Rebuttal accuracy meets >= 75% threshold on multi-turn cases

**Note**: T015 is a manual validation procedure, not a code implementation task. It does not follow the TDD checkpoint pattern — results are recorded as evidence (scorecard JSON + duration log) to prove the ACs against a live instance.

**Procedure**:
1. Start AgentinaBox container (`docker compose up -d`)
2. Run `python -m eval --output-dir eval/results/ --verbose` — full suite against frozen T014 fixtures and spec-default thresholds
3. Record scorecard metrics and duration as-is — this is the acceptance evidence for AC-1/AC-3
4. Run `python -m eval --ci` — verify exit code 0 on passing thresholds (proves baseline reviewer meets all spec-default thresholds)
5. Degrade the system prompt using multi-component ablation: replace the entire `REVIEWER_PERSONA` in `server/prompts.py` with `"Review this code."` (a single sentence with no JSON schema, no severity taxonomy, no few-shot examples, no rules). Re-run `python -m eval --ci` — expect metric regression (severity_accuracy or recall drops below threshold) and `--ci` exit code 1 (AC-2). Restore the original prompt after recording results. Note: single-instruction removal (e.g. removing just the severity section) proved insufficient — the model uses JSON examples as implicit severity guides regardless of instructions

**If thresholds fail**: Record the failure as evidence. Do NOT adjust fixtures or thresholds within this run. Fixture corrections (fixing genuinely wrong expected findings) go through a T014 update committed before a fresh T015 rerun. Only the SNR threshold is explicitly calibratable per spec (FR-004: "calibrate after initial eval runs"); all other thresholds are spec-defined defaults.

**Dependencies**: T011, T014
**ACs**: AC-1, AC-2, AC-3

---

## Implementation Order (sequential)

For a single-builder workflow, the recommended execution order is:

1. **T001** — models (foundation for everything)
2. **T002** — loader (validates fixture format early)
3. **T003** — fingerprint grader (Tier 1, fast to implement)
4. **T004** — model grader (Tier 2, more complex)
5. **T005** — pipeline (combines T003 + T004)
6. **T006** — scorer (metrics, independent of grading)
7. **T007** — reporter (depends on scorer)
8. **T008** — prompt version (independent)
9. **T009** — mcp client (independent)
10. **T010** — runner (wires loader + pipeline + scorer + mcp)
11. **T011** — cli (wires everything together)
12. **T012** — starter fixtures (needs fixture + prompt format)
13. **T013** — integration test (validates everything)
14. **T014** — full fixture library (curate 20+ cases per FR-002)
15. **T015** — live validation run (proves AC-1, AC-2, AC-3 against live instance with frozen fixtures/thresholds)
