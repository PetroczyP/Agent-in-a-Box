# Tasks: Core Review Server (001)

**Input**: Design documents from `/specs/001-ai-code-reviewer/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, Docker configuration, test infrastructure

- [x] T001 Create project structure: `server/__init__.py`, `tests/__init__.py`, directory scaffolding per plan.md
- [x] T002 Create `pyproject.toml` with dependencies: `fastapi>=0.128`, `uvicorn`, `mcp>=1.0.0`, `github-copilot-sdk>=0.1.0`, `pydantic>=2.12`, `jinja2`; dev deps: `pytest`, `pytest-asyncio`
- [x] T003 [P] Create `requirements.txt` (pip-compile or manual pin from pyproject.toml)
- [x] T004 [P] Create `Dockerfile` — `python:3.11-slim-bookworm` base, install Node.js 22 + `@github/copilot` npm package, copy source, CMD `uvicorn server.main:app --host 0.0.0.0 --port 8080`
- [x] T005 [P] Create `docker-compose.yml` — single service, port 8080, `GITHUB_TOKEN` env var passthrough, health check config
- [x] T006 Create `tests/conftest.py` — shared fixtures: sample review bundle, mock Copilot client, sample findings

**Checkpoint**: Project builds and `pytest` runs (0 tests)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data types, utilities, and storage that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Tests (TDD — write first, must fail)

- [x] T007 [P] Write tests for Pydantic models in `tests/test_models.py` — validate enum values, field constraints, Finding fingerprint computation, serialization round-trips
- [x] T008 [P] Write tests for content denylist in `tests/test_denylist.py` — default patterns block `.env`/`*.pem`/`*.key`/`*credentials*`/`*secret*`/`*.p12`/`*.pfx`, custom patterns, case sensitivity, path-only matching (no content inspection)
- [x] T009 [P] Write tests for session store in `tests/test_store.py` — save/get/list_all, copilot session mapping, idempotency record save/get/token_exists_elsewhere, missing keys return None
- [x] T010 [P] Write tests for finding parser in `tests/test_finding_parser.py` — valid JSON input, malformed JSON fallback to regex, unparseable fallback to single NIT finding, fingerprint computation

### Implementation

- [x] T011 [P] Implement Pydantic models in `server/models.py` — all entities and enums from data-model.md: `SessionStatus`, `MessageSender`, `Severity`, `Category`, `Confidence`, `FindingStatus`, `Location`, `Finding`, `TokenUsage`, `Message`, `ReviewSession`, `IdempotencyRecord`, plus MCP I/O models: `ReviewBundle`, `ReviewResult`, `DiscussRequest`, `DiscussResult`, `SummaryRequest`, `ReviewSummary`, `SessionInfo`, `SessionList`
- [x] T012 [P] Implement content denylist in `server/denylist.py` — `ContentDenylist` class with `fnmatch`-based pattern matching per contracts/review-engine.md
- [x] T013 [P] Implement session store in `server/store.py` — `SessionStore` class with `_sessions`, `_copilot_sessions`, `_idempotency_records` dicts per data-model.md
- [x] T014 [P] Implement finding parser in `server/finding_parser.py` — `FindingParser` class: JSON parse → regex fallback → NIT wrap fallback; SHA-256 fingerprint computation per research.md Decision 7
- [x] T015 Create reviewer persona prompts in `server/prompts.py` — system prompt instructing Copilot to output JSON findings with severity/category/evidence per contracts/review-engine.md Context Ordering section

**Checkpoint**: All Phase 2 tests pass. Models, denylist, store, parser, and prompts are functional.

---

## Phase 3: User Story 1 — Submit Code for Review (Priority: P1) MVP

**Goal**: Claude Code calls `start_review` with a code bundle, receives SARIF-structured findings
**Independent Test**: Call `start_review` with a sample diff, verify findings returned with `finding_id`, severity, category, fingerprint

### Tests (TDD — write first, must fail)

- [x] T016 Write tests for Copilot client wrapper in `tests/test_copilot_client.py` — `CopilotReviewClient.start()`, `select_model()`, `create_review_session()`, `send_review()` with mocked SDK; error classification (auth → `CopilotAuthError`, timeout → `CopilotTimeoutError`, rate limit → `CopilotRateLimitError`); `is_connected` property
- [x] T017 Write tests for review engine `start_review` in `tests/test_review_engine.py` — happy path (bundle → findings), denylist rejection, empty diff rejection, bundle too large rejection, idempotency (duplicate token returns cached result), idempotency conflict (token reused cross-tool), Copilot timeout → retryable error, Copilot auth failure → terminal error
- [x] T018 Write tests for prompt construction in `tests/test_review_engine.py` — two boundaries per copilot-client.md contract: (a) verify `create_review_session(system_prompt=...)` receives the reviewer persona prompt containing FR-010 category instructions (correctness/design/tests/maintainability/security/style) and FR-011 evidence requirement for BUG/WARN findings; (b) verify the review context prompt passed to `send_review(prompt=...)` assembles sections in FR-008 order (conventions → anti_patterns → spec → diff → files → test_files → test_results → context). Tests capture both args via mocked Copilot client.
- [x] T019 Write tests for MCP `start_review` tool in `tests/test_mcp_tools.py` — tool registration, input validation, success response shape, error response shape

### Implementation

- [x] T020 Implement Copilot client wrapper in `server/copilot_client.py` — `CopilotReviewClient` class per contracts/copilot-client.md; **BUILD-PHASE SPIKE**: validate SDK API surface (6-item checklist from contract), implement primary path (`send_and_wait`) or fallback path (`send` + event collection); error classification layer (`CopilotError` hierarchy)
- [x] T021 Implement review engine `start_review` flow in `server/review_engine.py` — `ReviewEngine` class with `start_review()` per contracts/review-engine.md steps 1-10; context ordering per FR-008; bundle size check per FR-009; finding parsing; session creation; idempotency record storage
- [x] T022 Implement MCP server with `start_review` tool in `server/mcp_server.py` — `FastMCP("review-server")`, `@mcp.tool()` for `start_review`, wire to `ReviewEngine`; stdio entry point (`mcp.run()`)
- [x] T023 Implement FastAPI health endpoint in `server/main.py` — minimal FastAPI app, `/health` endpoint returning `{"status": "ok"}`, container CMD target

**Checkpoint**: `start_review` works end-to-end with mocked Copilot. All US1 tests pass (including prompt construction verification). Docker container starts and health check responds.

---

## Phase 4: User Story 2 — Multi-Turn Review Discussion (Priority: P2)

**Goal**: Claude Code calls `discuss` with rebuttals, receives updated findings; calls `get_review_summary` for final report
**Independent Test**: Start a review, call `discuss` with a rebuttal referencing a finding ID, verify response and finding status update; call `get_review_summary` and verify counts

### Tests (TDD — write first, must fail)

- [x] T024 Write tests for `discuss` flow in `tests/test_review_engine.py` — happy path (rebuttal → response + updated findings), session not found, session not active, denylist on additional files, idempotency (duplicate token), idempotency conflict, Copilot timeout, finding status updates
- [x] T025 Write tests for finding stability across discuss rounds in `tests/test_review_engine.py` — after `start_review` returns findings F-001/F-002/F-003, a `discuss` round MUST preserve existing `finding_id` and `fingerprint` values; new findings from follow-up get next sequential IDs; dismissed findings retain their original ID; reconciliation matches on `fingerprint` (SHA-256 of rule_id + normalized code) to detect same-finding across Copilot responses (AC-7, SC-008)
- [x] T026 [P] Write tests for `get_review_summary` in `tests/test_review_engine.py` — counts by severity/category/status, session not found
- [x] T027 [P] Write tests for MCP `discuss` and `get_review_summary` tools in `tests/test_mcp_tools.py` — tool registration, input/output shapes, error mapping

### Implementation

- [x] T028 Implement finding reconciliation in `server/review_engine.py` — after each `discuss` response, match Copilot's returned findings against existing session findings by `fingerprint`; preserve `finding_id` for matched findings, assign next sequential ID for new findings, update `status` for dismissed/fixed findings. This ensures AC-7: stable IDs and fingerprints across rounds
- [x] T029 Implement `discuss` flow in `server/review_engine.py` — `ReviewEngine.discuss()` per contracts/review-engine.md steps 1-9; denylist check on additional files (FR-007); calls finding reconciliation (T028) after parsing; idempotency with session-scoped key
- [x] T030 Implement `get_summary` flow in `server/review_engine.py` — `ReviewEngine.get_summary()` computing by_severity, by_category, by_status counts
- [x] T031 Add MCP tools for `discuss` and `get_review_summary` in `server/mcp_server.py` — `@mcp.tool()` decorators, wire to engine

**Checkpoint**: Multi-turn discussion works end-to-end with mocked Copilot. All US2 tests pass.

---

## Phase 5: User Story 3 — List Active Sessions (Priority: P3)

**Goal**: Claude Code calls `list_sessions` to see all review sessions with metadata
**Independent Test**: Create two sessions, call `list_sessions`, verify both appear with correct counts

### Tests (TDD — write first, must fail)

- [x] T032 Write tests for `list_sessions` in `tests/test_review_engine.py` — multiple sessions returned with correct metadata (severity/category counts, round count, branch), empty list when no sessions

### Implementation

- [x] T033 Implement `list_sessions` flow in `server/review_engine.py` — `ReviewEngine.list_sessions()` per contracts/mcp-tools.md `SessionInfo` shape
- [x] T034 Add MCP tool for `list_sessions` in `server/mcp_server.py` — `@mcp.tool()` decorator, wire to engine

**Checkpoint**: All 4 MCP tools functional. All US3 tests pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Docker validation, integration smoke test, cleanup

- [x] T035 Validate Docker build: `docker compose build` succeeds, `docker compose up -d` starts container, health check passes, `docker exec -i` MCP connection responds
- [x] T036 [P] Add Copilot SDK build-phase spike documentation: record actual API surface discovered in T020 into `specs/001-ai-code-reviewer/research.md` Decision 3 (update "confirmed" vs "needs validation" lists)
- [x] T037 [P] Create `.dockerignore` — exclude `.git/`, `__pycache__/`, `*.pyc`, `.env`, `specs/`, `agent-loop/`, `.specify/` (NOTE: `tests/` is NOT excluded — needed for in-container test runs in T039)
- [x] T038 [P] Create `.gitignore` — Python defaults + `__pycache__/`, `*.pyc`, `.env`, `*.egg-info/`, `dist/`, `htmlcov/`, `.coverage`
- [x] T039 Run full test suite inside Docker container (`docker exec <container> pytest`) to verify parity with host — tests are included in the image (see T037 note)

**Checkpoint**: Docker image builds, starts, responds to health check, and MCP tools are accessible via `docker exec -i`. All tests pass both on host and in container.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─── no deps, start immediately
     │
Phase 2 (Foundational) ─── depends on Phase 1
     │
     ├── Phase 3 (US1 - P1) ─── depends on Phase 2 ─── MVP
     │        │
     │        ├── Phase 4 (US2 - P2) ─── depends on Phase 3 (needs start_review to create sessions)
     │        │
     │        └── Phase 5 (US3 - P3) ─── depends on Phase 3 (needs sessions to list)
     │
Phase 6 (Polish) ─── depends on Phases 3-5
```

