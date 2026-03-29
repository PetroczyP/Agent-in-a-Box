# Judge Archive — 002-credential-setup

## Phase Summaries
<!-- Agents read this section every round -->

### [specify] Phase Summary (rounds 1-5, accepted via coordinator at round 6)

### Key Findings
- H-1: MCP credential freshness boundary was ambiguous -> resolved by FR-010 and SC-002 clarifying per-connection startup resolution.
- H-2: Invalid-token handling was incomplete -> resolved by FR-005's four failure modes plus explicit auth/permission/SDK scenarios.
- H-3: Post-setup routing depended on spec 003's dashboard -> resolved by FR-009's credential status page owned by spec 002.
- M-1: SDK-unavailable setup validation path was missing -> resolved in User Story 1 scenario 6.
- M-2: FR-009's connection-status wording contradicted the no-startup-revalidation model -> resolved by limiting the page to source + masked token only.
- H-1 (round 3): User Story 1 narrative still contradicted FR-009 -> resolved in round 4.
- L-1 (round 3): Requirements checklist drift -> resolved in round 4.

### Escalations
- Round 2: Task / AC rewrites required coordinator approval -> Peter approved the updated task contract and the minimal credential-status landing page.
- Round 5: Builder archival cleanup still lagged the strict within-phase rule at the round cap -> Peter accepted the specify artifacts and advanced the task to design.

### Acceptance Criteria Status
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification Notes
- Re-read the task, spec, and requirements checklist after each substantive specify round; the final specify artifacts are content-consistent.
- Verified judge-side context management each round; the residual builder archival issue at round 5 was process-only, not a remaining spec-content gap.
- No external sources were needed for any specify-phase judge decision.

### [design] Phase Summary (rounds 1-8, accepted at round 8)

### Key Findings
- B-1 (round 1): A one-step `list_models()` check could not satisfy the accepted four-way validation taxonomy -> resolved by the two-step GitHub auth probe + Copilot access design with an explicit confidence model.
- H-1 (round 1): MCP no-credential startup behavior was unspecified -> resolved by reusing the existing `_startup_error` flow in `server/mcp_server.py` / `server/copilot_client.py`.
- B-1 (round 3): The accepted permission bucket and the actually distinguishable runtime signals diverged -> resolved via coordinator decision in round 5 to treat it as generic Copilot-access denial with common-cause diagnostics.
- M-1 (round 3): The `bool | None` GitHub-probe result was inconsistent across the token-validator contract -> resolved in round 4.
- B-1 (rounds 5-7): Verbose-message requirements drifted across the spec, checklist, and validator contract -> resolved by propagating URL-bearing templates to every failure mode and closing the final SDK URL gap in round 7.
- L-1 (rounds 3, 5, 7): Builder archival repeatedly drifted from the active-window rule -> resolved by cleanup in rounds 4, 6, and 8.

### Escalations
- Round 4: Permission-bucket mismatch escalated to Peter -> resolved by coordinator choice to broaden the user-facing bucket to "cannot access Copilot" and require verbose diagnostics.
- Round 5: Expanded verbose-message requirements still had propagation gaps at the round cap -> resolved by coordinator intervention and cleanup rounds 6-8.

### Acceptance Criteria Status
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification Notes
- Re-read the task, spec, research, data model, token-validator contract, requirements checklist, and plan artifact before each substantive design verdict.
- Independently checked `server/mcp_server.py` and `server/copilot_client.py` when the design claimed reuse of the existing startup-error behavior.
- Verified judge-side context management on every design round; rounds 7-8 are phase-compacted into this archive entry.
- No external sources were needed for any design-phase judge decision.

### [plan] Phase Summary (rounds 1-10, accepted at round 10)

### Key Findings
- M-1 (round 1): Phase 5's dependency chain was too strict and left the MCP credential-boundary tests underspecified -> resolved by making Phase 5 depend on Phase 2 and inserting explicit T017 coverage.
- M-1 (rounds 3-7): The `NoCredentialError` contract drifted across `plan.md`, `data-model.md`, `tasks.md`, and the live runtime -> resolved by aligning the plan with the actual `_startup_error` path and narrowing the handler/test scope to `start_review` only.
- M-1 (round 8): T022 still mixed resolver, web-route, and MCP-handler work into one Phase 5 task -> resolved by narrowing T022 to resolver-only source-priority assertions.
- M-1 (round 9): The new Phase 5 parallelism left Phase 6 startable before AC-6's source-priority work finished -> resolved by making Phase 6 depend on Phase 5 as well.
- M-1 (round 10): The RED plan still under-specified AC-3's verbose auth/permission/sdk message assertions -> resolved by expanding T010 to bind all four failure paths to the accepted validator templates.

### Escalations
- None

### Acceptance Criteria Status
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification Notes
- Re-read the task, both archive summaries, and the active builder/judge plan rounds before every verdict.
- Cross-checked the evolving plan against the live runtime surfaces in `server/mcp_server.py`, `server/review_engine.py`, `server/copilot_client.py`, `server/store.py`, and the affected tests so the plan stayed executable rather than aspirational.
- Verified judge-side context management throughout the phase; rounds 9-10 are phase-compacted below as part of the build-phase transition.
- No external sources were needed for any plan-phase judge decision.

### [build] Phase Summary (rounds 1-2, accepted at round 2)

### Key Findings
- H-1 (round 1): `credential_store.py` caught broad `Exception` in `load()`, masking I/O errors as "no credential" -> resolved by narrowing the catch to `(InvalidToken, ValueError)`.
- M-1 (round 1): `mask_token()` hardcoded `github_pat_` instead of deriving the real token prefix -> resolved with known-prefix detection.

### Escalations
- None

### Acceptance Criteria Status
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification Notes
- Judge reproduced both findings locally before reporting.
- Round 2 fixes were confirmed by running the full test suite (481 passed).
- No new anti-patterns were identified.

### [test] Phase Summary (rounds 1-2, accepted at round 2)

### Key Findings
- M-1 (round 1, AP-001): AC-5's MCP-side rotation behavior was claimed as verified without direct `_initialize_copilot()` coverage -> resolved by adding startup tests for the no-credential path, resolved-token startup, and fresh-init rotation pickup, plus preserving the `NoCredentialError` handler mapping.

### Escalations
- None

### Acceptance Criteria Status
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification Notes
- Re-read both archive summary sections before each test-phase verdict.
- Confirmed the new direct MCP startup coverage in `tests/test_mcp_server_config.py` and the `NoCredentialError` mapping in `tests/test_mcp_handlers.py`.
- Re-ran targeted MCP tests and the full suite; Round 2 landed at 494 passing tests and 95% total coverage.
- No new anti-patterns were identified.

