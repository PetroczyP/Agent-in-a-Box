# Tasks: Prompt Tuning for Structured Copilot Output

**Input**: Design documents from `/specs/008-prompt-tuning/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US4)
- Exact file paths included in descriptions

---

## Phase 1: Setup

**Purpose**: Add new dependency, verify environment

- [x] T001 Add `json-repair>=0.50.0` to `requirements.txt` and `pyproject.toml` `[project] dependencies` (D-2, design R3 fix)
- [x] T002 Create curated validation samples in `tests/fixtures/validation_samples/` — derive from real PRs in explainIT-Home-Page: [PR #169](https://github.com/PetroczyP/explainIT-Home-Page/pull/169), [PR #108](https://github.com/PetroczyP/explainIT-Home-Page/pull/108), [PR #137](https://github.com/PetroczyP/explainIT-Home-Page/pull/137). Extract 3+ code snippets with known issues (at least one BUG, one WARN, one NIT). Include expected severity+category for SC-006 validation
- [x] T002b **Token Verification Gate**: Verify `GITHUB_TOKEN` in `.env` is a fine-grained PAT (`github_pat_` prefix) with `Copilot Requests` Account permission. Test with a minimal Copilot SDK call (`start()` + `list_models()`). Document token type and result. **BLOCKS all live Copilot testing** — coordinate with Peter if token needs to be regenerated

---

## Phase 2: Foundational — Fallback Regression Safety Net

**Purpose**: Lock existing parser behavior before modifying anything. These tests MUST PASS before AND after all changes (FR-009, SC-007)

**CRITICAL**: No parser or prompt modification until this phase is complete

- [x] T003 [P] Write regression test for JSON parse path in `tests/test_finding_parser.py` — valid JSON array input → `_try_json` succeeds, returns structured findings
- [x] T004 [P] Write regression test for regex fallback path in `tests/test_finding_parser.py` — semi-structured text with `**BUG** in \`file\`` pattern → `_try_regex` succeeds
- [x] T005 [P] Write regression test for NIT-wrap fallback path in `tests/test_finding_parser.py` — pure conversational text → `_wrap_as_nit` fires, returns single NIT finding

**Checkpoint**: All 3 fallback tiers have dedicated passing regression tests. Safety net established.

---

## Phase 3: User Story 1 — Structured Review Findings (Priority: P1) 🎯 MVP

**Goal**: Copilot returns JSON-parseable findings with accurate severity/category instead of conversational text

**Independent Test**: Send a review bundle with a known bug via `start_review`. Verify response parses as JSON with correct severity/category.

### TDD Tests for US1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T006 [P] [US1] Failing test: `REVIEWER_PERSONA` contains at least 2 few-shot examples (a BUG finding JSON + an empty array `[]`) in `tests/test_prompts.py`
- [x] T007 [P] [US1] Failing test: `build_review_context()` output ends with `FORMAT_REINFORCEMENT` text when `reinforce_format=True` (default) in `tests/test_prompts.py`
- [x] T008 [P] [US1] Failing test: `build_review_context(reinforce_format=False)` does NOT include reinforcement suffix in `tests/test_prompts.py`

### Implementation for US1

- [x] T010 [US1] Enhance `REVIEWER_PERSONA` in `server/prompts.py` with 2 few-shot format examples (FR-001, D-1): one BUG finding + one empty array. Examples derived from generalized Copilot review patterns
- [x] T011 [US1] Add `FORMAT_REINFORCEMENT` constant in `server/prompts.py` (FR-002, D-6). Add `reinforce_format: bool = True` parameter to `build_review_context()` that appends it as the final section
- [x] T012 [US1] Add inline comments to `server/prompts.py` documenting rationale for each prompt section (FR-008) — why few-shot, why reinforcement at end, why these specific examples

**Checkpoint**: US1 tests pass. `REVIEWER_PERSONA` has format examples, `build_review_context()` appends reinforcement. Prompt < 12,800 chars. Existing 154+ tests still pass.

---

## Phase 4: User Story 2 — Robust Parsing of Mixed Output (Priority: P2)

**Goal**: Parser extracts JSON from mixed output (prose + JSON, bare arrays, truncated responses) without falling to NIT-wrap

