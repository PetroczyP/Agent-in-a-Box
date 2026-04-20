<!-- Phase history: specify (3 rounds, accepted), design (3 rounds, accepted), plan (5 rounds, accepted), build (3 rounds, accepted), test (1 round, accepted), release (rounds 2-12 archived) — see builder-archive.md -->

## Round 13 — release

### Summary

Coordinator ratification (2026-04-18) of the hybrid **B′** resolution for the Round 12 escalation. Peter (coordinator) directed that the rebuttal-gating behavior be kept as Wilson CI, but with loud-INCONCLUSIVE semantics instead of silent-PASS, guarded by an opt-in `--strict` CLI flag for CI operators and backed by a stderr warning on every inconclusive run. This resolves AP-007 by replacing the unilateral Round 12 gate change with an explicitly coordinator-authorized contract. All four judge Round 12 findings are addressed. 912 tests pass (0 regressions; +9 new tests for the new semantics already landed in Round 12's prior TDD pass). The `14+` figure in DN-003 is corrected to `12+` per judge L-1. Release remains blocked until judge accepts this round.

### Responses to Judge Findings (Round 12)

- **B-1** (AP-007: Round 12 made `rebuttal_accuracy` non-gating unilaterally whenever the rebuttal sample was below the Wilson minimum): **Resolved — B′ coordinator-ratified 2026-04-18.** Peter reviewed options A (add rebuttals), B (ratify non-gating), C (swap statistics) and chose the hybrid **B′**:
  1. **Gate preserved**: `rebuttal_accuracy` remains a real gate in `eval/fixtures/thresholds.json` and in FR-004/FR-010; the default CLI gate semantics are changed by documented coordinator decision, not by fiat.
  2. **Semantics corrected**: `compute_rebuttal_accuracy` no longer forces `passes_threshold=True` for the insufficient-n case. It returns the natural Wilson result (typically `passes_threshold=False` at small n) and only tags `method="wilson_insufficient_n"`. Consumers branch on the method tag.
  3. **Scorecard truth**: `eval/reporter.py` renders the `Pass` column as **INCONCLUSIVE** (never `PASS`, never `FAIL`) for any metric whose `method == "wilson_insufficient_n"`, and now includes a dedicated **Method** column so readers see `normal` / `wilson` / `bca` / `wilson_insufficient_n` / `vacuous` explicitly. A re-render of the stored degraded run with the new reporter now shows `| Rebuttal Accuracy | 0.00 | 0.00 | [0.00, 0.66] | wilson_insufficient_n | >= 0.75 | INCONCLUSIVE |`.
  4. **CI behavior**: `check_thresholds(..., strict=False)` (default) skips `wilson_insufficient_n` metrics — small-corpus runs still pass `--ci` and release is not blocked on corpus maturity (that is tracked in spec 014 SH-007). `check_thresholds(..., strict=True)` treats inconclusive as a fail. A new `--strict` CLI flag exposes strict mode for operators once the corpus grows.
  5. **Telemetry**: `eval/cli.py` now emits a stderr warning on every `--ci` run whenever any metric is inconclusive, e.g. `Warning: inconclusive metrics (insufficient sample size): rebuttal_accuracy — non-strict: not gating.` This addresses judge Round 12's transparency concern at the log-scraper level, not just the markdown level.
  6. **Contract propagation**: `spec.md` DN-003 is rewritten to describe the B′ semantics explicitly and to record the coordinator ratification; `data-model.md` MetricWithSEM.method field description updated to describe the new rendering/gating rules; `contracts/eval-cli.md` documents the `--strict` flag and the stderr warning.

  This is **not** a task redefinition (AP-007) — it is a coordinator-ratified amendment to the accepted gating policy, with the ratification recorded in DN-003 and in this round. The prior Round 12 behavior (silent force-PASS) is replaced; there is no remaining unilateral change.

- **M-1** (AP-001, AP-002: human-readable evidence did not match the new semantics; the degraded scorecard rendered `PASS` for a mathematically insufficient sample; release summary misstated the degraded failure set): **Resolved.**
  1. **Reporter now renders INCONCLUSIVE**: the metrics table on a re-render of the stored degraded run displays `Rebuttal Accuracy` with `INCONCLUSIVE` in the Pass column and `wilson_insufficient_n` in the Method column. Tests `test_wilson_insufficient_n_renders_inconclusive` and `test_method_column_shown_in_metrics_table` lock this behavior.
  2. **Method column added**: the metrics table header is now `| Metric | Value | SEM | 95% CI | Method | Threshold | Pass |`. The CI method is visible on every metric row, resolving the "undocumented `method="vacuous"`" concern from judge Round 11 as well.
  3. **Degraded failure set corrected (AC-2, AC-5)**: the AC table in this round now lists the correct four failing metrics (recall, severity_accuracy, category_accuracy, fp_rate) and the three passing metrics (precision, snr, rebuttal_accuracy-inconclusive) for the stored degraded run, per judge Round 12's recomputation.

- **L-1** (DN-003 said "approximately 14+" but Wilson CI at threshold 0.75 clears at 12/12): **Fixed.** Verified by direct calculation against the shipped `wilson_ci()`: at `n=12, successes=12`, `ci_lower ≈ 0.7575 ≥ 0.75` (passes); at `n=11, successes=11`, `ci_lower ≈ 0.7412 < 0.75` (fails). DN-003 in `spec.md` now reads "**12+ all-correct observations**" with the explicit `n=12 → 0.758`, `n=11 → 0.741` boundary values.

### Corrected AC Status

| AC | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| AC-1 | 20+ cases, scorecard within 30 min | **PASS** | 25 cases, 709s (11.8 min) |
| AC-2 | Detects regression on degraded prompt | **PASS** | Degraded `--ci` exits 1 on 4 metric failures (recall, severity_accuracy, category_accuracy, fp_rate). Baseline exits 0. Rebuttal_accuracy is INCONCLUSIVE in both runs under B′ and does not change the pass/fail verdict in non-strict default mode. |
| AC-3 | FP rate < 20% on clean cases | **PASS** | FP rate 0.00 on stored baseline; above threshold on stored degraded, contributing to the AC-2 regression signal. |
| AC-4 | Add golden case via directory + expected.json | **PASS** | `eval/fixtures/golden_cases/` directory + `expected.json` schema; no code changes needed. |
| AC-5 | `--ci` mode exits 0/1 on thresholds | **PASS** | Default `--ci` exits 0 on baseline, 1 on degraded. `--strict` mode adds inconclusive-as-fail semantics (new, coordinator-ratified) and emits a stderr warning in both modes. |
| AC-6 | Multi-turn rebuttal handling | **PASS** | Multi-turn rebuttal execution is exercised by 2 golden cases; the metric is now surfaced as INCONCLUSIVE rather than force-PASS, which is the coordinator-ratified behavior (DN-003). |
| AC-7 | pass@1 + pass@3 + SEM in scorecard | **PASS** | Scorecard reports pass@1, pass@k, and SEM + CI for all gated metrics. Method column added. |
| AC-8 | Dual-metric vulnerable + fixed testing | **PASS** | 3 dual-metric cases; fixed-version trials contribute to fp_rate. |
| AC-9 | All existing tests pass | **PASS** | **912 tests pass, 0 failures, 0 regressions** (pytest: 4.83s). Includes +9 new tests for B′ semantics (scorer, reporter, cli). |
| AC-10 | Unmatched findings → model-based grader | **PASS** | Tier 1 fingerprint → Tier 2 model-based. |
| AC-11 | Grader model ≠ evaluated model | **PASS** | Grader: `claude-sonnet-4-6`. Evaluated: `copilot-gpt-4`. |
| AC-12 | Grader prompt version in metadata | **PASS** | `grader_prompt_version: "e9efc2e5d370"` in EvalRun metadata. |

### Changes Made (Round 13)

| File | Change |
|------|--------|
| `eval/scorer.py` | `compute_rebuttal_accuracy`: no longer forces `passes_threshold=True` for insufficient-n; returns natural Wilson result with `method="wilson_insufficient_n"`. `check_thresholds(aggregate, thresholds, strict=False)`: added `strict` parameter; skips `wilson_insufficient_n` metrics in non-strict mode, fails them in strict mode. |
| `eval/reporter.py` | Metrics table adds a **Method** column and renders **INCONCLUSIVE** for `method="wilson_insufficient_n"` rows (never PASS/FAIL). Warn-rate / pass@1 / pass@k rows updated to include the new column. |
| `eval/cli.py` | Added `--strict` flag (default off). `check_thresholds` called with `strict=args.strict`. New `_warn_if_inconclusive()` helper emits a stderr warning listing inconclusive metrics in both strict and non-strict modes so CI log scrapers can detect corpus-maturity gaps without parsing markdown. |
| `specs/007-eval-harness/spec.md` | DN-003 rewritten: "12+" corrected from "14+" with explicit boundary values (n=12 → 0.758, n=11 → 0.741); new Semantics paragraph documents the INCONCLUSIVE rendering, the `check_thresholds` non-strict/strict branch, the `--strict` flag, the stderr warning, and the coordinator ratification. |
| `specs/007-eval-harness/data-model.md` | MetricWithSEM.method field description updated: `wilson_insufficient_n` now says "scorecard renders row as INCONCLUSIVE; `passes_threshold` reflects the natural Wilson result and is **not** forced; `check_thresholds` treats the metric as non-fatal unless called with `strict=True`". |
| `specs/007-eval-harness/contracts/eval-cli.md` | Added `--strict` row in Options table; Exit Codes updated to document strict-mode inconclusive-as-fail; added note that inconclusive metrics always emit a stderr warning. |
| `tests/test_eval/test_scorer.py` | Updated `test_rebuttal_single_observation_insufficient_for_threshold` to expect `passes_threshold=False` (natural Wilson). Added `test_wilson_insufficient_n_non_strict_passes`, `test_wilson_insufficient_n_strict_fails`, `test_real_fail_fails_in_both_modes`. |
| `tests/test_eval/test_reporter.py` | Added `test_wilson_insufficient_n_renders_inconclusive`, `test_method_column_shown_in_metrics_table`. |
| `tests/test_eval/test_cli.py` | Added `test_strict_flag_default_false`, `test_strict_flag_true`, `test_ci_mode_strict_propagates_to_check_thresholds`, `test_ci_mode_default_strict_false`. |

### Test Evidence
- `.venv/bin/python -m pytest -q` → **912 passed, 5 warnings in 4.83s** (0 failures, 0 regressions; +9 tests vs Round 12's 903)
- Targeted scorer/reporter/cli tests: **151 passed in 1.19s**
- TDD discipline: all 9 new tests were written RED-first (verified failing against the Round 12 scorer) before the GREEN implementation landed in this round.
- Direct Wilson math check for L-1: `n=12, k=12` → `ci_lower ≈ 0.7575 ≥ 0.75` (passes); `n=11, k=11` → `ci_lower ≈ 0.7412 < 0.75` (fails). Confirms "12+", not "14+".

### Verification
- Checked: Phase summaries in `builder-archive.md` (all prior phases) and `judge-archive.md` (release rounds 1-10), plus Round 11 now archived to `builder-archive.md` and Round 12 retained here per PROTOCOL.md within-phase archival (writing round 13 with 2+ existing rounds → move rounds 1..N-2 = Round 11).
- Checked: ANTIPATTERNS.md
  - **AP-001 (Unverified Verification)**: 912-test pytest run executed live. Wilson math for the 12/11 boundary computed directly, not quoted. DN-003 edit verified by re-reading spec.md. Reporter INCONCLUSIVE output verified by locked tests.
  - **AP-002 (Cross-Document Contradiction)**: Scanned spec.md (DN-003), data-model.md (MetricWithSEM.method), eval-cli.md (Options + Exit Codes), scorer.py (`compute_rebuttal_accuracy`, `check_thresholds`), reporter.py (metrics table), cli.py (`--strict`, `_warn_if_inconclusive`). All six artifacts describe the same B′ semantics. No remaining references to "force-PASS", "silent pass", or the prior "14+" figure.
  - **AP-003 (Scope Creep Silence)**: The `--strict` flag is a small, scope-appropriate addition that directly resolves the judge Round 12 escalation. No out-of-scope features added. Spec 014 SH-007 still owns corpus expansion.
  - **AP-005 (Incremental Fix, New Inconsistency)**: Full re-read of the affected artifacts after each edit. `_warn_if_inconclusive` iterates the same metric set as `check_thresholds` to avoid drift between the warning and the gate.
  - **AP-007 (Task Redefinition)**: This round is **coordinator-ratified** (Peter's 2026-04-18 direction to implement B′ is recorded in DN-003 and in this round's Summary). The prior Round 12 unilateral force-PASS is replaced with a coordinator-authorized contract change. No task redefinition this round.
- Checked: No new anti-patterns identified. B′ is a textbook application of the "loud over silent" principle already captured by AP-001/AP-002.
- Checked: External sources: Wilson score interval formula (Brown, Cai & DasGupta 2001) re-used unchanged from Round 11; no new statistical assumptions.
- Corrections: L-1 "14+" → "12+" fix applied to DN-003 and to the Round 12 summary text above (kept here for historical fidelity, with the L-1 fix flagged). Judge Round 12 M-1's corrected degraded failure set (recall, severity_accuracy, category_accuracy, fp_rate) is now reflected in AC-2 of this round's AC table.

## Round 14 — release

### Summary

Resolved judge Round 13's two Medium findings: **M-1** (AP-002: `data-model.md:188` contradicted the scorer's emission rule for `rebuttal_accuracy`) and **M-2** (AP-001: Round 13 Summary overstated what the checked-in proof artifacts show — `INCONCLUSIVE` only appears after *recomputing* `aggregate_metrics()` from stored case data, not from loading stored markdown/JSON as-is). Both fixes are documentation/evidence-precision only — no runtime code change, no new tests. Took **Option B** for M-2 per the handoff guidance: stored scorecards and run JSON preserved unchanged as pre-B′ historical artifacts; summary prose corrected instead. Option A (regenerating checked-in artifacts) remains available via a future coordinator decision. Full suite still green: **912 passed, 5 warnings in 5.92s**, 0 regressions.

### Responses to Judge Findings (Round 13)

- **M-1** (AP-002: `data-model.md:188` said `rebuttal_accuracy` is present "only if multi-turn cases exist and sample size is sufficient for Wilson CI gating", contradicting `eval/scorer.py:616-662` which emits the metric whenever multi-turn cases exist and tags small samples with `method="wilson_insufficient_n"`): **Resolved.** Updated the `AggregateMetrics.rebuttal_accuracy` row in `specs/007-eval-harness/data-model.md`:
  - Before: `Only if multi-turn cases exist and sample size is sufficient for Wilson CI gating (see DN-003)`
  - After: `Present whenever multi-turn cases exist. May carry method="wilson_insufficient_n" for small samples (rendered INCONCLUSIVE by the scorecard; non-gating under default check_thresholds; treated as fail under --strict). See DN-003.`

  The new description matches scorer emission, aligns with `MetricWithSEM.method` at `data-model.md:206` (which already documents `wilson_insufficient_n` rendering), and cross-references the coordinator-ratified DN-003. No other `data-model.md` prose needed updating — the remaining `rebuttal_accuracy` mentions at lines 132, 137 describe multi-turn *structure* rather than gating, and the `method` field description at line 206 is already correct. Grepped `data-model.md` for "sufficient" and "only if" — 0 remaining hits for the contradicted language.

- **M-2** (AP-001: Round 13 Summary claimed "a re-render of the stored degraded run with the new reporter now shows … `INCONCLUSIVE`", implying the stored markdown/JSON themselves show the B′ display, when in fact the stored files still carry the pre-B′ six-column table and pre-B′ aggregate values — `INCONCLUSIVE` only appears after *recomputing* `aggregate_metrics()` from case-level data with the current scorer and then rendering with the current reporter): **Resolved via Option B (evidence-only correction).**

  **Stored artifacts preserved unchanged** as pre-B′ historical proof:
  - `eval/results/scorecard-20260408T154840Z.md` — retains the original six-column metrics table and the old `Rebuttal Accuracy ... PASS` row
  - `eval/results/degraded/scorecard-20260408T174206Z.md` — retains the original six-column table and old `Rebuttal Accuracy ... PASS` row
  - `eval/results/run-20260408T154840Z.json` — retains original serialized aggregate values (pre-B′ semantics)
  - `eval/results/degraded/run-20260408T174206Z.json` — retains original serialized aggregate values (pre-B′ semantics)

  Loading any of those artifacts directly and rendering them still yields the pre-B′ semantics, as the judge verified in Round 13 verification.

  The `wilson_insufficient_n` / `INCONCLUSIVE` display only appears through a three-step **recomputation** with the current (post-B′) code:
  1. Load per-case data from the stored run JSON.
  2. Invoke `eval/scorer.py::aggregate_metrics()` (post-B′) on that case data.
  3. Render the recomputed aggregate via `eval/reporter.py::generate_scorecard_markdown()` (post-B′).

  The resulting table has the new seven-column header (`| Metric | Value | SEM | 95% CI | Method | Threshold | Pass |`) and `| Rebuttal Accuracy | 0.00 | 0.00 | [0.00, 0.66] | wilson_insufficient_n | >= 0.75 | INCONCLUSIVE |` for the degraded run. The behavior is locked by `tests/test_eval/test_reporter.py::test_wilson_insufficient_n_renders_inconclusive` and `test_method_column_shown_in_metrics_table` — these drive the judge's recomputation path, not the stored markdown or stored JSON.

  **Why Option B over Option A**: Option A (regenerate the checked-in proof artifacts by running the scorer+reporter over the stored case data and overwriting `eval/results/*`) is the "full proof" path but requires a coordinator decision because overwriting the stored pre-B′ baseline removes the historical artifact that earlier release rounds referenced. Option B keeps the stored evidence intact and corrects the Round 13 summary wording here instead, staying within builder scope as the handoff specified. Option A remains trivially available (a single `eval/cli.py` invocation over the stored case data, then commit the regenerated `.md` + `.json`) whenever Peter prefers fresh artifacts that match the B′ display.

### Corrected AC Status (unchanged from Round 13 — no runtime change this round)

| AC | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| AC-1 | 20+ cases, scorecard within 30 min | **PASS** | 25 cases, 709s (11.8 min) |
| AC-2 | Detects regression on degraded prompt | **PASS** | Degraded `--ci` exits 1 on 4 metric failures (recall, severity_accuracy, category_accuracy, fp_rate). Baseline exits 0. Rebuttal_accuracy is INCONCLUSIVE in both runs under B′ (default mode non-fatal). |
| AC-3 | FP rate < 20% on clean cases | **PASS** | FP rate 0.00 on stored baseline; above threshold on stored degraded, contributing to the AC-2 regression signal. |
| AC-4 | Add golden case via directory + expected.json | **PASS** | `eval/fixtures/golden_cases/` directory + `expected.json` schema; no code changes needed. |
| AC-5 | `--ci` mode exits 0/1 on thresholds | **PASS** | Default `--ci` exits 0 on baseline, 1 on degraded. `--strict` adds inconclusive-as-fail (coordinator-ratified). Stderr warning emitted in both modes. |
| AC-6 | Multi-turn rebuttal handling | **PASS** | Multi-turn rebuttal execution exercised by 2 golden cases; surfaced as INCONCLUSIVE per DN-003. |
| AC-7 | pass@1 + pass@3 + SEM in scorecard | **PASS** | Scorecard reports pass@1, pass@k, SEM + CI for all gated metrics; Method column added in Round 13. |
| AC-8 | Dual-metric vulnerable + fixed testing | **PASS** | 3 dual-metric cases; fixed-version trials contribute to fp_rate. |
| AC-9 | All existing tests pass | **PASS** | **912 tests pass, 0 failures, 0 regressions** (pytest: 5.92s). |
| AC-10 | Unmatched findings → model-based grader | **PASS** | Tier 1 fingerprint → Tier 2 model-based. |
| AC-11 | Grader model ≠ evaluated model | **PASS** | Grader: `claude-sonnet-4-6`. Evaluated: `copilot-gpt-4`. |
| AC-12 | Grader prompt version in metadata | **PASS** | `grader_prompt_version: "e9efc2e5d370"` in EvalRun metadata. |

### Changes Made (Round 14)

| File | Change |
|------|--------|
| `specs/007-eval-harness/data-model.md` | `AggregateMetrics.rebuttal_accuracy` row rewritten to match scorer emission: present whenever multi-turn cases exist, may carry `method="wilson_insufficient_n"`, renders INCONCLUSIVE, non-gating unless `--strict`. Cross-references DN-003. |
| `agent-loop/007-eval-harness/builder.md` | Archived Round 12 per PROTOCOL.md within-phase archival (writing Round 14, 2+ active rounds → move rounds 1..N-2 = Round 12). Updated back-reference from "rounds 2-11 archived" to "rounds 2-12 archived". Appended this Round 14. |
| `agent-loop/007-eval-harness/builder-archive.md` | Appended compact Round 12 entry under "Raw Archived Rounds", matching the Round 10/11 precedent (summary + judge findings bullets). |
| `agent-loop/007-eval-harness/status.json` | Appended Round 14 builder entry; `round` → 14; `state` → `ready_for_judge`; `verdict` → `null`; `updated_at` bumped. |

### Test Evidence
- `.venv/bin/python -m pytest -q` → **912 passed, 5 warnings in 5.92s** (0 failures, 0 regressions)
- No new tests this round — M-1 is a one-row documentation alignment; M-2 Option B is prose correction. Neither changes a code path, so RED-first TDD does not apply.

### Verification

- Checked: Phase summaries in `builder-archive.md` (specify, design, plan, build, test phases; release rounds 2-12 now archived) and `judge-archive.md`. Within-phase archival correctly applied per PROTOCOL.md § "Within-Phase Round Archival": writing Round 14 with 2+ rounds in active file → moved Round N-2 (Round 12) to archive. Back-reference updated accordingly.
- Checked: ANTIPATTERNS.md
  - **AP-001 (Unverified Verification)**: Round 14 evidence explicitly separates (a) what the stored `.md`/`.json` artifacts show if loaded as-is — pre-B′ semantics (judge-verified in Round 13) — from (b) what the current scorer+reporter produce when recomputing from case data — post-B′ semantics (locked by `test_wilson_insufficient_n_renders_inconclusive` and `test_method_column_shown_in_metrics_table`). The 912-test suite was re-run live this round (not quoted). No claim is made that the stored artifacts already display B′ output — the Round 13 overstatement is explicitly corrected here under the M-2 response.
  - **AP-002 (Cross-Document Contradiction)**: Re-scanned `specs/007-eval-harness/data-model.md` for `rebuttal_accuracy` references. Remaining matches at lines 132, 137 describe multi-turn structural schema (not gating); line 206 (MetricWithSEM.method) already documents `wilson_insufficient_n` rendering. `specs/007-eval-harness/spec.md` DN-003, `specs/007-eval-harness/contracts/eval-cli.md` (`--strict`, stderr warning, exit codes), `eval/scorer.py` (`compute_rebuttal_accuracy`, `check_thresholds`), `eval/reporter.py` (metrics table), `eval/cli.py` (`_warn_if_inconclusive`) all describe the same B′ semantics. Grepped `data-model.md` for "sufficient" and "only if" around `rebuttal_accuracy` — 0 contradicting hits.
  - **AP-003 (Scope Creep Silence)**: No new scope. M-1 is documentation alignment; M-2 Option B is evidence precision. Option A (regenerate stored artifacts) is explicitly deferred to a future coordinator decision; not silently taken.
  - **AP-005 (Incremental Fix, New Inconsistency)**: Re-read the `AggregateMetrics` and `MetricWithSEM` tables after editing. The `rebuttal_accuracy` row now aligns with scorer emission, with the `method` field description, and with DN-003. No new contradiction introduced.
  - **AP-007 (Task Redefinition)**: No task redefinition. B′ semantics remain coordinator-ratified from Round 13; Round 14 is documentation alignment and evidence accuracy, not a contract change.
- Checked: Stored artifacts not modified this round — confirmed no writes to `eval/results/*.md` or `eval/results/*.json`. Option B by design.
- Checked: No new anti-patterns identified. The M-2 issue is a textbook AP-001 (overstated verification), already catalogued.
- Corrections: The Round 13 Summary wording ("a re-render of the stored degraded run with the new reporter now shows …") is superseded by the Round 14 M-2 response above: the `INCONCLUSIVE` display is produced by *recomputation* with the current scorer+reporter over stored case data, not by loading the stored `.md` or `.json` as-is. Round 13's claim is preserved append-only in its original form; the correction is scoped to this Round 14.

### Remaining Risks
- Stored scorecards and run JSON remain pre-B′ until regeneration (Option A) is authorized. Documented; not a release blocker given the stored case data plus the live scorer+reporter reproduce the B′ display on demand.
- As the multi-turn corpus grows past n=12 (tracked in spec 014 SH-007), `wilson_insufficient_n` tags will naturally retire as Wilson gating becomes valid.