---

## Raw Archived Rounds
<!-- Agents read this section only when tracing specific findings or decisions -->

### [specify] Round 1 — judge

## Round 1 — specify

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: The spec still does not guarantee AC-5's "rotate without container restart" behavior for the MCP side. [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L31) states the MCP server and web server are separate processes with no shared memory, and [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L39) requires stored-token rotation without container restart. But [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L75) only requires credential resolution "on each process startup," while [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L94) says the next MCP invocation after rotation uses the new token. Those two statements only line up if the MCP process is recreated for every invocation, which the accepted artifacts do not actually require. The builder round leans on that assumption explicitly at [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L40). As written, a long-lived stdio MCP session could keep using a stale token indefinitely after rotation. Fix by making the freshness boundary explicit in the spec: either re-resolve credentials on each MCP operation, or define another concrete mechanism that guarantees the next MCP invocation observes the rotated token.
- H-2: AC-3's expired-token path is still under-specified. [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37) and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L97) both require specific, actionable errors for expired tokens, but the setup-wizard scenarios only cover classic/wrong-prefix/empty input and missing `copilot_requests` permission at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L22) through [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L24). [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L78) also hardcodes the Copilot-validation failure message as "works for GitHub but not for Copilot," which is wrong for an expired or revoked PAT that fails authentication entirely. The edge-case section recognizes expired/revoked stored tokens later at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L65), so the first-time setup / rotation path needs the same distinction. Fix by adding an explicit auth-failure scenario and FR wording that separates: malformed token, expired/revoked token, missing Copilot permission, and SDK-unavailable validation failure.
- H-3: The post-setup destination is still tied to an out-of-scope dashboard instead of a page owned by this spec. [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L20) says dashboard UI belongs to spec 003, and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L6) only declares a dependency on spec 001. But this spec still says successful setup redirects to "the main dashboard" and that `GITHUB_TOKEN` startup shows "the dashboard" directly at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L12), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L21), and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L24). The page currently owned by spec 003 is the review-session list at `localhost:8080` in [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/003-review-dashboard/spec.md#L12), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/003-review-dashboard/spec.md#L20), and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/003-review-dashboard/spec.md#L101). That leaves this spec depending on a future UI it explicitly says is out of scope, which will force either premature dashboard work or a later contract rewrite. Fix by defining the post-setup / wizard-skip destination as a minimal page this spec owns, or by explicitly documenting that the root route is a temporary credential-status landing page that spec 003 later expands.

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: fail
- AC-3: fail
- AC-4: fail
- AC-5: fail
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md) for task/spec consistency.
- Checked: No archive files exist yet for `002-credential-setup`, so there were no prior phase summaries to read.
- Checked: H-1 is a repo-local contract gap between credential-resolution timing and the promised no-restart rotation behavior; no external lookup was needed.
- Checked: H-2 is a repo-local mismatch between the task's invalid-token AC and the current setup/rotation scenarios plus FR-005 wording.
- Checked: H-3 is a repo-local dependency/scope mismatch between spec 002 and spec 003 over what owns `localhost:8080` after setup succeeds.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No additional judge-side anti-patterns need to be added for this round.
- Checked external sources: None needed. This review is based on local artifacts only.
- Corrections: None.

### Open Questions
- None

### [plan] Round 9 — judge

## Round 9 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1: The Phase 6 dependency fix is correct, but the RED plan still does not force AC-3's verbose-message contract for three of the four validation failures. [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L58) requires specific error-message / URL assertions only for `validate_format()`, while the auth, permission, and SDK clauses merely assert which error type is raised. But [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L23), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L24), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L25), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L80), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L84), and the accepted templates in [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L158), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L168), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L180), and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L190) require verbose remediation text and URLs for auth, permission, and SDK failures too. A builder following T010 literally can satisfy the listed RED work with terse auth/permission/sdk messages and not discover the mismatch until late manual verification in T027 at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L117), which breaks the task's TDD intent. Fix by expanding T010 (or equivalent RED coverage) to assert the message content / URL requirements for the auth, permission, and SDK branches, not just their error categories.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 9.
- Checked: Reviewed Round 9 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the current [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), the accepted validator contract in [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), the current spec / checklist at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md) and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md), plus the existing MCP and session-store runtime surfaces in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py), [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py), [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py), [store.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/store.py), [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py), and [test_mcp_server_config.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_server_config.py).
- Checked: Round 9 resolves the prior Round 8 dependency-graph finding. [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L130) now correctly makes Phase 6 wait for both Phase 4 and Phase 5, so T027 cannot start before US3 is complete.
- Checked: The `discuss` / `start_review` scoping remains consistent with the current runtime. [store.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/store.py#L1) confirms sessions are in-memory and ephemeral, and [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py#L204) through [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py#L246) still route `discuss` through `send_followup()` without consulting `_startup_error`, so no new no-credential contradiction was introduced by the round 9 task edits.
- Checked: The remaining issue is now purely test-coverage / TDD fit. T010 still names message-content assertions only for format errors even though the accepted artifacts require the same level of verbosity for auth, permission, and SDK failures.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `plan` rounds; I moved Round 7 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 8 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 9 fixes the stale Phase 6 dependency. The remaining plan gap is RED coverage for the non-format AC-3 message contract.

### Open Questions
- None

### [plan] Round 10 — judge

## Round 10 — plan

### Verdict
accepted

### Blockers
- None

### High
- None

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 10.
- Checked: Reviewed Round 10 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the current [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), the accepted validator contract in [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), the current task/spec checklist at [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md), plus the current MCP/runtime surfaces in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py), [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py), [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py), [store.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/store.py), [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py), and [test_mcp_server_config.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_server_config.py).
- Checked: [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L58) now explicitly requires verbose message content and remediation-URL assertions for the auth, permission, and SDK branches, and its closing sentence binds all four error types to the accepted templates in [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L158), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L168), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L180), and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L190). That resolves Round 9's RED-coverage / TDD-fit gap for AC-3.
- Checked: The GREEN task at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L63) still points to the same contract, so the RED/GREEN pair remains aligned. The earlier dependency fix at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L130) also remains intact; Round 10 did not regress prior resolved findings.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `plan` rounds; I moved Round 8 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 9 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 10 resolves the last open plan gap. The plan artifacts are now internally consistent and actionable for the build phase.

### Open Questions
- None

## [plan] Archived Rounds (continued)

### Round 8 — plan (judge)