**Independent Test**: Feed parser a string with prose surrounding a JSON code fence. Verify JSON is extracted and parsed correctly.

### TDD Tests for US2

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T013 [P] [US2] Failing tests for mixed output in `tests/test_finding_parser.py`: (a) JSON inside ```json fence surrounded by prose, (b) bare JSON array in prose (no fence) → must be REJECTED (NIT-wrapped, not parsed) per trusted-container contract [coordinator resolution: Option B, 2026-03-18], (c) sentinel-delimited JSON surrounded by prose, (d) multiple JSON blocks merged (FR-003)
- [x] T014 [P] [US2] Failing tests for object unwrap in `tests/test_finding_parser.py`: `{"findings": [...]}` → extract inner array (FR-004)
- [x] T015 [P] [US2] Failing tests for truncated JSON repair in `tests/test_finding_parser.py`: unclosed brackets, trailing commas, truncated strings → `json-repair` recovers valid JSON (FR-007)

### Implementation for US2

- [x] T016 [US2] Harden `FindingParser._try_json` in `server/finding_parser.py` for mixed output (FR-003): extract from trusted containers ONLY — code fences, sentinel delimiters (`BEGIN_FINDINGS_JSON`/`END_FINDINGS_JSON`), whole-response JSON. Bare JSON in prose is explicitly rejected (NIT-wrapped) [coordinator resolution: Option B, 2026-03-18]
- [x] T017 [US2] Add JSON object unwrap to `_try_json` in `server/finding_parser.py` (FR-004): if parsed data is a dict with a list value (e.g., `{"findings": [...]}`), extract the list
- [x] T018 [US2] Add `json-repair` integration in `server/finding_parser.py` (FR-007): new `_try_json_repair` step between `_try_json` and `_try_regex` in `parse()` chain. Import `json_repair`, attempt repair before regex fallback

**Checkpoint**: US2 tests pass. Parser handles mixed output, object wrappers, and truncated JSON. Fallback regression tests (T003-T005) still pass.

---

## Phase 5: User Story 3 — Format Reinforcement in Follow-up (Priority: P2)

**Goal**: `discuss()` follow-up prompts reinforce JSON format while preserving conversational response contract

**Independent Test**: After `start_review`, call `discuss` and verify response contains both conversational text and parseable JSON findings.

### TDD Tests for US3

- [x] T019 [P] [US3] Failing test: `discuss()` prompt includes `DISCUSS_REINFORCEMENT` text appended after user message + additional files in `tests/test_review_engine.py`
- [x] T020 [P] [US3] Failing test: parser extracts findings from dual-format response (conversational text + JSON code fence at end) — `DiscussResult.response` contains full text (FR-010)

### Implementation for US3

- [x] T021 [US3] Add `DISCUSS_REINFORCEMENT` constant in `server/prompts.py` (FR-005, D-4): structured separator asking for conversational text first, then JSON findings in code fence at end
- [x] T022 [US3] Modify `ReviewEngine.discuss()` in `server/review_engine.py` to append `DISCUSS_REINFORCEMENT` after the follow-up prompt (user message + additional files), before sending to Copilot
- [x] T023 [US3] Verify parser handles dual-format discuss responses correctly (FR-010): JSON section extracted, full response preserved in `DiscussResult.response`

**Checkpoint**: US3 tests pass. `discuss()` reinforces format. Parser extracts from dual-format responses. Spec 001 `DiscussResult.response` contract preserved. All regression tests still pass.

---

## Phase 6: User Story 4 — Prompt Tuning Documentation (Priority: P3)

**Goal**: Prompt changes are documented so future maintainers understand rationale

- [x] T024 [US4] Review all modified files (`server/prompts.py`, `server/finding_parser.py`, `server/review_engine.py`) and ensure each prompt section and parser change has inline comments explaining purpose and rationale (FR-008)

**Checkpoint**: A developer reading the prompt file understands the purpose of each section without external docs.

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: Pre-live-testing verification of all code changes (test suite, prompt budget, fixtures, consistency)

- [x] T025 Run full test suite (`pytest`), verify zero regressions on 154+ existing tests (SC-004)
- [x] T026 Verify all 3 fallback tiers have dedicated passing regression tests (SC-007) — cross-reference T003-T005
- [x] T027 Add permanent prompt size guard test in `tests/test_prompts.py`: `assert len(REVIEWER_PERSONA) < 12_800` (SC-005). This is a post-change budget verification — the current prompt (~1,673 chars) passes today, so it is NOT a fail-first TDD test. It prevents future prompt growth from silently exceeding the budget
- [x] T028 [P] Update `tests/conftest.py` with new fixtures for mixed-output, truncated JSON, and dual-format response scenarios
- [x] T029 Cross-document consistency check: verify tasks.md ↔ spec.md FR coverage ↔ plan.md project structure alignment

---

## Phase 8: Live Validation & Prompt Iteration

**Purpose**: Empirical validation against live Copilot. This is the D-5 iteration loop that the feature exists to deliver.

**GATE**: T002b (PAT Verification) MUST pass before any task in this phase can execute.

- [x] T030 **Baseline measurement**: Send validation samples (T002) to live Copilot using the ORIGINAL prompt (pre-spec-008 REVIEWER_PERSONA, no few-shot examples, no FORMAT_REINFORCEMENT) via `tests/live_baseline.py`. Record: `_try_json` success count, `_wrap_as_nit` count, severity levels observed. This establishes the "before" state for comparison
- [x] T031 **Post-change measurement**: Send same validation samples to live Copilot using the UPDATED prompt (after Phases 3-6). Record: `_try_json` success rate (target: SC-001 >= 80%), `_wrap_as_nit` rate (target: SC-002 < 10%), distinct severity levels (target: SC-003 >= 2)
- [x] T032 **Classification accuracy scoring**: Compare live findings from T031 against expected severity+category in validation samples (T002). Score per SC-006: >= 70% of findings must match both expected severity AND expected category
- [x] T033 **Prompt iteration loop** (up to 6 rounds): If T031/T032 targets not met, adjust prompt wording in `server/prompts.py` (REVIEWER_PERSONA, FORMAT_REINFORCEMENT, or DISCUSS_REINFORCEMENT), re-run T031/T032. Each iteration: (1) hypothesize prompt change, (2) apply change, (3) run `pytest` to catch regressions, (4) re-measure live SC targets, (5) record delta. After 6 iterations, agent MUST prompt user: "6 iteration rounds completed. Current scores: [SC-001: X%, SC-002: X%, SC-006: X%]. Continue iterating or accept current results?"
- [x] T034 **Discuss live validation**: Send a `discuss` follow-up on an active session from T031. Verify: (a) `DiscussResult.response` contains conversational text, (b) parser extracts JSON findings from the response, (c) no regression from spec 001 contract (AC-1, AC-2, AC-3)

- [x] T035 **Post-iteration final verification**: After T033/T034 complete (i.e., after any prompt edits from the iteration loop), re-run: (a) `pytest` full suite — verify AC-4/SC-004 (zero regressions), (b) prompt size guard — verify SC-005 (`len(REVIEWER_PERSONA) < 12_800`), (c) fallback regression tests T003-T005 — verify SC-007 (all 3 tiers still pass), (d) discuss contract check — verify `DiscussResult.response` still contains conversational text. This ensures late prompt edits don't silently regress verified properties

**Checkpoint**: All SC targets met (or iteration cap reached with user acceptance). Live Copilot returns structured findings. Classification accuracy meets SC-006 threshold. Post-iteration verification confirms no regressions from prompt edits.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately. T002b (PAT gate) BLOCKS all live Copilot testing in test phase
- **Phase 2 (Foundational)**: Depends on Phase 1 (T001 for json-repair import in tests). BLOCKS all parser/prompt work
- **Phase 3 (US1)**: Depends on Phase 2 completion (safety net in place)
- **Phase 4 (US2)**: Depends on Phase 2 completion. Independent of Phase 3 (different files: parser vs prompts)
- **Phase 5 (US3)**: Depends on Phase 3 (FORMAT_REINFORCEMENT constant exists) and Phase 4 (parser handles mixed output)
- **Phase 6 (US4)**: Depends on Phase 3-5 (all code changes complete)
- **Phase 7 (Polish)**: Depends on Phase 3-6 completion
- **Phase 8 (Live Validation)**: Split dependency:
  - **T030 (baseline)**: Depends on T002b (PAT gate) + T002 (validation samples). Captures the "before" prompt behavior. NOTE: Per coordinator decision (release round 5), baseline was captured post-implementation using original prompt text — valid for parse-method metrics since _try_json vs _wrap_as_nit depends on prompt, not parser
  - **T031-T034**: Depend on Phase 7 completion (all code verified) + T002b (PAT gate)
  - **T035 (post-iteration verification)**: Depends on T033/T034 completion. MUST be the final task

### Within Each Phase

- TDD tests MUST be written and FAIL before implementation
- Implementation tasks are sequential within their story (they modify the same file)
- Tasks marked [P] across stories can run in parallel

### Parallel Opportunities

```
Phase 2:  T003 ─┐
          T004 ─┤ (all parallel — different test cases, same file but independent)
          T005 ─┘

