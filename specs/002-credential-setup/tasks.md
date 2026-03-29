# Tasks: Credential Setup & Management

**Input**: Design documents from `/specs/002-credential-setup/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story. TDD is mandatory per constitution — write failing tests before implementation (RED-GREEN-REFACTOR).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Project Configuration)

**Purpose**: Docker configuration, dependencies, and UI infrastructure needed before any module work.

- [x] T001 Update `requirements.txt` — add `cryptography>=44.0.0`
- [ ] T002 [P] Update `Dockerfile` — add `RUN mkdir -p /data && chmod 700 /data`
- [ ] T003 [P] Update `docker-compose.yml` — add named volume `review-data:/data`, change port to `127.0.0.1:8080:8080` (FR-008), add secrets section
- [ ] T004 [P] Create `server/templates/base.html` — layout template with nav, flash message area, footer; monospace dark theme; links to style.css
- [ ] T005 [P] Create `server/static/style.css` — single CSS file, monospace dark theme per constitution

**Checkpoint**: Infrastructure ready — module implementation can begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core credential storage and resolution modules that ALL user stories depend on.

**CRITICAL**: No user story work can begin until CredentialStore and CredentialResolver are implemented.

### CredentialStore (TDD)

- [ ] T006 Write failing tests for `CredentialStore` in `tests/test_credential_store.py` (RED). Cover: `store()` creates key + encrypted file + metadata, `load()` decrypts, `load()` returns None on missing key (FR-001 key loss), `load()` returns None on missing file, `delete()` removes credential files but keeps key, `has_stored_credential()`, `get_metadata()`, `update_last_validated()`, atomic writes via `os.replace()`
- [ ] T007 Implement `CredentialStore` in `server/credential_store.py` (GREEN). Follow contract at `specs/002-credential-setup/contracts/credential-store.md`. Fernet key at `/data/.fernet_key` (chmod 600), encrypted token at `/data/credentials.enc`, metadata at `/data/credential_meta.json`. Use `os.replace()` for atomic writes.

### CredentialResolver (TDD)

- [ ] T008 Write failing tests for `CredentialResolver` in `tests/test_credential_resolver.py` (RED). Cover: Docker secret > env var > stored priority (FR-002), whitespace stripping on all sources (edge case), returns None when no source available, `get_source()` returns correct `CredentialSource` enum, logging source type without token value (FR-007)
- [ ] T009 Implement `CredentialResolver` in `server/credential_resolver.py` (GREEN). Follow contract at `specs/002-credential-setup/contracts/credential-resolver.md`. Priority: Docker secret (`/run/secrets/github_token`) > env var (`GITHUB_TOKEN`) > stored credential. Strip whitespace from all sources. No caching — fresh on each `resolve()` call.

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 — First-Time Setup via Web UI (Priority: P1) MVP

**Goal**: New user opens localhost:8080, sees setup wizard, pastes PAT, gets validated and stored, redirected to status page.

**Independent Test**: Start container with no credentials, open localhost:8080, verify wizard appears, paste valid PAT, verify redirect to status page.

### Tests for US1 (RED — write first, must fail)

- [ ] T010 Write failing tests for `TokenValidator` in `tests/test_token_validator.py` (RED). Cover: `validate_format()` accepts `github_pat_` prefix, rejects `ghp_`/`gho_`/`ghs_`/`ghu_`/empty with specific error messages and URLs per contract; `_probe_github_auth()` raises auth error on 401 with verbose message and URL per contract, returns True on 2xx, returns None on other status codes; `validate_copilot_access()` raises permission error with verbose message and URL per contract when `github_auth_confirmed=True` and Copilot fails, raises auth (combined) with verbose message and URL when `github_auth_confirmed=None` and Copilot fails, raises sdk error with verbose message and URL per contract on ImportError/CopilotUnavailableError; `validate()` orchestrates all three steps correctly. All 4 error types (format, auth, permission, sdk) must assert message content and remediation URLs matching the accepted templates in `contracts/token-validator.md` (AC-3)
- [ ] T011 [P] Write failing tests for setup + status web routes in `tests/test_web_routes.py` (RED). Cover: GET `/` redirects to `/setup` when no credential (AC-1), GET `/` renders status page with source + masked token when credential exists, GET `/setup` renders wizard when no credential (AC-1), GET `/setup` redirects to `/` when credential exists, POST `/setup` with valid token → validates + stores + redirects to `/?msg=saved` (AC-2), POST `/setup` with invalid token → re-renders setup with error message (AC-3), `mask_token()` helper shows prefix + last 4 chars

### Implementation for US1 (GREEN)

- [ ] T012 Implement `TokenValidator` in `server/token_validator.py` (GREEN). Follow contract at `specs/002-credential-setup/contracts/token-validator.md`. Three-step validate: format → `_probe_github_auth()` (urllib.request via asyncio.to_thread) → `validate_copilot_access()` (temporary CopilotReviewClient). Verbose error messages with URLs per error messages section of contract.
- [ ] T013 [P] Create `server/templates/setup.html` — extends base.html; PAT creation instructions (step-by-step: go to github.com/settings/tokens?type=beta, generate token, enable copilot_requests); token input form with "Save & Test Connection" button; error display area
- [ ] T014 [P] Create `server/templates/status.html` — extends base.html; shows credential source and masked token; flash message display; link to Settings page; MUST NOT claim connection status (FR-009)
- [ ] T015 Implement setup + status routes in `server/web_routes.py` (GREEN). Follow contract at `specs/002-credential-setup/contracts/web-routes.md`. GET `/` (redirect to /setup if no credential, else render status), GET `/setup`, POST `/setup` (validate → store → redirect with PRG pattern). Include `mask_token()` helper.
- [ ] T016 Update `server/main.py` — mount `Jinja2Templates("server/templates")`, mount `StaticFiles` for `server/static`, include `web_routes` router, instantiate shared `CredentialStore`/`CredentialResolver`/`TokenValidator`

### MCP Credential Integration (TDD)

- [ ] T017 Write failing tests for MCP credential integration in `tests/test_mcp_server_config.py` (RED). Extend existing MCP test surface to cover: `_initialize_copilot()` uses `CredentialResolver.resolve()` instead of `os.environ.get("GITHUB_TOKEN")`, `_startup_error` set to `NoCredentialError` with message listing all 3 credential methods when `resolve()` returns None (FR-010), after storing new token via `CredentialStore.store()` next MCP connection picks up updated credential (AC-5 rotation). Also add `NoCredentialError` → `"no_credential"` error-mapping test in `tests/test_mcp_handlers.py` for the `start_review` handler only (following existing pattern at `test_auth_error_maps_correctly`), verifying the error does NOT fall through to `"internal"`. Note: `discuss` does not need this test — its code path (`send_followup()` → `send_review()`) never checks `_startup_error`; if no credential was configured, no session exists, so `discuss` hits `session_not_found` first
- [ ] T018 Update `server/mcp_server.py` and `server/copilot_client.py` (GREEN) — first add `NoCredentialError(CopilotError)` class to `server/copilot_client.py` (extends existing hierarchy, `retryable = False`, fits `_startup_error: CopilotError | None` type). Then in `server/mcp_server.py`: (a) replace `os.environ.get("GITHUB_TOKEN")` in `_initialize_copilot()` with `CredentialResolver.resolve()`, setting `_startup_error` as `NoCredentialError` when `resolve()` returns None (FR-010); (b) add `except NoCredentialError` handler to the `start_review` tool handler only, mapping to `{"error": "no_credential", "message": str(e), "retryable": False}` — placed alongside existing `CopilotAuthError`/`CopilotUnavailableError` handlers, before the generic `except Exception` branch. Note: `discuss` does not need this handler — its path (`send_followup()` → `send_review()`) never checks `_startup_error`; `get_review_summary` and `list_sessions` are read-only (session store only)

**Checkpoint**: US1 complete — fresh container shows setup wizard, accepts valid PAT, rejects invalid tokens with verbose errors, redirects to status page. MCP returns clear error when no credential configured.

---

## Phase 4: User Story 2 — Rotate or Change Token (Priority: P2)

**Goal**: User with existing token can view masked token on Settings page and rotate to a new token without container restart.

**Independent Test**: Set up a token, open Settings page, change to a new valid token, verify next MCP connection uses new token.

### Tests for US2 (RED)

- [ ] T019 Extend tests in `tests/test_web_routes.py` for settings/rotation routes (RED). Cover: GET `/settings` shows masked token + source + change form when source is `stored` (US2-AS1), GET `/settings` disables form when source is `docker_secret` or `env_var` (US2-AS4), POST `/settings/rotate` with valid token → replaces old + redirects to `/settings?msg=rotated` (US2-AS2, AC-5), POST `/settings/rotate` with invalid token → preserves old token + shows error (US2-AS3), POST `/settings/rotate` rejected when source is not `stored`

### Implementation for US2 (GREEN)

- [ ] T020 Create `server/templates/settings.html` — extends base.html; shows masked token and credential source; change form (visible only when `can_rotate` is True); externally-managed explanation when Docker secret/env var; flash message display
- [ ] T021 Implement settings/rotation routes in `server/web_routes.py` (GREEN). GET `/settings` (render with source, masked_token, can_rotate flag), POST `/settings/rotate` (check source is stored → validate → store → redirect with PRG pattern; reject if externally managed)

**Checkpoint**: US2 complete — stored tokens can be rotated via Settings page. External credentials show source with disabled form.

---

## Phase 5: User Story 3 — Multiple Credential Sources (Priority: P3)

**Goal**: System correctly discovers and prioritizes credentials from Docker secret, env var, and stored credential.

**Independent Test**: Provide credentials via Docker secret while stored credential exists; verify Docker secret takes precedence.

- [ ] T022 [US3] Write integration tests for credential source priority in `tests/test_credential_resolver.py` (extend). Cover all 4 combinations from SC-004: Docker secret + env var → Docker secret wins (US3-AS1), env var only → env var used (US3-AS2), stored only → stored used (US3-AS3), none → returns None (US3-AS4). Note: cross-surface assertions (web UI redirect when no source, MCP `start_review` error response) are already covered by T011 (`tests/test_web_routes.py`) and T017 (`tests/test_mcp_handlers.py`) respectively — T022 focuses solely on resolver-level source priority.
- [ ] T023 [P] [US3] Write test for Docker secret trailing whitespace stripping in `tests/test_credential_resolver.py` — verify `.strip()` on Docker secret file contents (edge case)

**Checkpoint**: All credential source combinations verified. Priority order correct.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Security hardening, edge cases, and end-to-end verification.

- [ ] T024 [P] Security audit — grep all code for token value exposure (FR-007, SC-003). Verify: no token in log statements, no token in HTTP response bodies, no token in error messages, `mask_token()` used consistently. Check error messages from TokenValidator don't echo submitted token.
- [ ] T025 [P] Edge case tests — add tests for: Fernet key loss with existing credential file (AC-9), decryption failure (corrupted file), Copilot SDK unavailable during validation (edge case), concurrent store/load (atomic writes), stored credential becomes invalid between restarts (EC-2: verify MCP returns auth error on first use, not startup error)
- [ ] T026 Docker build and compose validation — `docker compose build --no-cache`, verify container starts, `/data/` exists with correct permissions, `127.0.0.1:8080` binding works, named volume persists across restarts
- [ ] T027 End-to-end AC verification — manually verify all 9 acceptance criteria from task.md with evidence

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on T001 (cryptography in requirements.txt) — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 completion (CredentialStore + CredentialResolver)
- **Phase 4 (US2)**: Depends on Phase 3 completion (web routes infrastructure, TokenValidator)
- **Phase 5 (US3)**: Depends on Phase 2 completion (CredentialResolver). Can run in parallel with Phase 3 and Phase 4.
- **Phase 6 (Polish)**: Depends on Phase 4 and Phase 5 completion (all features implemented)

### Within-Phase Dependencies

**Phase 2**:
```
T006 (store tests) → T007 (store impl) → T009 (resolver impl)
T008 (resolver tests) can parallel with T006/T007 (mock CredentialStore in tests)
```

**Phase 3**:
```
T010 (validator tests) → T012 (validator impl) → T015 (web routes impl)
T011 (route tests) can parallel with T010
T013, T014 (templates) can parallel with T010-T012
T015 depends on T012 (TokenValidator) + T013/T014 (templates)
T016 (main.py) depends on T015
T017 (MCP tests) depends on T009 (CredentialResolver)
T017 (MCP tests) → T018 (MCP impl)
```

**Phase 4**:
```
T019 (settings tests) → T020 (template) + T021 (routes impl)
```

### Parallel Opportunities

- **Phase 1**: T002, T003, T004, T005 can all run in parallel
- **Phase 2**: T006+T007 (store) and T008 (resolver tests) can run in parallel
- **Phase 3**: T010 (validator tests) and T011 (route tests) can run in parallel; T013 and T014 (templates) can run in parallel with test/impl work
- **Phase 5**: T022 and T023 can run in parallel; Phase 5 can run in parallel with Phase 3 and Phase 4
- **Phase 6**: T024 and T025 can run in parallel

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1: Setup (T001-T005)
2. Phase 2: Foundational — CredentialStore + CredentialResolver (T006-T009)
3. Phase 3: US1 — Setup wizard + status page + MCP integration (T010-T018)
4. **STOP and VALIDATE**: Fresh container → setup wizard → paste PAT → status page works

### Full Delivery

5. Phase 4: US2 — Token rotation via Settings page (T019-T021)
6. Phase 5: US3 — Priority order integration tests (T022-T023)
7. Phase 6: Polish — security audit, edge cases, Docker validation, AC verification (T024-T027)

---

## Notes

- TDD is MANDATORY per constitution — every module has RED tests before GREEN implementation
- [P] tasks = different files, no shared state
- All error messages must be verbose with URLs per coordinator decision (Option A)
- `mask_token()` must be used everywhere tokens are displayed (FR-007)
- Web routes use PRG pattern — POST validates + stores, then redirects (R-5)
- Flash messages via query param `?msg=` (YAGNI, no session middleware)
- Commit after each task or logical TDD cycle (RED-GREEN-REFACTOR)