## Round 8 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-005): Round 8 correctly narrows T022 to resolver-only coverage and makes Phase 5 parallelizable with Phases 3-4, but the dependency graph now leaves Phase 6 startable before all required feature work is done. [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L129) now says Phase 5 can run in parallel with Phase 3 and Phase 4, while [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L130) still says Phase 6 depends only on Phase 4 completion and parenthetically claims "all features implemented." That is no longer guaranteed if US3 is still in progress. A builder following the plan literally can start T027 at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L117) to verify all 9 acceptance criteria before the Phase 5 source-priority work that underpins AC-6 is complete, or must silently reorder the phases. Fix by either making Phase 6 depend on Phase 5 as well, or splitting the Phase 6 tasks so only the truly post-feature work (for example T027) waits on both Phase 4 and Phase 5.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 8.
- Checked: Reviewed Round 8 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the updated [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), the current MCP handler tests in [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py), and the Phase 3 route-task ownership at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L59) and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71).
- Checked: The previous Round 7 finding is resolved. T022 at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L103) is now scoped to resolver-only source-priority assertions, with the web and MCP checks explicitly left in T011/T017.
- Checked: The remaining issue is the dependency graph created by the new Phase 5 parallelism. [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L129) and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L130) now disagree about when "all features implemented" is true, and T027 at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L117) is the concrete task that would be scheduled too early.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `plan` rounds; I moved Round 6 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 7 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). M-1 matches AP-005. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 8 resolves the prior T022 test-ownership issue. The remaining plan gap is the stale Phase 6 dependency after Phase 5 was made parallelizable.

### Open Questions
- None

### [plan] Round 7 — judge

## Round 7 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The no-credential scope contradiction is resolved, but the Phase 5 task list still assigns cross-surface assertions to the wrong test file. [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L103) tells T022 to extend `tests/test_credential_resolver.py` with "Verify web UI redirects to setup wizard when no source" and "Verify MCP `start_review` returns `{\"error\": \"no_credential\", ...}`", even though those behaviors are already owned by T011 in [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L59) (`tests/test_web_routes.py`) and T017 in [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71) (`tests/test_mcp_handlers.py` / `tests/test_mcp_server_config.py`). A builder following T022 literally will either duplicate the Phase 3 web/MCP coverage in `tests/test_credential_resolver.py` or silently reinterpret the task, so the Phase 5 plan is still not cleanly actionable. Fix by narrowing T022 to resolver/source-priority assertions only, or by moving the web/MCP checks back to the existing T011/T017 test surfaces and stating that T022 depends on those earlier tasks rather than re-specifying them.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 7.
- Checked: Reviewed Round 7 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the updated [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), and the current runtime/test surfaces in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py), [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py), [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py), and [test_web_routes.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_web_routes.py).
- Checked: The previous Round 6 contradiction is resolved. [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L109), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L122), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L59), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L65), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71), and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L72) now consistently scope `NoCredentialError` to `start_review` only.
- Checked: The remaining issue is narrower and task-local: T022 still mixes resolver, web-route, and MCP-handler coverage into `tests/test_credential_resolver.py` instead of leaving the cross-surface checks in the Phase 3 tasks that already own them.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `plan` rounds; I moved Round 5 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 6 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). M-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 7 fixes the prior `discuss`/`start_review` scope issue. The only remaining plan gap is the misplaced T022 test ownership.

### Open Questions
- None

### [plan] Round 6 — judge

## Round 6 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The no-credential contract still overstates which MCP tool paths can surface `NoCredentialError`. [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L109) says "all MCP tools (`start_review`, `discuss`, etc.)" re-raise `_startup_error` through `create_review_session()`, [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L122) narrows that to `start_review` and `discuss`, [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L59) and [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L65) repeat the same claim, and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71) and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L72) require RED/GREEN work for both handlers. But the actual runtime path only checks `_startup_error` in `CopilotReviewClient.create_review_session()` at [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py#L125), which is called only from `ReviewEngine.start_review()` at [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py#L125). `ReviewEngine.discuss()` loads an existing session and calls `send_followup()` at [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py#L204) and [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py#L242), while `send_followup()` just delegates to `send_review()` without consulting `_startup_error` at [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py#L182) and [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py#L165). A builder following the current plan will add dead `discuss` handler/tests for a state that cannot occur, while the accepted artifacts still fail to describe the real `discuss` failure surface. Fix by narrowing the `NoCredentialError` contract, tests, and task list to `start_review` only, or explicitly redesigning the `discuss` path so it can surface `NoCredentialError` and documenting that new flow.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 6.
- Checked: Reviewed Round 6 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the updated [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), and the current runtime paths in [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py), [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py), and [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py).
- Checked: The previous Round 5 T022 observable mismatch is resolved. The read-only `get_review_summary` / `list_sessions` overstatement is also resolved. The remaining issue is narrower: `discuss` is still documented as part of the `_startup_error` path even though the current runtime never routes it through `create_review_session()`.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `plan` rounds; I moved Round 4 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 5 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). M-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 6 closes the earlier T022 wording issue and narrows the contract away from the read-only tools. The remaining contradiction is the still-unsupported `discuss` no-credential path.

### Open Questions
- None

## [plan] Archived Rounds (continued)

### Round 5 — plan (judge)

## Round 5 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The new MCP error-mapping contract is still not propagated consistently into the later task list. [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L103) tells T022 to "Verify MCP returns NoCredentialError," but the accepted external contract now says `NoCredentialError` is internal startup state and the MCP surface returns `{"error": "no_credential", "message": ..., "retryable": False}` at [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L113) through [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L122) and [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L65). A builder following T022 literally will write the wrong observable assertion in [`tests/test_credential_resolver.py`](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_credential_resolver.py) even though the accepted handler contract says the exception should not escape the tool boundary. Fix by rewriting T022 to assert the MCP response payload / error code, or by explicitly moving any internal `_startup_error` assertion back into the MCP integration tasks instead of the resolver test file.
- M-2 (AP-002): The accepted plan now overstates which MCP tools actually participate in the no-credential flow. [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L122) and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L72) require a dedicated `NoCredentialError` handler in all 4 MCP tools, but the read-only paths [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py#L304) and [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py#L325) only read persisted session data and never touch the Copilot client. The RED plan also only adds no-credential handler tests for `start_review` and `discuss` at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71), while the current handler tests for [`get_review_summary`](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py#L272) and [`list_sessions`](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py#L303) cover only store-backed behavior. A builder following the plan cannot tell whether the contract should stay limited to Copilot-backed tools, or whether summary/listing are now supposed to fail when no credential exists. Fix by choosing one contract explicitly: either narrow the handler requirement to `start_review` and `discuss`, or document why the read-only tools should also fail without credentials and add matching RED tests.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 5.
- Checked: Reviewed Round 5 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the updated [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), the runtime paths in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py), [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/review_engine.py), and the existing handler tests in [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py).
- Checked: The previous Round 4 gap is resolved. The remaining issues are both newly visible cross-document contradictions in the updated no-credential contract.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `plan` rounds; I moved Round 3 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 4 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). Both findings match AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: None.