Phase 3:  T006 ─┐                    T010 → T011 → T012
          T007 ─┤ (parallel tests)     (sequential implementation, same file)
          T008 ─┘

Phase 3 + Phase 4 partial overlap:
          US1 impl (prompts.py) ──────┐
          US2 tests (finding_parser)  ┤  (parallel — different files)
                                      └──→ US2 impl (finding_parser.py)

Phase 5:  T019 ─┐ (parallel tests)
          T020 ─┘
```

### FR → Task Traceability

| FR | Task(s) | Test(s) |
|----|---------|---------|
| FR-001 (few-shot examples) | T010 | T006 |
| FR-002 (format reinforcement) | T011 | T007, T008 |
| FR-003 (mixed output parsing) | T016 | T013 |
| FR-004 (object unwrap) | T017 | T014 |
| FR-005 (discuss reinforcement) | T021, T022 | T019 |
| FR-006 (prompt size) | T010, T011 | T027 |
| FR-007 (JSON repair) | T018 | T015 |
| FR-008 (documentation) | T012, T024 | — |
| FR-009 (fallback preservation) | — (preserved by design) | T003, T004, T005 |
| FR-010 (dual-format discuss) | T023 | T020 |

**SC → Live Validation Task Traceability:**

| SC | Live Task | Metric |
|----|-----------|--------|
| SC-001 (>=80% JSON parse) | T031 | `_try_json` success rate |
| SC-002 (<10% NIT-wrap) | T031 | `_wrap_as_nit` fire rate |
| SC-003 (2+ severity levels) | T031 | distinct severity count |
| SC-004 (154+ tests pass) | T025 | pytest exit code |
| SC-005 (prompt < 12,800 chars) | T027 | `len(REVIEWER_PERSONA)` |
| SC-006 (>=70% classification) | T032 | severity+category match rate |
| SC-007 (3 fallback regression tests) | T026 | test count per tier |

---

## Implementation Strategy

### MVP First (US1 Only — Phase 1-3)

1. Phase 1: Add json-repair dependency + create validation samples + verify PAT (T002b)
2. **T030 baseline** (if PAT verified): Measure original prompt's live Copilot parse-method behavior (per coordinator decision, baseline uses original prompt text with current parser — valid for parse-method metrics)
3. Phase 2: Establish fallback regression safety net
4. Phase 3: Enhance prompts with few-shot examples + format reinforcement
5. **STOP and VALIDATE**: Run full test suite. Verify prompt size < 12,800 chars

### Incremental Delivery

1. MVP (US1) → prompts tuned, reinforcement active
2. Add US2 → parser hardened for mixed/truncated output
3. Add US3 → discuss reinforcement active
4. Add US4 → documentation complete
5. Each story adds resilience without breaking previous stories

---

## Notes

- [P] tasks = different files or independent test cases, no dependencies
- Constitution: TDD for parser changes (US2), structural tests for prompt changes (US1)
- Live iteration with Copilot (D-5) is Phase 8 — explicit tasks T030-T035, gated by PAT verification (T002b). T035 is the mandatory final verification step
- **Iteration cap**: 6 rounds max for live prompt iteration. After 6 rounds, agent MUST prompt user: "6 iteration rounds completed. Continue iterating or accept current results?"
- Commit after each completed phase