### Within Each Phase

- Tests MUST be written and FAIL before implementation (TDD per constitution)
- Models before services, services before MCP tools
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T003, T004, T005 can run in parallel
- **Phase 2**: All test tasks (T007-T010) in parallel; all impl tasks (T011-T015) in parallel (different files)
- **Phase 3**: Test tasks T016-T019 sequential (T016 first as copilot client is lowest dependency, T018 prompt tests before T019 MCP tests)
- **Phase 4**: T026, T027 in parallel; T024 first (discuss is the core), T025 (finding stability) after T024
- **Phase 5**: Small — sequential is fine
- **Phase 6**: T036, T037, T038 in parallel

### MVP Scope

**Minimum viable delivery = Phase 1 + Phase 2 + Phase 3 (through T023)**

This gives: `start_review` tool working end-to-end in Docker with health check. Claude Code can submit code and receive findings. Discussion and session listing are follow-on.

---

## Phase 7: Follow-Up (Post-MVP)

**Purpose**: Issues discovered during live testing that don't block MVP but need attention

- [ ] T040 Refine reviewer persona prompt in `server/prompts.py` to produce structured JSON output from Copilot. Live smoke test (2026-03-14) showed Copilot returns conversational text instead of the JSON finding format expected by `FindingParser`. The regex and NIT-wrap fallbacks handle this gracefully, but structured output is needed for reliable severity/category classification. Requires iterative tuning against real Copilot responses — not testable with mocks alone.

---

## Task Count Summary

| Phase | Tasks | Test Tasks | Impl Tasks |
|-------|-------|-----------|------------|
| Phase 1: Setup | 6 | 0 | 6 |
| Phase 2: Foundational | 9 | 4 | 5 |
| Phase 3: US1 (P1) | 8 | 4 | 4 |
| Phase 4: US2 (P2) | 8 | 4 | 4 |
| Phase 5: US3 (P3) | 3 | 1 | 2 |
| Phase 6: Polish | 5 | 0 | 5 |
| Phase 7: Follow-Up | 1 | 0 | 1 |
| **Total** | **40** | **13** | **27** |

**ID range**: T001–T040, no duplicates, no gaps.