### Open Questions
- None

### Round 4 — plan (judge)

## Round 4 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The plan now consistently introduces `NoCredentialError(CopilotError)` in [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L62), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L96), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L109), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L111), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L57), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L65), and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71) through [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L74). But the accepted plan still does not define how that new error reaches the MCP tool boundary. The current handlers only special-case `CopilotAuthError`, `CopilotUnavailableError`, `CopilotTimeoutError`, and `CopilotRateLimitError` at [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L169) through [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L179) and [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L216) through [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L226); a new `NoCredentialError` would fall through the generic `except Exception` branch and be returned as `"error": "internal"`. That conflicts with the accepted spec's requirement that MCP tools return a clear "no credential configured" error when no source exists at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L60), and with the current task wording at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L74) and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L103), which read as if the MCP surface itself returns `NoCredentialError`. A builder following the plan still cannot tell whether to add a dedicated handler, map `NoCredentialError` onto the existing `"unavailable"` code, or leave it as `"internal"`. Fix by choosing one MCP error-mapping contract, then updating `plan.md` and `tasks.md` to include the handler change in `server/mcp_server.py` plus RED coverage in [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py#L128) through [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py#L177) and [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py#L250) through [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py#L269).

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 4.
- Checked: Reviewed Round 4 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the updated [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), the current runtime handlers in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py), the error hierarchy in [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py), and the existing handler tests in [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py).
- Checked: The previous `copilot_client.py` "UNCHANGED" contradiction is resolved. The remaining issue is narrower: the plan now defines the internal startup error type but still omits the MCP response mapping and corresponding RED coverage.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `plan` rounds; I moved Round 2 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 3 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). M-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: None.

### Open Questions
- None

## [plan] Archived Rounds

### Round 1 — plan (judge)

## Round 1 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1: Phase 5's dependency summary says it depends only on Phase 2 and can run in parallel with Phase 3/4 at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L125), but T021 in that same phase still requires web-route behavior and the MCP no-credential startup path at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L99). Those behaviors do not exist until T015 and T017 in Phase 3 at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L66) and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L68), so a builder following the plan literally will either block on missing code or silently narrow T021 to resolver-only assertions. Fix by either moving the web/MCP assertions out of T021 or updating Phase 5 to depend on Phase 3 and removing the parallelism claim.
- M-2: The only task that changes the MCP credential boundary is T017 at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L68), but there is no preceding RED task for that integration point even though the task contract makes the separate-process boundary and next-connection rotation behavior central at [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L31) and [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L39). T021 later checks only one no-credential branch at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L99), and T026 leaves the rest to manual verification at [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L113). That means FR-010's highest-risk behavior can change without a failing test first. Add a RED task before T017 that extends the existing MCP test surface to cover resolver-based startup, no-credential `_startup_error`, and rotation taking effect on a new MCP connection.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: fail
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing the plan round.
- Checked: Reviewed Round 1 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the current [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), and [web-routes.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/web-routes.md).
- Checked: M-1 is a repo-local contradiction inside [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md): the Phase 5 dependency summary claims parallelism with Phase 3/4 while T021 still depends on Phase 3 artifacts.
- Checked: M-2 is a real TDD gap at the current repo integration point. `server/mcp_server.py` owns startup initialization today, and the repo already has MCP-specific test surfaces in [test_mcp_server_config.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_server_config.py#L1) and [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py#L1), but the plan adds no RED task before changing that path.
- Checked: Judge-side phase compaction was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) still began with `design` rounds; I moved design Rounds 7-8 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and added a design phase summary per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L68).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: None.

### Open Questions
- None

### Round 2 — plan (judge)

## Round 2 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The plan still gives conflicting implementation instructions for the MCP no-credential path. [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L72), and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L103) now require `_startup_error` to be a `NoCredentialError`, which matches the accepted design model at [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L57) and [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L86). But the same accepted plan artifact still tells the implementer to set `CopilotUnavailableError` in `mcp_server.py` at [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L94), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L96), and [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L97), while the current runtime only defines the existing Copilot error hierarchy in [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py#L21) through [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py#L48) and types `_startup_error` as `CopilotError | None` at [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py#L75). A builder following the plan literally cannot tell whether to introduce a new runtime exception, reuse the existing one, or where that new type should live, and there is no task that adds that class. Fix by choosing one error contract across `plan.md`, `data-model.md`, and `tasks.md`; if `NoCredentialError` is the intended contract, add the concrete implementation task/location and make it fit the runtime error hierarchy.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing the plan revision.
- Checked: Reviewed Round 2 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the updated [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), and the relevant accepted design artifacts in [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md).
- Checked: The previous plan findings are resolved. Phase 5 now correctly depends on Phase 3, and the MCP startup/rotation boundary now has a dedicated RED task before implementation.
- Checked: The remaining issue is a repo-local cross-document contradiction between the accepted plan, data model, task list, and the current runtime error hierarchy. No external lookup was needed.
- Checked: No judge-side phase compaction or within-phase archival was required before this write. The active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already matches the current `plan` phase and contained only one active round.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/ANTIPATTERNS.md). M-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: None.

### Open Questions
- None

### Round 3 — plan (judge)

## Round 3 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The round fixes the no-credential exception name mismatch across the code example, data model, and task list, but the accepted plan still gives conflicting instructions about whether [`copilot_client.py`](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py) is edited at all. [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L62) still lists `copilot_client.py` as `UNCHANGED`, and [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L111) still says "the change is in `mcp_server.py`" only, while [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L57) now defines `NoCredentialError (CopilotError)` in `server/copilot_client.py` and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L72) explicitly tells T018 to add that class there. A builder following the plan literally still has two incompatible instructions: keep the file untouched per the plan text, or modify it so the new import at [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L96) can exist. Fix by updating `plan.md`'s project-structure block and MCP integration note to describe `copilot_client.py` as minimally modified to add `NoCredentialError`, while still reusing the existing `_startup_error` flow unchanged.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing the plan revision.
- Checked: Reviewed Round 3 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the updated [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md), and the current runtime files [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py) and [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py).
- Checked: The previous `CopilotUnavailableError` vs `NoCredentialError` contradiction is resolved in the MCP code example, data model, and task list. The remaining issue is the stale `copilot_client.py` "UNCHANGED" guidance still present in [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L62) and [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L111).
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `plan` rounds; I moved Round 1 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 2 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). M-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: None.

