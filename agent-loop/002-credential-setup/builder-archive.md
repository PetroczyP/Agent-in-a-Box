# Builder Archive — 002-credential-setup

## Phase Summaries
<!-- Agents read this section every round -->

### [specify] Phase Summary (rounds 1-5, accepted via coordinator at round 6)

#### Key Decisions
- D-1: Credential status page at `/` owned by this spec, not dependent on spec 003's dashboard
- D-2: Status page shows source + masked token only — no connection status claims (Peter's decision)
- D-3: MCP credential freshness boundary: resolved at process startup, rotation effective on next `docker exec` connection, active sessions keep their token
- D-4: 4 distinct token validation failure modes: format error, auth error, permission error, SDK error
- D-5: Fernet key loss → treat as no stored credential, require re-entry via setup wizard

#### Findings Resolved
- H-1 (R1): MCP freshness gap → FR-010 added with explicit per-connection resolution
- H-2 (R1): Expired token under-specified → FR-005 restructured with 4 failure modes
- H-3 (R1): Dashboard dependency on spec 003 → FR-009 added, credential status page owned by this spec
- B-1 (R2): Task.md AC edits without coordinator → Peter approved all changes
- M-1 (R2): SDK-unavailable missing from US1 → AS6 added
- M-2 (R2): FR-009 "connection status" contradicts no-revalidation → removed, Peter chose source+token only
- H-1 (R3): US1 narrative still said "confirming connection" → updated to match FR-009
- L-1 (R3): Stale requirements checklist → updated FR-005, SC-002, added FR-009/FR-010
- L-1 (R4): builder.md archival rule violation → builder-archive.md created, rounds archived

#### Artifacts Produced
- `specs/002-credential-setup/spec.md` — 10 FRs, 3 user stories, 5 edge cases, 5 success criteria
- `specs/002-credential-setup/checklists/requirements.md` — quality checklist
- `agent-loop/002-credential-setup/task.md` — 9 acceptance criteria

#### Deferred / Out of Scope
- Copilot SDK error type distinction (auth vs permission) — flagged for design-phase spike
- Dashboard UI (spec 003)
- External KMS / Vault integration

### [design] Phase Summary (rounds 1-8, accepted at round 8)

#### Key Decisions
- D-1: Two-step validation: GET /user (stdlib urllib) → list_models() for 4 distinct error types (format, auth, permission, sdk)
- D-2: `_probe_github_auth()` returns `bool | None` — diagnostic probe, not gate. Only 401 maps to auth; other non-2xx is inconclusive
- D-3: Confidence model: 401→auth(high), 2xx+Copilot fail→permission(high), inconclusive→auth fallback(low)
- D-4: Permission error broadened from "missing copilot_requests" to "cannot access Copilot" (coordinator Option A, round 5)
- D-5: All 4 error types carry verbose multi-line messages with specific URLs and remediation steps
- D-6: No new HTTP dependencies — `urllib.request` (stdlib) for GET /user, `asyncio.to_thread` for async wrapper
- D-7: Flash messages via query params, PRG pattern for forms (R-5 YAGNI)
- D-8: 4 new modules: credential_store, credential_resolver, token_validator, web_routes (flat layout in server/)
- D-9: Temporary client pattern for validation — TokenValidator creates/stops CopilotReviewClient per validate()
- D-10: MCP no-credential error via existing `_startup_error` mechanism on CopilotReviewClient

#### Findings Resolved
- B-1 (R1): Design needed 4 distinct error types → restructured with two-step validation approach
- H-1 (R1): MCP no-credential error contract → defined via existing _startup_error pattern in copilot_client.py
- B-1 (R2, AP-002): Token classification redesigned — two-step validation with confidence model
- M-1 (R3, AP-002): validate_copilot_access type signature → corrected to accept `bool | None`
- B-1 (R3, AP-002): Confidence model tightened — only 401 = auth, GET /user 403 = inconclusive
- L-1 (R3): Builder archival non-compliant → design round 1 archived
- B-1 (R4): Escalated — SDK cannot distinguish copilot_requests from other Copilot access failures
- B-1 (R5): Coordinator Option A applied — all error messages verbose with URLs across all artifacts
- B-1 (R6, AP-002): Format and SDK paths missing verbose messages → propagated to all error paths, wording aligned
- L-1 (R6): Archived design rounds 2-3
- B-1 (R7, AP-002): SDK error path missing URL → added docs.github.com/en/copilot
- L-1 (R7): Builder archival regression (4 active rounds) → round 4 archived in R8

#### Artifacts Produced
- `specs/002-credential-setup/research.md` — 5 research decisions (R-1 through R-5)
- `specs/002-credential-setup/data-model.md` — StoredCredential, CredentialSource, ResolvedCredential, TokenValidationError, NoCredentialError
- `specs/002-credential-setup/contracts/credential-store.md` — Fernet encrypt/decrypt, file I/O, atomic writes
- `specs/002-credential-setup/contracts/credential-resolver.md` — Docker secret > env var > stored resolution
- `specs/002-credential-setup/contracts/token-validator.md` — format → GitHub auth probe → Copilot access, verbose error messages
- `specs/002-credential-setup/contracts/web-routes.md` — GET /, GET /setup, POST /setup, GET /settings, POST /settings/rotate
- `specs/002-credential-setup/plan.md` — technical context, constitution check, project structure, integration points

#### Deferred / Out of Scope
- None

---

## Raw Archived Rounds
<!-- Agents read this section only when tracing specific findings or decisions -->

### [specify] Round 1 — builder

#### Summary

- Reviewed existing draft spec against web research on Fernet encryption, Docker secrets, and GitHub PAT formats
- Tightened all 8 functional requirements with specific, testable criteria
- Answered all 3 open edge case questions with concrete behaviors
- Added 2 new edge cases (SDK unavailable during validation, Docker secret trailing whitespace)
- Added new acceptance scenarios (US1-AS4: Copilot permission failure, US1-AS5: env var bypass, US2-AS4: externally managed credential display, US3-AS4: no credential available)
- Added SC-005 for invalid token error message quality
- Added Fernet Key as a third key entity
- Created requirements quality checklist

#### Speckit Artifacts

- `specs/002-credential-setup/spec.md` — updated (was 91 lines, now ~115 lines)
- `specs/002-credential-setup/checklists/requirements.md` — created
- `agent-loop/002-credential-setup/task.md` — created
- `agent-loop/002-credential-setup/status.json` — created

#### Design / Implementation Notes

Key refinements to the draft spec:

1. **FR-001 expanded**: Added Fernet key lifecycle — auto-generated on first use, persisted in volume, key loss invalidates stored credentials. This was implicit but needed to be explicit for testability.

2. **FR-003 tightened**: Enumerated all rejected prefixes (`ghp_`, `gho_`, `ghs_`, `ghu_`) instead of just "classic PATs." Research confirmed these are the standard GitHub token prefixes. Error messages must identify the specific rejected type.

3. **FR-005 strengthened**: Added the case where the Copilot SDK itself is unavailable (not just auth failure). The token must not be stored if validation cannot complete.

4. **FR-006 expanded**: Specified masking format (`github_pat_...XXXX`), and added the behavior when credential is externally managed (Docker secret/env var) — rotation form is disabled with explanation.

5. **Edge cases answered**:
   - Key deleted → treat as no credential, fallback or setup wizard
   - Invalid stored credential → detected on first MCP use, not at startup
   - Shared volume → unsupported, atomic writes for corruption mitigation
   - SDK unavailable → format validation passes but Copilot validation fails with specific error
   - Docker secret whitespace → strip before use

6. **Architecture insight**: MCP and web are separate processes (`docker exec` vs uvicorn). This means hot-reload is a non-issue — each MCP invocation reads fresh credentials. This simplifies the design significantly vs cross-process coordination.

#### Verification

- **Checked**: [Fernet docs at cryptography.io](https://cryptography.io/en/latest/fernet/) — confirmed Fernet.generate_key() produces 44-char URL-safe base64 key, AES-128-CBC + HMAC-SHA256
- **Checked**: [Docker Compose secrets docs](https://docs.docker.com/compose/how-tos/use-secrets/) — confirmed non-Swarm secrets are file mounts at `/run/secrets/<name>`, no Docker-level encryption
- **Checked**: [GitHub token prefixes gist](https://gist.github.com/magnetikonline/073afe7909ffdd6f10ef06a00bc3bc88) — confirmed `github_pat_` for fine-grained, `ghp_` for classic, `gho_`/`ghs_`/`ghu_` for app tokens
- **Checked**: [GitHub blog on fine-grained PATs](https://github.blog/security/application-security/introducing-fine-grained-personal-access-tokens-for-github/) — confirmed 93-char length, fine-grained permissions model
- **Corrections**: None — research validated the existing spec's technical claims. Additions were refinements, not corrections.

#### Remaining Risks

- Copilot SDK `list_models()` is Technical Preview — API may change. Mitigation: assumption documented, fallback path to be designed in design phase.
- Docker Compose secrets without Swarm have no Docker-level encryption. Mitigation: Fernet layer provides at-rest encryption independently.
- FR-001 names Fernet specifically — this is a constitution constraint, not a spec leak. If the judge flags this, the response is that the constitution mandates "Fernet encryption in Docker named volume."

### [specify] Round 2 — builder

#### Summary

- Addressed all 3 judge findings (H-1, H-2, H-3) from round 1
- Added FR-009 (credential status page) and FR-010 (MCP freshness boundary)
- Separated token validation errors into 4 distinct failure modes in FR-005
- Replaced all "dashboard" references with "credential status page"
- Updated task.md ACs to match spec changes
- Cross-document consistency verified (AP-002, AP-005 check)

#### Changes Since Last Round

- `specs/002-credential-setup/spec.md`:
  - All "dashboard" references → "credential status page" (H-3)
  - US1-AS3 split into AS3 (format error), AS4 (auth error), AS5 (permission error) — distinct failure modes (H-2)
  - US1-AS5 (old) renumbered to AS6, expanded to cover both env var and Docker secret
  - FR-005 restructured with 4 explicit failure modes: format, auth, permission, SDK (H-2)
  - FR-009 added: credential status page at `/`, owned by this spec, post-setup destination (H-3)
  - FR-010 added: MCP credential freshness boundary — resolved at process startup, rotation takes effect on next connection, long-lived sessions keep their token (H-1)
  - SC-002 updated: clarified "next MCP connection" and "active sessions continue with original token" (H-1)
- `agent-loop/002-credential-setup/task.md`:
  - AC-2: "redirects to dashboard" → "redirects to credential status page"
  - AC-3: expanded to list all 4 error types
  - AC-4: added Docker secret alongside env var
  - AC-5: clarified "next MCP connection uses new token"

#### Responses to Judge Findings

- **H-1** (MCP credential freshness): Addressed by adding FR-010, which makes the freshness boundary explicit. Credential resolution occurs at MCP process startup. Each `docker exec` starts a fresh process. Long-lived sessions bind to their startup token — this is documented as expected behavior, analogous to env var binding at process start. SC-002 updated to match.

- **H-2** (Expired token error path under-specified): Addressed by restructuring FR-005 into 4 distinct failure modes (format, auth, permission, SDK). US1 acceptance scenarios now have separate scenarios for each: AS3 (format error — wrong prefix/empty), AS4 (auth error — expired/revoked), AS5 (permission error — missing copilot_requests). The previous FR-005 wording that hardcoded "works for GitHub but not for Copilot" for all failures is replaced with per-mode messages.

- **H-3** (Post-setup destination depends on spec 003): Addressed by adding FR-009, which defines a credential status page at `/` owned by this spec. All "dashboard" references replaced with "credential status page." FR-009 explicitly states this spec MUST NOT depend on spec 003 for the post-setup experience. Spec 003 may later expand or replace this page.

#### Verification

- **Checked**: Grep for "dashboard" in spec.md — 0 matches. All references replaced.
- **Checked**: Cross-document consistency (AP-002): task.md ACs match spec acceptance scenarios. FR-010's freshness boundary matches SC-002's wording. FR-005's error taxonomy matches US1 acceptance scenarios AS3-AS5.
- **Checked**: Scope creep (AP-003): FR-009 defines a minimal credential status page, not a full dashboard. It explicitly states spec 003 may expand it. The page shows only credential-owned information (source, masked token, connection status).
- **Checked**: Incremental fix consistency (AP-005): Re-read entire spec after changes. No new contradictions introduced. US2 acceptance scenarios still consistent (rotation path uses same error taxonomy from FR-005).
- **Corrections**: None needed after consistency check.

#### Remaining Risks

- Copilot SDK `list_models()` is Technical Preview — API may change. Mitigation: assumption documented, fallback path to be designed in design phase.
- Distinguishing "auth error" (expired/revoked) from "permission error" (missing copilot_requests) depends on the Copilot SDK surfacing distinct exception types. If the SDK returns a generic error for both, the design phase must define a fallback classification strategy. Flagged for design-phase spike.

### [specify] Round 3 — builder

(Escalation resolved: Peter approved task.md AC changes and chose "source + masked token only" for status page. Added SDK-unavailable AS6 to US1. Tightened FR-009 to prohibit connection status claims.)

### [specify] Round 4 — builder

(Fixed stale US1 narrative contradicting FR-009. Updated requirements checklist for FR-005/SC-002/FR-009/FR-010.)

### [specify] Round 5 — builder

(Context management: created builder-archive.md, archived rounds 1-2. No spec changes.)

## [design] Archived Rounds

### [design] Round 1 — builder

#### Summary

- Completed Phase 0 (Research) and Phase 1 (Design & Contracts)
- Created research.md with 5 research decisions including Copilot SDK error classification spike (R-4)
- Created data-model.md with 4 entities: StoredCredential, CredentialSource, ResolvedCredential, TokenValidationError
- Created 4 contract files: credential-store, credential-resolver, token-validator, web-routes
- Created plan.md with technical context, constitution check, project structure, and integration points
- R-4 spike resolved: SDK cannot distinguish auth vs permission errors — combined into single "auth" error_type

#### Speckit Artifacts

- `specs/002-credential-setup/research.md` — 5 research decisions (R-1 through R-5)
- `specs/002-credential-setup/data-model.md` — entities, file layout, relationships
- `specs/002-credential-setup/plan.md` — technical context, constitution check, project structure
- `specs/002-credential-setup/contracts/credential-store.md` — Fernet encrypt/decrypt interface
- `specs/002-credential-setup/contracts/credential-resolver.md` — multi-source resolution interface
- `specs/002-credential-setup/contracts/token-validator.md` — format + Copilot validation interface
- `specs/002-credential-setup/contracts/web-routes.md` — FastAPI routes for setup/settings/status

#### Design / Implementation Notes

1. SDK error classification uses string matching, no structured error codes
2. 4 new modules: credential_store, credential_resolver, token_validator, web_routes
3. Temporary client pattern for validation
4. Flash messages via query params (YAGNI)
5. Integration: mcp_server.py uses CredentialResolver, main.py gains templates/routes, copilot_client.py unchanged
6. Docker: named volume, localhost binding, /data/ directory

#### Verification

- Confirmed copilot_client.py error classification, mcp_server.py token reading, main.py minimal state, docker-compose.yml bindings, Dockerfile structure, constitution compliance
- Corrections: None

#### Remaining Risks

- Copilot SDK Technical Preview, cryptography OpenSSL requirement

### [design] Round 2 — builder

#### Summary

- Addressed B-1 (AP-002): Redesigned token validation to produce 4 distinct error types matching FR-005
- Addressed H-1: Designed explicit MCP no-credential error contract
- Updated 4 design artifacts: research.md, data-model.md, token-validator.md, plan.md
- Cross-document consistency verified across all 7 design artifacts

#### Speckit Artifacts

- `specs/002-credential-setup/research.md` — R-4 rewritten: two-step validation approach (GitHub API + Copilot SDK)
- `specs/002-credential-setup/data-model.md` — TokenValidationError now has 4 error_type values; added NoCredentialError entity
- `specs/002-credential-setup/contracts/token-validator.md` — rewritten: 3-step validate() sequence (format → github_auth → copilot_access)
- `specs/002-credential-setup/plan.md` — MCP integration section expanded with no-credential error contract

#### Design / Implementation Notes

1. Two-step validation: GET /user (stdlib urllib) → list_models(). 4 distinct error paths.
2. No new dependencies. MCP no-credential contract via existing _startup_error pattern.
3. copilot_client.py remains unchanged.

#### Verification

- Confirmed GET /user behavior, Copilot 403 multi-mode, stdlib urllib, cross-doc consistency
- Corrections: None

#### Remaining Risks

- Copilot SDK Technical Preview, GitHub API rate limiting, cryptography OpenSSL

### [design] Round 3 — builder

#### Summary

- Addressed B-1 (AP-002): Tightened classification with confidence model
- Only HTTP 401 → "auth"; confirmed-auth + Copilot fail → "permission"; inconclusive fallback
- Permission message broadened to cover copilot_requests, subscription, and policy
- Renamed validate_github_auth() → _probe_github_auth() (diagnostic, not gate)

#### Speckit Artifacts

- `specs/002-credential-setup/research.md` — R-4 tightened: confidence model table
- `specs/002-credential-setup/data-model.md` — error_type descriptions tightened
- `specs/002-credential-setup/contracts/token-validator.md` — rewritten with bool | None return

#### Design / Implementation Notes

1. Confidence model: 401 = auth (high), 2xx + Copilot fail = permission (high), inconclusive = auth fallback (low)
2. Probe, not gate: _probe_github_auth() returns bool | None, doesn't block on non-401
3. GET /user 403 treated as inconclusive, not auth failure

#### Verification

- Confirmed GitHub API 401/403 semantics, cross-document confidence model consistency
- Corrections: None

#### Remaining Risks

- Copilot SDK Technical Preview, GitHub API rate limiting, cryptography OpenSSL

### [design] Round 4 — builder

#### Summary

- Fixed M-1: validate_copilot_access() type signature corrected to bool | None
- Fixed L-1: Archived design round 1 to builder-archive.md
- Escalated B-1 to coordinator: SDK cannot distinguish copilot_requests from other Copilot access failures. Presented 3 options; recommended Option A (broaden FR-005).

#### Design / Implementation Notes

1. Coordinator decided Option A — broaden FR-005 permission error from "missing copilot_requests" to "cannot access Copilot"
2. Type signature alignment: _probe_github_auth() → bool | None, validate_copilot_access() accepts bool | None

#### Verification

- Confirmed type signature consistency, builder archival compliance, AP-007 correct escalation pattern
- Corrections: None

#### Remaining Risks

- Pending coordinator decision on FR-005 scope (resolved in round 5 via Option A)

### [design] Round 5 — builder

(Coordinator resolved escalation: Option A — broaden FR-005 permission error + verbose messages with URLs. Applied across all design artifacts: spec.md, task.md, token-validator.md, research.md, data-model.md, checklists/requirements.md.)

### [design] Round 6 — builder

(Propagated verbose message requirement to format and SDK error paths. Aligned wording: "URLs and remediation steps" consistently. Archived design rounds 2-3.)

### [design] Round 7 — builder

(Added docs.github.com/en/copilot URL to SDK error messages. All 4 error types now carry at least one troubleshooting URL.)

### [design] Round 8 — builder

(Archived design round 4 from builder.md. Context management fix only — no artifact changes.)

### [plan] Round 1 — builder

Generated `specs/002-credential-setup/tasks.md` with 26 tasks across 6 phases (Setup, Foundational, US1 MVP, US2, US3, Polish). TDD RED-GREEN pairs for all modules. 100% FR/AC/edge-case coverage. Phase-compacted builder.md (design rounds archived).

### [plan] Round 2 — builder

Addressed R1 findings: M-1 (Phase 5 dependency contradiction — fixed to depend on Phase 3, not Phase 2), M-2 (missing RED task for MCP credential boundary — inserted T017 for MCP integration tests, renumbered T017-T026 → T018-T027, 27 tasks total). AC-5 gap closed (T017 tests rotation pickup on next MCP connection).

### [plan] Round 3 — builder

Addressed M-1 (AP-002): Unified error contract across `plan.md`, `data-model.md`, and `tasks.md` — all now use `NoCredentialError(CopilotError)` instead of mixed `CopilotUnavailableError`/standalone-`NoCredentialError`. T018 updated to include creating the `NoCredentialError` class in `copilot_client.py`.

### [plan] Round 4 — builder

Addressed M-1 (AP-002): Updated `plan.md` project structure and integration note — `copilot_client.py` now marked as MODIFIED (was UNCHANGED), integration note describes the minimal modification (add `NoCredentialError` class). Archived plan rounds 1-2.

### [plan] Round 5 — builder

Addressed M-1 (AP-002): Defined MCP error-mapping contract for `NoCredentialError` → `{"error": "no_credential", ...}`. Added handler contract to plan.md, RED coverage in T017, GREEN implementation in T018. Initially scoped to all 4 MCP tools (later narrowed in round 6).

### [plan] Round 6 — builder

Addressed M-1 (AP-002): Fixed T022 — changed "Verify MCP returns NoCredentialError" to "Verify MCP `start_review` returns `{"error": "no_credential", ...}` response payload". Addressed M-2 (AP-002): Narrowed handler requirement from "all 4 MCP tools" to "`start_review` and `discuss`" only — read-only tools only access session store. Updated plan.md, tasks.md, data-model.md.

### [plan] Round 7 — builder

Addressed M-1 (AP-002): Narrowed `NoCredentialError` handler from `start_review` + `discuss` to `start_review` only. `discuss` never checks `_startup_error` — its path is `send_followup()` → `send_review()` on existing sessions. Updated plan.md, tasks.md (T017/T018), data-model.md.

### [plan] Round 8 — builder

Addressed M-1 (AP-002): Narrowed T022 to resolver-only source-priority assertions. Removed web UI redirect and MCP error assertions (already owned by T011/T017). Updated Phase 5 dependency from Phase 3 → Phase 2. Updated parallel opportunities to include Phase 3.

### [plan] Round 9 — builder

Addressed M-1 (AP-005): Fixed Phase 6 dependency to include Phase 5. Phase 6 previously said "Depends on Phase 4 completion" but Phase 5 runs in parallel with Phase 3/4, so T027 could start before US3 source-priority work is complete. Fixed to "Depends on Phase 4 and Phase 5 completion."

### [plan] Round 10 — builder

Addressed M-1: Expanded T010 RED coverage to require verbose message content and URL assertions for all 4 error types (format, auth, permission, sdk), not just format. Added closing sentence binding all 4 types to accepted templates in contracts/token-validator.md (AC-3).

### [plan] Phase Summary (rounds 1-10, accepted)

#### Key Decisions
- D-1: 27 tasks across 6 phases (Setup, Foundational, US1 MVP, US2, US3, Polish)
- D-2: TDD RED-GREEN pairs for all modules — no implementation without failing test first
- D-3: Phase 5 can run in parallel with Phase 3 and Phase 4 (depends only on Phase 2)
- D-4: Phase 6 depends on both Phase 4 and Phase 5 completion
- D-5: NoCredentialError handler required only in start_review MCP tool (not discuss or read-only tools)
- D-6: T022 narrowed to resolver-only source-priority assertions (web/MCP coverage already in T011/T017)
- D-7: All 4 error types (format, auth, permission, sdk) must assert verbose message content and URLs in RED tests

#### Findings Resolved
- M-1 (R1): Phase 5 dependency → fixed to Phase 2 (not Phase 3)
- M-2 (R1): Missing MCP credential boundary tests → T017 inserted
- M-1 (R3, AP-002): Unified NoCredentialError(CopilotError) across plan.md, data-model.md, tasks.md
- M-1 (R4, AP-002): copilot_client.py marked as MODIFIED in plan.md
- M-1 (R5, AP-002): MCP error-mapping contract for NoCredentialError defined
- M-1 (R6, AP-002): T022 fixed to assert response payload, handler narrowed to start_review+discuss
- M-1 (R7, AP-002): Handler narrowed to start_review only (discuss never checks _startup_error)
- M-1 (R8, AP-002): T022 narrowed to resolver-only assertions
- M-1 (R9, AP-005): Phase 6 dependency fixed to include Phase 5
- M-1 (R10): T010 RED coverage expanded for all 4 error types' verbose messages

#### Artifacts Produced
- `specs/002-credential-setup/tasks.md` — 27 tasks, 6 phases, TDD RED-GREEN pairs

#### Deferred / Out of Scope
- None

### [build] Phase Summary (rounds 1-2, accepted at round 2)

#### Key Decisions
- D-1: Implemented all 27 tasks (T001-T027) across 6 phases with TDD
- D-2: Exception catch in credential_store.py narrowed from `(InvalidToken, Exception)` to `(InvalidToken, ValueError)` per contract
- D-3: mask_token() derives prefix from actual token string, not hardcoded `github_pat_`
- D-4: Security audit fixed `ResolvedCredential.__repr__` to mask token value

#### Findings Resolved
- H-1 (R1): credential_store.py caught broad Exception in load(), masking I/O errors → narrowed to (InvalidToken, ValueError)
- M-1 (R1): mask_token() hardcoded `github_pat_` prefix → now derives from actual token

#### Artifacts Produced
- 13 new files (4 server modules, 4 templates, 1 CSS, 5 test files)
- 6 modified files (requirements.txt, pyproject.toml, Dockerfile, docker-compose.yml, main.py, copilot_client.py, mcp_server.py)
- 482 tests total (328 new + 154 existing), all passing

#### Deferred / Out of Scope
- Docker build/run validation (requires Docker daemon)
- Copilot SDK runtime validation (requires running inside Docker with SDK installed)

### [build] Round 1 — builder

(Implemented all 27 tasks T001-T027 across 6 phases. 476 tests passing. Security audit found and fixed ResolvedCredential.__repr__ token exposure. All 9 ACs verified with test evidence.)

### [build] Round 2 — builder

(Fixed H-1: narrowed exception catch to (InvalidToken, ValueError). Fixed M-1: mask_token() derives prefix from actual token. Added 5 new tests. 481 tests passing.)

### [test] Phase Summary (rounds 1-2, accepted at round 2)

#### Key Decisions
- D-1: Added 12 direct `_initialize_copilot()` tests to close MCP startup coverage gap (mcp_server.py:90-111)
- D-2: 1 additional edge case test for credential_store.py (update_last_validated noop)

#### Findings Resolved
- M-1 (R1, AP-001): AC-5 only verified at web route level, not MCP startup → added TestInitializeCopilotNoCredential (5), TestInitializeCopilotWithToken (5), TestInitializeCopilotRotation (2)

#### Test Results
- 494 tests, 0 failures, 95% overall coverage
- mcp_server.py: 77% → 89% (lines 90-111 now covered)
- All spec-002 modules: credential_store 100%, credential_resolver 100%, web_routes 100%, main 100%, token_validator 88%

#### Deferred / Out of Scope
- Docker build/run validation (requires Docker daemon)
- Copilot SDK runtime validation (requires running inside Docker with SDK installed)

### [test] Round 1 — builder

(482 tests passing, 94% coverage. All 9 ACs verified with test evidence. 1 new edge case test. Judge found M-1: AC-5 missing MCP startup-level verification.)

### [test] Round 2 — builder

(Added 12 _initialize_copilot() tests in 3 classes. 494 tests, 95% coverage. mcp_server.py 77% → 89%. M-1 resolved.)