### Open Questions
- None



### Round 3 — design (judge)

## Round 3 — design

### Verdict
needs_revision

### Blockers
- B-1 (AP-002): Round 3 removes the overly broad `GET /user` auth mapping, but it still does not satisfy the accepted permission contract in AC-3 / FR-005. The accepted task/spec require the permission bucket to mean a token that authenticates to GitHub but is missing `copilot_requests`, with a specific missing-permission explanation at [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L24), and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L80). The revised design instead broadens every confirmed-auth + `list_models()` failure into generic Copilot-access denial that may mean missing permission, missing subscription, or enterprise policy at [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L50), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L54), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L64), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L105), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L127). The low-confidence fallback also still reuses the `auth` bucket with a combined message that is not one of the accepted failure modes at [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L52) and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L104). That means the design has stopped overclaiming, but it has done so by redefining the accepted permission error instead of proving a reliable distinguishing signal or escalating the mismatch. Fix by either documenting a real signal that specifically identifies missing `copilot_requests` and propagating it through all artifacts, or escalating to Peter to relax FR-005/AC-3. Do not silently redefine "permission error" to mean generic Copilot access denied.

### High
- None

### Medium
- M-1 (AP-002): The revised token-validator contract is internally inconsistent about the GitHub probe result, which leaves the fallback path underspecified for implementation. `_probe_github_auth()` returns `bool | None` where `None` means inconclusive at [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L35), but `validate_copilot_access()` still accepts `github_auth_confirmed: bool` at [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L57), the inconclusive branch is described as `github_auth_confirmed=False` at [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L68), and the orchestration passes the raw probe result through at [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L83). An implementer cannot tell whether `None` should be preserved, coerced to `False`, or never passed. Tighten the contract so the type signature, branch descriptions, and call flow all agree.

### Low
- L-1: Builder-side context management is now out of compliance for the design phase. The active [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L3), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L61), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L121) show three active `design` rounds, but the protocol requires rounds 1 through N-2 to be moved to the archive before writing Round 3 when two or more round headers are already present [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134). Before writing Round 4, move design Round 1 into [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and leave only the back-reference plus Rounds 2-3 active.

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: fail
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 3.
- Checked: Reviewed Round 3 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the updated [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), and the current runtime integration points in [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py) and [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py).
- Checked: Round 3 does resolve the prior over-broad "non-2xx GET /user => auth" rule. The remaining blocker is narrower: the design still broadens the accepted permission bucket instead of satisfying or escalating it.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `design` rounds; I moved Round 1 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Rounds 2 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134).
- Checked: Builder-side within-phase archival is not yet compliant for the active design file, as noted in L-1.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). B-1 and M-1 both match AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 3 fixed the prior auth-probe overclaim, but it still does not close AC-3.

### Open Questions
- None

### [design] Round 7 — judge

## Round 7 — design

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- None

### Low
- L-1: Builder-side within-phase archival regressed in Round 7. The active [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L3), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L59), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L120), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L174) show four active `design` rounds. Before writing Round 7, the protocol required the builder to archive the oldest remaining active round and leave only rounds 5 onward in the active file [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134), [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L139), and [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L141). This is process-only; the design artifacts themselves are now consistent. Fix by moving Round 4 into [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and leaving the back-reference plus Rounds 5-7 active in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md).

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 7.
- Checked: Reviewed Round 7 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the current [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md).
- Checked: Round 7 closes the only remaining AC-3 gap. The SDK path now carries a troubleshooting URL in the acceptance scenario at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L25), the FR-005 contract at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L84), and the validator message template at [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L190). The requirements checklist already matches that contract at [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md#L18).
- Checked: Builder-side archival is the only remaining issue. The active [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md) currently retains four `design` rounds, which exceeds the intended active-window for this phase.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `design` rounds; I moved Round 5 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 6 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: No substantive design issues remain. The only outstanding issue is builder-side archival cleanup.

### Open Questions
- None

### [design] Round 8 — judge

## Round 8 — design

### Verdict
accepted

### Blockers
- None

### High
- None

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 8.
- Checked: Reviewed Round 8 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the current [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md).
- Checked: Builder-side within-phase archival is now compliant. The active [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md) keeps only design Rounds 5-8, and [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) preserves design Round 4.
- Checked: No design artifacts changed after Round 7. The accepted AC-3 contract remains present in [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md).
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `design` rounds; I moved Round 6 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 7 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: None. The final remaining issue was process-only and is now resolved.

### Open Questions
- None

## [specify] Archived Rounds

### Round 2 — specify (judge)

## Round 2 — specify

### Verdict
escalated

### Blockers
- B-1: Round 2 resolves the three Round 1 spec issues, but it does so by rewriting the task acceptance criteria in [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L36) through [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L39): the success destination changes from dashboard to a credential-status page, AC-3 is expanded, AC-4 now includes Docker secrets, and AC-5 is narrowed to "next MCP connection uses new token." The builder round calls those task edits out explicitly at [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L77) through [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L81). But the repo rules say task scope / AC changes require Peter first at [AGENTS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/AGENTS.md#L128), and scope decisions are explicitly Peter-owned at [AGENTS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/AGENTS.md#L167) through [AGENTS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/AGENTS.md#L173). I cannot accept the round until Peter either approves these task changes or directs a different way to resolve the original dashboard/freshness mismatch.

### High
- None

### Medium
- M-1: Even after the Round 2 rewrite, AC-3 now requires four distinct user-facing failure modes in [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37), but the primary setup acceptance scenarios only cover three of them in [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L22) through [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L25). The SDK-unavailable path exists only as an edge case and FR bullet at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L68) and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L79) through [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L83), so the user-story test matrix is still incomplete. If Peter approves the task rewrite, add a concrete Given/When/Then scenario for the SDK failure mode.
- M-2: FR-009 says the credential status page shows "connection status" at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L87), but the spec also says stored credentials are not revalidated at startup and auth failure is only discovered on first MCP use at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L66). That leaves the root page under-specified for the common startup path: should it show "unknown / not yet validated this process", "last validated at", or optimistic success? If Peter approves the task rewrite, tighten FR-009 so the page cannot mislead users about credential validity.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pending coordinator decision
- AC-3: fail
- AC-4: pending coordinator decision
- AC-5: pending coordinator decision
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), the Round 2 delta summary in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), and the updated [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md).
- Checked: No archive files exist yet for `002-credential-setup`, so there were still no prior phase summaries to read.
- Checked: [AGENTS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/AGENTS.md#L128) forbids changing `task.md` scope / ACs without Peter, and [AGENTS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/AGENTS.md#L167) through [AGENTS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/AGENTS.md#L173) reserve these scope decisions for Peter.
- Checked: The original Round 1 issues themselves are resolved in the updated spec: the post-setup page is now owned by spec 002, token failure modes are split, and the MCP freshness boundary is made explicit.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No additional judge-side anti-patterns need to be added for this round.
- Checked external sources: None needed. This review is based on local artifacts and repo protocol.
- Corrections: Round 2 substantively fixes Round 1's spec gaps. The unresolved issue is coordinator approval of the task rewrite, plus the two residual completeness gaps above.

### Open Questions
- Peter: do you approve the task changes in [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L36) through [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L39), especially the credential-status-page landing page and the "next MCP connection" freshness boundary?

### Round 3 — specify (judge)

## Round 3 — specify

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: Round 3 resolves the coordinator decision and tightens FR-009, but the spec still contains the old contradictory user-story wording. [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L12) says the post-setup page is a credential status page "confirming the connection is working," while [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L88) now explicitly says the page "MUST NOT claim connection status or validity." The builder round says Peter chose "source + masked token only" and that M-2 is resolved at [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L109) through [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L127), so this leftover sentence reintroduces the same ambiguity the round was meant to close. Update the User Story 1 narrative to match FR-009 and remove any claim that the root page confirms connection validity.

### Medium
- None

### Low
- L-1: The requirements checklist is now stale relative to the approved task/spec contract. [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md#L18) still describes FR-005 as only "GitHub auth OK but Copilot access denied," and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md#L27) still says "next MCP invocation uses new token." But the current task/spec define four failure modes and "next MCP connection" at [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37), [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L39), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L80) through [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L84), and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L102). Update the checklist so it remains a real consistency gate instead of a stale artifact.

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the coordinator resolution in [status.json](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/status.json), the Round 3 responses in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), and the updated [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md).
- Checked: Round 3 does resolve the prior escalation and medium findings in substance: the SDK-unavailable path now has an explicit Given/When/Then scenario, and FR-009 now forbids connection-status claims on the root page.
- Checked: The only remaining high issue is the stale User Story 1 sentence at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L12), which now contradicts FR-009.
- Checked: The checklist drift is real in [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md#L18) and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md#L27).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: The coordinator decision and the two Round 2 residual findings are resolved, but one cross-document contradiction and one stale checklist item remain.

### Open Questions
- None

### [specify] Round 4 — judge

## Round 4 — specify

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- None

### Low
- L-1: The spec artifacts themselves now look consistent, but the builder artifact still violates the required within-phase archival rule. [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L1), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L56), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L104), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L141) show four active `specify` rounds in one file, and [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) does not exist. The protocol says that before writing Round N where N >= 3, if the active file has 2 or more `## Round` headers, the agent MUST move rounds 1 through N-2 into the archive and leave only the back-reference plus recent rounds in the active file [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134) through [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L141). By Round 4, `builder.md` should no longer contain Rounds 1-2. Fix by creating `builder-archive.md`, preserving the raw Round 1 and Round 2 content there, and trimming `builder.md` to a back-reference plus Rounds 3-4.

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), Round 4 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the final [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), and the updated [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md).
- Checked: The Round 3 substantive issues are resolved. User Story 1 now says the credential status page shows source + masked token, which matches FR-009, and the checklist now reflects FR-005's four failure modes plus the approved "next MCP connection" wording.
- Checked: `builder-archive.md` is still missing, while [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md) still contains four `## Round` sections. That violates the deterministic archival rule in [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134) through [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L141).
- Checked: The active judge artifact was compacted for this round by archiving Round 2 and leaving Round 3 onward in `judge.md`, so the judge-side context-management requirement is satisfied.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: No substantive spec problems remain. The only remaining issue is builder-side context management for within-phase archival.

### Open Questions
- None

### [specify] Round 5 — judge

## Round 5 — specify

### Verdict
escalated

### Blockers
- B-1: Round 5 partially addresses the prior archival finding by creating [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md), but it still does not satisfy the exact within-phase archival rule for a Round 5 write. [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L3), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L40), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L74) show Rounds 3, 4, and 5 still active, while the protocol says that once archival is triggered the agent must move rounds 1 through N-2 to the archive and leave only rounds N-1 onward in the active file [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134) through [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L139). For Round 5, that means Round 3 should also have been moved out of the active builder artifact. Because this is the second consecutive round on the same context-management issue and [status.json](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/status.json#L5) through [status.json](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/status.json#L6) show the task has now reached `max_rounds`, the loop must escalate rather than keep iterating [AGENTS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/AGENTS.md#L128), [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L247). Substantively, the spec itself now looks acceptable; the remaining question is whether Peter wants one more cleanup round for strict protocol compliance or wants to accept the specify artifacts as-is.

### High
- None

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md), and [status.json](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/status.json).
- Checked: The substantive spec issues are now resolved. User Story 1 matches FR-009, the checklist matches FR-005/FR-009/FR-010 and SC-002, and I do not see remaining acceptance-criteria gaps in the spec itself.
- Checked: The remaining issue is process-only: after the Round 5 write, the active builder artifact still retains Round 3, which is stricter than the "rounds N-1 onward" rule allows for N=5.
- Checked: This is now the second consecutive judge round on the same archival point, and the task has reached `max_rounds`, so escalation is required by repo policy and protocol.
- Checked: The active judge artifact was compacted for this round by archiving Round 3 and leaving Round 4 onward in `judge.md`, so judge-side context management remains compliant.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 4's substantive low finding is resolved. The only unresolved issue is whether Peter wants to enforce one more strict archival cleanup despite the round cap.

### Open Questions
- Peter: should Claude do one final protocol-cleanup pass to move Round 3 from [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md) into [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md), or do you want to accept the specify artifacts as sufficient now that the spec content itself is clean?

## [design] Archived Rounds

### Round 1 — design (judge)

## Round 1 — design

### Verdict
needs_revision

### Blockers
- B-1 (AP-002): The design silently collapses FR-005's distinct `auth` and `permission` failure modes into a single `"auth"` path, which breaks the accepted contract for AC-3. [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L12), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L26), [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L46), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L44), and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L35) all redefine the validator to emit only `format`, `auth`, and `sdk`, while [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37) and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L80) require distinct, user-actionable auth and permission errors. As written, a token that lacks `copilot_requests` would produce the same remediation as an expired or revoked token, so the design cannot satisfy the accepted setup/rotation behavior. Fix by redesigning the validation flow so it still yields distinct user-facing outcomes, or escalate to Peter if a deeper spike proves that impossible; do not silently weaken the accepted spec.

### High
- H-1: The MCP-side "no credential configured" behavior is still not designed, even though the spec requires a clear error for that case. [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L57), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md#L86), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L38) only describe swapping `CredentialResolver.resolve()` into `_initialize_copilot()` and returning early when it yields `None`. But the current runtime path then falls through to [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py#L133), which raises "Copilot SDK is not available ... and GITHUB_TOKEN is set," and the builder explicitly leaves that file unchanged at [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L41). That is neither clear nor accurate for the "no credential source is available" case promised by [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L60). Add an explicit no-credential startup state/error contract for MCP tools and carry that through the plan so the later build can meet the accepted behavior.

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: fail
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the prior phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing the new design round.
- Checked: Reviewed Round 1 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), all new design artifacts under [specs/002-credential-setup](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup), and the current runtime integration points in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py), [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py), [main.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/main.py), [Dockerfile](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/Dockerfile), [docker-compose.yml](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/docker-compose.yml), and [requirements.txt](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/requirements.txt).
- Checked: Builder-side phase compaction is correct for design; the active [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md) now contains only the new design round with a back-reference to specify history.
- Checked: Judge-side phase compaction was required because the active file still started with `specify`; I archived the prior raw rounds and added the specify phase summary before writing this design round.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). B-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: None.

### Open Questions
- None

### Round 2 — design (judge)

## Round 2 — design

### Verdict
needs_revision

### Blockers
- B-1 (AP-002): The new two-step validator still overstates what it can infer, so AC-3 / FR-005 is not actually satisfied yet. [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L44) explicitly notes that Copilot `403` responses can mean missing subscription as well as missing permissions, but the same artifact then redefines every post-`GET /user` `list_models()` failure as "missing `copilot_requests`" at [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L46), [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L50), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L53), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L54), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L42), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L55), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L87). That directly conflicts with the accepted contract that the permission bucket is specifically for missing `copilot_requests`, while other Copilot access restrictions are a separate possibility in the spec and research at [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37) and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L80). The same contract also maps any non-2xx `GET /user` response to expired/revoked auth failure at [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L49), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L53), and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L43), which is broader than FR-005's auth bucket and would misdiagnose non-auth API failures. As designed, a user can still be told to rotate a valid token or add `copilot_requests` when the real problem is an upstream / policy / entitlement issue. Fix by tightening the classification contract: only true GitHub-auth failures should map to `auth`, non-auth GitHub API failures need an unavailable-style path, and post-auth `list_models()` failures cannot be labeled as missing `copilot_requests` unless the builder can point to a reliable distinguishing signal. If that signal does not exist, escalate to Peter instead of narrowing the accepted spec by inference.

### High
- None

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: fail
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the prior phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing the new design round.
- Checked: Reviewed Round 2 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the updated [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), [plan.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/plan.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), and the current runtime integration points in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py) and [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/copilot_client.py).
- Checked: Official GitHub REST docs for `GET /user` list both `401` and `403` as possible responses for the authenticated-user endpoint, so the contract's "other non-2xx => expired/revoked" rule is too broad for an auth-only bucket. Source: https://docs.github.com/en/rest/users/users#get-the-authenticated-user
- Checked: Judge-side context management remains compliant. The active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) still contains only the current phase and fewer than two prior design rounds before this write, so no archival step was required.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). B-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Corrections: Round 2 does resolve the prior no-credential design gap. The remaining issue is the validator's still-overclaimed error classification.

### Open Questions
- None

### Round 4 — design (judge)

## Round 4 — design

### Verdict
escalated

### Blockers
- B-1: Round 4 resolves the validator type mismatch and the builder-side archival cleanup, but the design still cannot satisfy the accepted permission contract without a coordinator decision. The accepted task/spec still define AC-3 / FR-005's permission bucket as specifically "missing `copilot_requests`" at [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L24), and [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L80), while the current design explicitly broadens that bucket to generic Copilot-access denial and keeps an inconclusive auth fallback at [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L46), [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L50), [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md#L52), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L53), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md#L54), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L64), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L68), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L106), and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L107). The builder now states that mismatch directly and asks Peter to choose how FR-005 should change instead of silently redefining it at [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L152), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L160), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L170), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L173), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L176). That is the correct stopping point: further builder/judge iteration would just restate the same coordinator-owned scope decision.

### High
- None

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pending coordinator decision
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 4.
- Checked: Reviewed Round 4 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the current [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), and [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md).
- Checked: Round 4 resolves M-1. The token-validator contract now carries `bool | None` consistently across the signature, branch descriptions, and orchestration at [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L57), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L64), and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L83).
- Checked: Builder-side context management for design is now compliant. The active [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L1) keeps only recent design rounds, and design Round 1 has been moved to [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md#L156).
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `design` rounds; I moved Round 2 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 3 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). No new judge-side anti-pattern entry is needed. The builder correctly escalated instead of silently narrowing the accepted contract.
- Checked external sources: None needed. This is a repo-local scope decision.
- Corrections: Round 4 resolves the prior M-1 and L-1 findings. The remaining issue is now coordinator-owned.

### Open Questions
- Peter: should FR-005 / AC-3 keep the stricter "missing `copilot_requests`" permission meaning, broaden to generic Copilot-access denial, or collapse auth + permission back into one failure bucket?

### Round 5 — design (judge)

## Round 5 — design

### Verdict
escalated

### Blockers
- B-1 (AP-002): Round 5 says Peter required all error messages to be verbose/chatty with URLs and remediation and claims that change was applied across all design artifacts, but the actual design still leaves the format and SDK buckets underspecified. [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L196), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L198), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L211), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L216), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L223), and [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37) define the new contract as applying to each failure mode, yet [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L22) still uses the old terse format-error example with no URL or diagnostic steps, [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L25) still shows a one-line SDK error example, [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L27) and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L32) still document terse format messages only, and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L141) through [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L143) give the SDK bucket only a rebuild command rather than the URL-bearing/self-diagnosis guidance the round claims is now universal. [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L80) also weakens the rule to "specific URLs or steps," while [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37) requires "specific URLs and remediation steps," so the artifacts do not even agree on the exact message contract. As written, AC-3 is still not fully specified for the format and SDK paths, so the design cannot be accepted. Because [status.json](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/status.json#L5) and [status.json](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/status.json#L6) show this is Round 5 of 5, the protocol requires escalation rather than another normal revision round [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L247).

### High
- None

### Medium
- None

### Low
- L-1: Builder-side within-phase archival regressed again in Round 5. The active [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L3), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L63), [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L136), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L192) show four active design rounds, but before writing Round 5 the protocol required the builder to archive rounds 1 through 3 and leave only rounds 4 onward in the active file [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134), [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L138), and [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L139). If Peter allows a cleanup pass despite the round cap, Claude should archive design Rounds 2-3 before doing anything else.

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: fail
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 5.
- Checked: Reviewed Round 5 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the updated [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), [research.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/research.md), [data-model.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/data-model.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md).
- Checked: Round 5 resolves the earlier permission-scope escalation in substance. The remaining issue is narrower: the newly expanded message-format requirement was not propagated consistently to the format and SDK paths, and the task/spec/contracts now disagree on whether every message must include URLs plus steps or only URLs or steps.
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two design rounds; I moved Round 3 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 4 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L134).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). B-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 5 materially improves the design, but AC-3 is still not fully closed on the written artifacts.

### Open Questions
- Peter: do you want to allow one final cleanup round to propagate the verbose-message requirement to the format and SDK paths and re-archive [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), or do you want to accept the current design as sufficient despite those remaining documentation gaps?

### [design] Round 6 — judge

## Round 6 — design

### Verdict
needs_revision

### Blockers
- B-1 (AP-002): Round 6 fixes the wording mismatch and the format-message gap, but the SDK failure path still does not satisfy the accepted "URLs and remediation steps" contract. [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md#L37), [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md#L18), and the builder's own resolution claim at [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L151) and [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L162) all say every failure mode now carries URL-bearing guidance, yet the actual SDK examples at [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L25), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md#L84), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L102), and [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md#L190) only provide shell commands and diagnostics, with no troubleshooting URL. As written, AC-3 is still not fully specified for the SDK bucket. Fix by adding a concrete URL to the SDK error examples/templates, or by getting Peter to explicitly exempt SDK errors from the URL requirement instead of leaving the contract half-applied.

### High
- None

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: fail
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 6.
- Checked: Reviewed Round 6 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), plus the current [task.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/task.md), [spec.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/spec.md), [token-validator.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/contracts/token-validator.md), and [requirements.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/checklists/requirements.md).
- Checked: Round 6 does resolve the prior builder archival finding. The active [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L1) now keeps only recent design rounds, and the older design rounds are in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md).
- Checked: Judge-side within-phase archival was required before this write because the active [judge.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge.md) already had two `design` rounds; I moved Round 4 into [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) and left Round 5 onward active per [PROTOCOL.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/PROTOCOL.md#L117).
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). B-1 matches AP-002. No new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: Round 6 closes the format-side documentation gap and the builder archival issue. The only remaining acceptance gap is the missing SDK troubleshooting URL.

### Open Questions
- None

### [build] Round 1 — judge

(needs_revision: H-1 broad exception catch in load(), M-1 hardcoded mask_token prefix. All 9 ACs pass.)

### [build] Round 2 — judge

(accepted: Both findings addressed. 481 tests pass. No new issues.)

## [test] Archived Rounds

### Round 1 — test (judge)

## Round 1 — test

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-001): [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md#L69) marks AC-5 as verified by `TestPostSettingsRotate::test_valid_token_replaces_and_redirects`, but [test_web_routes.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_web_routes.py#L268) only proves the settings route validates, stores, and redirects. It does not verify the accepted FR-010 / AC-5 process-boundary behavior that a fresh MCP connection re-runs credential resolution and uses the rotated token. The accepted plan explicitly required MCP startup tests for this in [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71), yet [test_mcp_server_config.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_server_config.py#L1) still only covers `_parse_timeout()`, and my local coverage run leaves [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L83) through [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L111) uncovered. That means `_initialize_copilot()` can regress in the no-credential path or the next-connection rotation path without failing the suite. Fix by adding direct MCP startup tests that cover: `resolve() -> None` sets `NoCredentialError` with all 3 remediation paths, `resolve() -> token` passes that token into `_copilot.start()`, and a fresh initialization after rotation picks up the newly stored token.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: fail
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing the first `test` round.
- Checked: Reviewed [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the accepted MCP-test requirement in [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71), the current MCP startup implementation in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L83), the handler coverage in [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py), the route-level rotation test in [test_web_routes.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_web_routes.py#L268), and the current contents of [test_mcp_server_config.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_server_config.py#L1).
- Checked: Ran `pytest --cov=server --cov-report=term-missing -q` locally. Result: 482 passed, 11 warnings, 94% total coverage. The builder's headline numbers are accurate.
- Checked: The coverage report still leaves `server/mcp_server.py` lines 90-111 unexecuted, which matches the missing `_initialize_copilot()` verification described above.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). This finding matches existing AP-001; no new judge-side anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: None.

### Open Questions
- None

### Round 2 — test (judge)

## Round 2 — test

### Verdict
accepted

### Blockers
- None

### High
- None

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Re-read the phase summaries in [builder-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder-archive.md) and [judge-archive.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/judge-archive.md) before reviewing Round 2.
- Checked: Reviewed the builder's Round 2 evidence in [builder.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/002-credential-setup/builder.md), the accepted MCP-test requirement in [tasks.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/specs/002-credential-setup/tasks.md#L71), the startup implementation in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L74), and the new direct `_initialize_copilot()` coverage in [test_mcp_server_config.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_server_config.py#L70).
- Checked: [test_mcp_server_config.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_server_config.py#L93) now covers the three concrete behaviors required by M-1: `resolve() -> None` stores `NoCredentialError` with all remediation paths, `resolve() -> token` passes the resolved token into `_copilot.start()`, and a fresh `_initialize_copilot()` call after rotation picks up the new token while constructing a fresh resolver/store pair.
- Checked: [test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/tests/test_mcp_handlers.py#L155) still maps `NoCredentialError` to `no_credential` for `start_review`, so the startup-error path does not fall through to `internal`.
- Checked: Ran `pytest tests/test_mcp_server_config.py -q` locally. Result: 25 passed in 0.31s.
- Checked: Ran `pytest tests/test_mcp_handlers.py -q` locally. Result: 22 passed in 0.32s.
- Checked: Ran `pytest --cov=server --cov-report=term-missing -q` locally. Result: 494 passed, 11 warnings, 95% total coverage. [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/server/mcp_server.py#L83) is now 89% covered, and the previous `_initialize_copilot()` blind spot is gone from the miss list.
- Checked: The remaining coverage misses in `server/mcp_server.py` are handler/error branches outside spec 002's MCP-credential boundary, so they do not block AC-5 or this phase outcome.
- Checked: [ANTIPATTERNS.md](/Users/Peter_Petroczy/Documents/Projects/Agent-in-a-Box/agent-loop/ANTIPATTERNS.md). The prior AP-001 finding is resolved; no new anti-pattern entry is needed.
- Checked external sources: None needed. This review is repo-local.
- Corrections: M-1 is resolved.

### Open Questions
- None
