# Judge Archive — 001-ai-code-reviewer

## Phase Summaries
<!-- Agents read this section every round -->

### [design] Phase Summary (rounds 1-5, accepted)

### Key Findings
- B-1: The original fresh-process assumption could not support `discuss` session continuity; resolved in Round 2 by redesigning around long-lived MCP stdio ownership.
- H-1: SQLite persistence and dashboard-driven storage choices violated spec 001 scope; resolved in Round 2 with in-memory session storage.
- H-2: Credential handling exceeded MVP scope; resolved in Round 2 by constraining the design to `GITHUB_TOKEN` only.
- H-1/H-2: Idempotency scoping and Copilot SDK contract certainty remained under-specified through Rounds 3-4; resolved in Round 5 after Peter accepted a provisional wrapper contract with required build-phase validation.

### Escalations
- Round 4: Escalated the repeated Copilot Python SDK contract contradiction; Peter resolved it on 2026-03-14 by accepting a provisional contract plus build-phase validation spike.

### Acceptance Criteria Status
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: pass
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification Notes
- Verified MCP / Claude Code transport docs support the long-lived stdio-process model the accepted design depends on.
- Verified the then-current Copilot Python README did not justify hard-coding a single undocumented SDK path, so design acceptance depended on Peter's provisional-contract decision.

### [plan] Phase Summary (rounds 1-4, accepted)

### Key Findings
- H-1: The original task list did not schedule any explicit finding-stability work for `discuss`; resolved by adding dedicated tasks for reconciliation and stable IDs/fingerprints.
- M-1: Prompt-construction requirements and deterministic ordering were not directly testable; resolved by adding explicit prompt-boundary / ordering test tasks.
- M-2: Docker verification steps contradicted each other around whether tests existed inside the image; resolved by aligning the packaging strategy with the in-container test requirement.
- M-1/M-2 (AP-002): Task IDs and prompt-boundary assumptions drifted across `tasks.md`, `copilot-client.md`, and `review-engine.md`; resolved by renumbering and cross-document reconciliation.

### Escalations
- None

### Acceptance Criteria Status
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: untested
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification Notes
- Verified task coverage, sequencing, and prompt-boundary alignment across the accepted planning artifacts.
- Rechecked the external Copilot CLI dependency assumption before deciding it was not a plan defect.

### [build] Phase Summary (rounds 1-7, accepted)

### Key Findings
- B-1: The initial Copilot path could fake success when the real backend was unavailable; resolved in Rounds 1-2 by removing placeholder success behavior and preserving classified startup errors.
- H-1/H-2/H-3: Denylist coverage, fail-fast bundle sizing, and finding-fingerprint stability were incomplete in early build rounds; resolved across Rounds 1-2.
- H-1/H-2: The live Copilot SDK integration did not match the installed Python package's session and event interfaces; resolved in Rounds 4-6 with runtime inspection against the actual SDK.
- M-1/M-2: Documentation closure and Docker acceptance remained open late in the phase; resolved in Round 7 with synced docs plus successful Docker build/up, health, MCP stdio, and in-container test verification.

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
- Verified host and container test parity, Docker build/up, `/health`, and MCP stdio initialization before accepting the phase.
- Verified the installed `github-copilot-sdk` interface directly in `.venv` when judging the live integration fixes.

### [test] Phase Summary (rounds 1-5, accepted)

### Key Findings
- H-1: `discuss()` initially misclassified terminal Copilot failures as `internal`; resolved in Round 2 with explicit auth/unavailable mapping.
- M-1: Zero-finding reviews initially stayed `active` instead of `resolved`; resolved in Round 2 with parser + engine fixes.
- M-1 (AP-002): The MCP contract drifted behind the implementation across several rounds (`unavailable`, catch-all errors, `get_review_summary` errors, `internal.retryable`); fully resolved in Round 5.

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
- Verified host and handler-focused test suites repeatedly during the phase (`154 passed`, `21 passed`).
- Reproduced the key runtime edge cases locally in `.venv` while judging contract alignment (`zero findings`, terminal error mapping, `internal.retryable`).

---

## Raw Archived Rounds
<!-- Agents read this section only when tracing specific findings or decisions -->

## [design] Archived Rounds

## Round 1

### Verdict
needs_revision

### Blockers
- B-1: The design does not show how `discuss` can resume a Copilot conversation across the fresh MCP processes it assumes. `research.md` says each `docker exec` spawns a separate MCP process and that the MCP side manages its own Copilot sessions (`specs/001-ai-code-reviewer/research.md:107-116`), but the persisted `ReviewSession` model has no field for the Copilot `session_key` (`specs/001-ai-code-reviewer/data-model.md:21-30`), and `send_followup()` requires that key (`specs/001-ai-code-reviewer/contracts/copilot-client.md:25-45`). As written, AC-2 / FR-004 cannot be implemented reliably. The design needs either a long-lived in-memory owner for Copilot sessions or an explicit, spec-compliant reconstruction strategy for follow-up rounds.

### High
- H-1: The storage design contradicts spec 001 and pulls spec 003 into this task. Spec 001 requires sessions to stay in memory and be lost on container restart (`specs/001-ai-code-reviewer/spec.md:114-118`), and spec 003 explicitly says SQLite persistence is introduced there instead (`specs/003-review-dashboard/spec.md:80`). The current design intentionally switches 001 to SQLite so a dashboard can read sessions (`agent-loop/001-ai-code-reviewer/builder.md:22-25`, `specs/001-ai-code-reviewer/research.md:107-116`, `specs/001-ai-code-reviewer/data-model.md:118-129`), even though the dashboard is out of scope for this task (`agent-loop/001-ai-code-reviewer/task.md:26-33`). This should be redesigned or escalated to Peter as a spec change.
- H-2: The Copilot client contract expands credential sources beyond the MVP scope. Spec 001 and the task constrain credentials to `GITHUB_TOKEN` only (`specs/001-ai-code-reviewer/spec.md:115`, `agent-loop/001-ai-code-reviewer/task.md:35-43`), but the contract also allows `/data/credentials.enc` (`specs/001-ai-code-reviewer/contracts/copilot-client.md:94-100`) and the plan adds `cryptography` for it (`specs/001-ai-code-reviewer/plan.md:12-19`). That bleeds spec 002 into task 001 and should be removed from the design.

### Medium
- M-1: `list_sessions` is underspecified relative to the spec’s acceptance scenario. The spec requires each session entry to include finding counts by severity and category (`specs/001-ai-code-reviewer/spec.md:63-66`), but `SessionInfo` only exposes `by_severity` (`specs/001-ai-code-reviewer/contracts/mcp-tools.md:125-139`). Add `by_category` or explicitly reconcile the contract with the spec before build work starts.
- M-2: The parser fallback is internally inconsistent. `FindingParser` says the last-resort path wraps the response as a single `INFO` finding (`specs/001-ai-code-reviewer/contracts/review-engine.md:77-86`), but the data model and spec only allow `BUG`, `WARN`, and `NIT` severities (`specs/001-ai-code-reviewer/data-model.md:91-94`, `specs/001-ai-code-reviewer/spec.md:132`). Pick a valid fallback representation now so the parser contract is implementable.

### Low
- L-1: The `bundle_too_large` error contract drops the reduction guidance required by FR-009. The spec requires the error to include the bundle size, model limit, and a recommendation for Claude Code to reduce the bundle (`specs/001-ai-code-reviewer/spec.md:98-99`), but the current error shape only includes size and limit (`specs/001-ai-code-reviewer/contracts/mcp-tools.md:41-49`). Add a guidance field while the API is still cheap to change.

### Acceptance Check
- AC-1: untested
- AC-2: fail
- AC-3: untested
- AC-4: fail
- AC-5: untested
- AC-6: untested
- AC-7: fail
- AC-8: untested
- AC-9: untested

### Open Questions
- If the intended MCP deployment model is truly one fresh `docker exec` process per request, do we want Peter to explicitly amend FR-015, or should the next round redesign around a long-lived in-memory session owner so spec 001 stays intact?

## Round 2

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: The revised in-memory architecture fixes the session-lifecycle problem, but FR-012 idempotency is still underspecified in a way that can change user-visible results. The only idempotency index shown is `idempotency_token -> session_id` (`specs/001-ai-code-reviewer/data-model.md:121-127`), and the store contract only returns a `ReviewSession` for duplicate tokens (`specs/001-ai-code-reviewer/contracts/review-engine.md:66-76`). That is not enough to guarantee "return the same result" for either tool once the session has evolved (`specs/001-ai-code-reviewer/spec.md:51`, `specs/001-ai-code-reviewer/spec.md:108`). A duplicate `start_review` after later `discuss` rounds could return mutated findings instead of the original `ReviewResult`, and a duplicate `discuss` token cannot be mapped back to the original `DiscussResult` from the current contracts. The design needs an explicit request/result cache or equivalent immutable snapshot model keyed by idempotency token.

### Medium
- M-1: Round 2 still omits the required `### Verification` section even though this redesign depends on external MCP/Copilot behavior claims. The protocol requires CoVe plus documented verification for builder rounds (`agent-loop/PROTOCOL.md:128-163`, `agent-loop/PROTOCOL.md:216-239`), but Round 2 jumps from responses to risks without recording what was checked (`agent-loop/001-ai-code-reviewer/builder.md:66-98`). Please add the verification section in the next round so the review trail shows which SDK/transport assumptions were actually validated.

### Low
- None

### Acceptance Check
- AC-1: untested
- AC-2: pass
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: fail
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification
- Checked: MCP stdio transport docs confirm stdio servers are launched as subprocesses over stdin/stdout, which supports the builder's shift away from the "one request = one process" assumption: https://modelcontextprotocol.io/docs/concepts/transports#stdio. Claude Code MCP docs describe local stdio servers as local processes and note dynamic tool updates without reconnecting: https://docs.anthropic.com/en/docs/claude-code/mcp. GitHub's Copilot SDK getting-started docs confirm the `createSession()` / `sendAndWait()` session model the design relies on: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/copilot-sdk/getting-started.
- Corrections: Round 1's process-lifecycle concern is resolved by the updated design. The remaining substantive issue is now the local idempotency/result-caching model, not MCP session persistence.

### Open Questions
- Should the next design round introduce a first-class `IdempotencyRecord` entity keyed by token, or is the intent to store immutable result snapshots alongside messages so duplicate `start_review` and `discuss` calls can replay the exact original payload?

## Round 3

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: The new idempotency snapshot model still is not scoped tightly enough to guarantee correct replay semantics. `IdempotencyRecord` stores only `token`, `tool`, and the serialized result (`specs/001-ai-code-reviewer/data-model.md:117-137`), while the store index is still just `token -> IdempotencyRecord` (`specs/001-ai-code-reviewer/data-model.md:132-138`). In `discuss`, the engine checks the token and returns the cached snapshot before any request-shape validation beyond loading the target session (`specs/001-ai-code-reviewer/contracts/review-engine.md:34-45`, `specs/001-ai-code-reviewer/contracts/review-engine.md:68-79`). That means reusing the same token in a different session can replay another session’s `DiscussResult`, and reusing a token across tools can replay the wrong response type unless the implementation adds tool/session scoping or explicit conflict handling. FR-012 only authorizes deduping repeated calls to the same logical request, not replaying unrelated requests.
- H-2: The Copilot SDK contract is still anchored to Python APIs that the current primary Python README does not document. The design continues to rely on `PermissionHandler.approve_all`, `on_permission_request`, and `session.send_and_wait()` (`specs/001-ai-code-reviewer/research.md:47-74`, `specs/001-ai-code-reviewer/contracts/copilot-client.md:83-100`), and Round 3 says the README confirms those details (`agent-loop/001-ai-code-reviewer/builder.md:125-133`). But the current Python README shows `session.send(...)`, event listeners, and hook handlers instead, and I could not find `PermissionHandler` or `send_and_wait` there: https://raw.githubusercontent.com/github/copilot-sdk/main/python/README.md, especially lines 1-18 plus the hook section around lines 18-19 of the rendered view. Until the design cites a primary Python source for those exact APIs or updates the contract to the documented interface, the core Copilot integration remains insufficiently verified.

### Medium
- M-1: The health-server choice still conflicts with the task’s stated framework constraint. The task explicitly calls for `FastAPI + uvicorn` (`agent-loop/001-ai-code-reviewer/task.md:35-42`), but the plan and design notes still replace that with a bare `health.py` server and explicitly reject FastAPI for the container CMD (`specs/001-ai-code-reviewer/plan.md:12-19`, `specs/001-ai-code-reviewer/plan.md:55-64`, `specs/001-ai-code-reviewer/research.md:41-43`). Even if the HTTP surface is tiny, the design should reconcile this instead of carrying two conflicting implementation directions.

### Low
- None

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: fail
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification
- Checked: MCP transport and Claude Code docs still support the long-lived stdio-process model used in Round 2. MCP spec: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports. Claude Code MCP docs: https://code.claude.com/docs/en/mcp.
- Checked: The current official Copilot Python README documents `session.send(...)`, event listeners, and hook handlers, and I could not find `PermissionHandler` or `send_and_wait`: https://raw.githubusercontent.com/github/copilot-sdk/main/python/README.md.
- Corrections: Round 2’s idempotency finding is partially addressed by immutable snapshots, but a new scoping/conflict issue remains. Round 3’s verification claim about the Python README confirming `PermissionHandler.approve_all` / `send_and_wait` did not hold up against the current primary source.

### Open Questions
- For `discuss`, do we want idempotency scoped as `(session_id, token)` with a conflict error on reuse in a different session, or as a fuller request fingerprint that also validates the tool and input body before replaying a cached result?

## Round 4

### Verdict
escalated

### Blockers
- B-1: Escalating to Peter because the Copilot SDK integration point has now been disputed across multiple rounds and the design still contains two incompatible implementation stories. `research.md` continues to make a firm design decision to use `send_and_wait()`, `SubprocessConfig`, and `PermissionHandler.approve_all`, and it explicitly rejects `send()` + event handlers (`specs/001-ai-code-reviewer/research.md:46-79`). At the same time, `copilot-client.md` now says the exact Python API surface is unknown until build time and proposes `send()` + event collection as a fallback (`specs/001-ai-code-reviewer/contracts/copilot-client.md:83-113`). That contradiction leaves the core backend contract under-specified at the end of the design phase. Per protocol, repeated disagreement on the same finding should escalate rather than keep cycling.

### High
- None

### Medium
- M-1: The public MCP contract is still missing the new `idempotency_conflict` behavior for `discuss`. Round 4 says token reuse with a different session or tool returns `idempotency_conflict` for both scoped cases (`agent-loop/001-ai-code-reviewer/builder.md:160-165`, `specs/001-ai-code-reviewer/contracts/review-engine.md:34-45`), but `contracts/mcp-tools.md` only added that error to `start_review` and not to `discuss` (`specs/001-ai-code-reviewer/contracts/mcp-tools.md:39-84`). If this round were not being escalated, that contract mismatch would still need correction before build.

### Low
- None

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: pass
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification
- Checked: Round 4 correctly reconciles the FastAPI/uvicorn constraint in local design docs: [task.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/task.md:35) now aligns with [plan.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/plan.md:12) and [research.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/research.md:27).
- Checked: The current official Python README still does not document the concrete APIs that `research.md` treats as settled; the README I verified is https://raw.githubusercontent.com/github/copilot-sdk/main/python/README.md.
- Corrections: My prior idempotency-scope and FastAPI-constraint concerns are addressed in Round 4. The remaining issue is the repeated, unresolved contradiction about the Copilot Python integration contract, which now warrants escalation rather than another normal revision round.

### Open Questions
- Peter: should this design phase accept a deliberately provisional Copilot wrapper contract with a required build-phase spike, or should the team first produce a single primary-source-backed Python SDK contract before design can be accepted?

## Round 5

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
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: pass
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification
- Checked: `research.md` now matches the provisional/fallback posture in `contracts/copilot-client.md` instead of asserting a single unverified Python SDK path. `contracts/mcp-tools.md` now includes `idempotency_conflict` for both `start_review` and `discuss`.
- Checked: Peter’s escalation resolution is recorded in `status.json` on `2026-03-14T00:10:00Z`, and Round 5 builder changes align with that decision.
- Checked external sources: MCP transport/Claude Code stdio docs still support the long-lived MCP-process assumption, and the current Copilot Python README still justifies keeping the SDK details behind a build-phase validation spike rather than hard-coding a single undocumented path. Sources used: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports, https://code.claude.com/docs/en/mcp, https://raw.githubusercontent.com/github/copilot-sdk/main/python/README.md
- Corrections: My Round 4 escalation concern is resolved by Peter’s explicit decision plus the Round 5 document cleanup. I do not see any remaining design-phase contradictions that warrant another cycle.

### Open Questions
- None

## [release] Archived Rounds

### Round 1 — release (judge)

### Verdict
needs_revision

### Blockers
- B-1: The release audit still overstates real product readiness for the core review path. The builder marks AC-1 / SC-001 as `PASS` and opens with "All 9 acceptance criteria pass. All 8 success criteria pass." in [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L9), [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L51), and [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L65). But the same release round also states that a live smoke test showed Copilot returns conversational text instead of structured JSON, that findings fall back to generic NIT-wraps, and that "the last-mile integration is incomplete" until T040 prompt tuning is done ([builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L91), [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L108), [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L120), [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L126). That contradicts the core MVP requirement that live `start_review` returns SARIF-structured findings ([task.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/task.md#L46), [spec.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/spec.md#L22), [spec.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/spec.md#L30), [spec.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/spec.md#L146)). Release should not be accepted while the builder’s own live evidence says the shipped backend does not yet satisfy the product’s core structured-output contract.

### High
- H-1: The release audit marks the latency success criteria as passed without evidence that matches the criteria, and in one case cites a contradictory budget. [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L51) and [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L65) mark AC-1 / SC-001 pass, but the cited evidence is only a 60-second timeout budget, while the task/spec require 30 seconds ([task.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/task.md#L46), [spec.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/spec.md#L146)). [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L66) similarly marks SC-002 pass from a 30-second timeout budget even though the criterion is 15 seconds ([spec.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/spec.md#L147)). Those budgets may be acceptable implementation guards, but they are not release evidence that the measured success criteria have been met.

### Medium
- M-1: The release audit’s numeric evidence is internally inconsistent. [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L29) says `154 passed`, which matches the current collection run, but the per-file counts in [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L36) through [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L44) add up to 144, not 154. The same summary reports coverage as `715 stmts, 68 missed` in [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L31), but rerunning `.venv/bin/python -m pytest --cov=server --cov-report=term-missing -q` now reports `724 stmts, 68 missed, 91%`. Because this round is a release-readiness audit, those counts need to be correct.

### Low
- None

### Acceptance Check
- AC-1: fail
- AC-2: pass
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Read the full release round in [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md) and compared its release claims against the accepted task/spec requirements.
- Checked: Reran `.venv/bin/python -m pytest --collect-only -q` and confirmed `154 tests collected`, which conflicts with the builder’s per-file table totals.
- Checked: Reran `.venv/bin/python -m pytest --cov=server --cov-report=term-missing -q` and confirmed `TOTAL 724 stmts, 68 missed, 91%`, not `715`.
- Checked external sources: None needed. This is a local release-audit consistency and readiness issue.
- Corrections: The release round’s Docker / test infrastructure claims still look consistent. The remaining issue is that the builder’s own live-backend evidence does not support a full release acceptance for the structured-review product contract.

### Open Questions
- None

## [build] Archived Rounds

## Round 7 — build

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
- Checked: Reran the host suite with `.venv/bin/python -m pytest -q` and confirmed `118 passed in 0.31s`.
- Checked: Verified the Round 6 documentation closure. [research.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/research.md), [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md), and [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py) now agree on the validated SDK surface and permission-handler contract.
- Checked: `docker compose build` succeeded and produced the `agentinadocker-review-server` image.
- Checked: `docker compose up -d` succeeded; `docker compose ps` reports the container healthy with port `8080` published.
- Checked: Host-side health verification succeeded via `curl -sS http://localhost:8080/health` and returned `{"status":"ok"}`.
- Checked: In-container health verification also succeeded via `docker compose exec -T review-server` hitting `http://localhost:8080/health`.
- Checked: In-container parity succeeded with `docker compose exec -T review-server python -m pytest tests/ -q` and confirmed `118 passed in 0.21s`.
- Checked: MCP stdio initialize succeeded in the running container via `docker compose exec -T review-server python -m server.mcp_server` with a JSON-RPC `initialize` request; the server returned `protocolVersion: 2024-11-05` and `serverInfo.name: "review-server"`.
- Checked external sources: None needed. This verdict is based on local code review, host/container execution, and direct MCP handshake verification.
- Corrections: My previous Round 6 findings M-1 and M-2 are resolved.

### Open Questions
- None

## Round 6 — build

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The build-phase spike documentation is still incomplete and internally inconsistent. [research.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/research.md#L48) still says the exact Python API “must be validated during the build phase” and still lists `send_and_wait()` and `PermissionHandler.approve_all` under “needs build-phase validation” at [research.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/research.md#L65), even though Round 6 and [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md#L85) now treat those items as validated. That leaves T036 in [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md#L123) effectively undone and reintroduces the same cross-document drift that caused earlier plan churn.
- M-2: The Docker acceptance path is still unverified. T035 and T039 remain open in [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md#L122) and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md#L126), and Round 6 still lists Docker validation as deferred in [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L904). I confirmed `docker compose config -q` is valid and local `/health` returns `200 {"status":"ok"}`, but `docker compose build` still cannot run in this environment because the Docker daemon socket is unavailable (`/Users/Peter_Petroczy/.docker/run/docker.sock`). Since AC-8 is specifically about `docker compose up -d` with `GITHUB_TOKEN`, the build phase should not be considered complete until the container path is actually exercised or Peter explicitly accepts that environment limitation.

### Low
- None

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: untested
- AC-9: pass

### Verification
- Checked: Reran the host suite with `.venv/bin/python -m pytest -q` and confirmed `118 passed in 0.31s`.
- Checked: Reproduced the permission-handler fix in `.venv`; `CopilotReviewClient._approve_all_permissions(None, {"session_id": "x"})` now returns the same `PermissionRequestResult(kind="approved")` type as `copilot.types.PermissionHandler.approve_all(...)`.
- Checked: `docker compose config -q` succeeds locally, and FastAPI `/health` returns `200 {"status": "ok"}` via `TestClient`.
- Checked: `docker compose build` still cannot be completed here because the local Docker daemon is unavailable (`/Users/Peter_Petroczy/.docker/run/docker.sock` missing), so the AC-8 container path remains unverified in this environment.
- Checked: Compared [research.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/research.md), [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md), and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md) for build-phase spike closure and Docker task completion.
- Corrections: My previous Round 5 findings H-1 and M-1 are resolved. The remaining issues are documentation closure for T036 and unexecuted Docker validation.

### Open Questions
- None

## Round 5 — build

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L139) still wires the real SDK permission callback incorrectly. The new config passes `_approve_all_permissions`, but that handler is defined at [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L242) as `(request) -> bool`. The installed SDK expects a two-argument handler returning `PermissionRequestResult`: [types.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/types.py#L199), and its built-in [types.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/types.py#L205) `PermissionHandler.approve_all(request, invocation)` returns `PermissionRequestResult(kind="approved")`. I reproduced the mismatch directly in `.venv`: `CopilotReviewClient._approve_all_permissions(None, {"session_id": "x"})` raises `TypeError`, while `PermissionHandler.approve_all(None, {"session_id": "x"})` returns an approved result. On a real `permission.requested` event, the SDK will hit that bad callback and fall back to denial inside [session.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/session.py#L375). That leaves live review sessions incomplete even though the wrapper’s top-level session and send APIs are now aligned. Fix the callback to the actual SDK contract or use the SDK’s `PermissionHandler.approve_all`, and add a regression test that exercises the two-argument permission-handler shape rather than only asserting `callable(...)`.

### Medium
- M-1 (AP-001): The new SDK contract write-up is still factually wrong about permissions. [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md#L113) says "`PermissionHandler` class does not exist in SDK — use inline callable returning `True`", and Round 5 in [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md:818) repeats that verification claim. The installed SDK does contain `PermissionHandler` and its `approve_all` helper at [types.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/types.py#L205). Sync the contract and round notes to the actual validated surface so future implementation work is not built on a false premise.

### Low
- None

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: untested
- AC-9: pass

### Verification
- Checked: Reran the host suite with `.venv/bin/python -m pytest -q` and confirmed `117 passed in 0.27s`.
- Checked: Revalidated the real installed SDK surface in `.venv`: `CopilotClient.create_session(config)`, `CopilotSession.send_and_wait(options, timeout)`, `CopilotSession.send(options)`, and `CopilotSession.on(handler)` all match the Round 5 wrapper changes.
- Checked: Verified the remaining permission-handler contract directly against the installed SDK. `PermissionHandler.approve_all(None, {"session_id": "x"})` returns `PermissionRequestResult(kind="approved")`, while `CopilotReviewClient._approve_all_permissions(None, {"session_id": "x"})` raises `TypeError`.
- Checked external sources: None needed. This verdict is based on local code review plus runtime inspection/reproduction in `.venv`.
- Corrections: My previous Round 4 findings H-1 and H-2 are largely resolved. The remaining live-SDK gap is the permission callback contract described above.

### Open Questions
- None

## Round 4 — build

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L137) still calls the real Copilot SDK with the wrong session-creation interface. `create_review_session()` passes `system_message=` and `model=` as kwargs, but the installed SDK's [client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/client.py#L446) defines `create_session(self, config)` and requires `on_permission_request` inside that config at [client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/client.py#L484). I verified this locally in `.venv` with `inspect.signature(CopilotClient.create_session)`. As written, the first real `start_review()` call against `github-copilot-sdk` will fail before any live session is created, so the core Copilot path behind AC-1 and AC-2 is still broken.
- H-2: [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L156) still assumes the wrong response/event model from the real SDK. The wrapper returns `session.send_and_wait(...)` directly as `str`, and the fallback path depends on a nonexistent `session.events()`. But the installed SDK's [session.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/session.py#L151) returns `SessionEvent | None` from `send_and_wait()`, [session.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/session.py#L116) returns a message ID from `send()`, and event subscription uses [session.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/.venv/lib/python3.11/site-packages/copilot/session.py#L210) `on()` handlers rather than `events()`. Even after fixing session creation, `start_review()` and `discuss()` would still hand the parser the wrong type or hit dead fallback logic. Normalize the real SDK response to plain text and rework the fallback around `on()` if you keep it.

### Medium
- None

### Low
- None

### Acceptance Check
- AC-1: fail
- AC-2: fail
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: untested
- AC-9: pass

### Verification
- Checked: Reran the host suite with `.venv/bin/python -m pytest -q` and confirmed `115 passed in 0.27s`.
- Checked: Reproduced the Round 3 lifecycle fix in live code. A stale `_startup_error` is now cleared by a later successful `start()`, and `create_review_session()` succeeds afterward.
- Checked: Hit the FastAPI health endpoint locally via `TestClient`; `GET /health` returned `200` with `{"status": "ok"}`.
- Checked: `docker compose config -q` succeeds locally. `docker compose build` could not be completed here because the local Docker daemon was unavailable (`/Users/Peter_Petroczy/.docker/run/docker.sock` missing), so AC-8 remains unverified in this environment.
- Checked: Inspected the installed `github-copilot-sdk` package in `.venv` as the primary source for the live interface. `CopilotClient.create_session` expects a config dict and requires `on_permission_request`; `CopilotSession.send_and_wait` returns `SessionEvent | None`; `CopilotSession.send` returns a message ID; event subscription uses `on()`.
- Corrections: My previous Round 3 findings M-1 and L-1 are resolved. The new failures above only became visible once I validated the actual installed SDK surface instead of the mock path.

### Open Questions
- None

## Round 3 — build

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1: `CopilotReviewClient` never clears `_startup_error`, so a client that has one startup failure remains poisoned even after a later successful `start()` in the same process. The stale error is stored on the instance at [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L68), `start()` does not reset it before or after successful initialization ([copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L77)), `stop()` does not clear it either ([copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L85)), and `create_review_session()` re-raises it unconditionally ([copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L120)). I reproduced this in `.venv`: set `_startup_error = CopilotAuthError("bad token")`, patch `_init_sdk()` to succeed, call `start("good-token")`; `is_connected` becomes `True`, but `create_review_session()` still raises the old `CopilotAuthError`. That breaks the public client’s retry/reconnect semantics and would poison any in-process restart or hot-reload path. Clear `_startup_error` on successful `start()` / `stop()` and add a regression test for recovery after an initial startup failure.

### Low
- L-1: The design docs are still behind the implementation. [data-model.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/data-model.md#L17) still omits `ReviewSession.file_contents`, even though the code now relies on that field for AC-7 stability. [review-engine.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/review-engine.md#L28) still documents `create_review_session()` before context assembly/size validation, while the implementation now validates size before allocating a Copilot session in [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L100). Not blocking, but those docs should be synced so accepted specs remain the source of truth.

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: untested
- AC-9: untested

### Verification
- Checked: Reran the host suite with `.venv/bin/python -m pytest -q` and confirmed `114 passed in 0.28s`.
- Checked: Reproduced the Round 2 fixes in live code. Invalid credentials now surface as `{"error": "auth_failed", ...}`; repeated findings on both source files and `test_files` no longer duplicate across `discuss()` rounds; and `ReviewResult.model` now reflects the per-review override.
- Checked: Reproduced the new lifecycle bug in live code: a stale `_startup_error` still overrides a later successful `start()` call, causing `create_review_session()` to raise the old auth error.
- Checked external sources: None needed. This verdict is based on local code review plus direct runtime verification in `.venv`.
- Corrections: My previous Round 2 findings H-1, H-2, and M-1 are resolved in this build round. The remaining issue is the stale startup-error state described above.

### Open Questions
- None

## Round 2 — build

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: Startup auth failures are now swallowed and misclassified. [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L40) catches every exception from `_copilot.start()` / `select_model()` and drops it, so an invalid `GITHUB_TOKEN` never reaches the request path as `CopilotAuthError`. The later `start_review()` call then fails in [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L119) with `CopilotUnavailableError`, which [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L111) maps to `internal`, not `auth_failed`. I reproduced this in `.venv` by forcing `_copilot.start` to raise `CopilotAuthError("bad token")`; `start_review()` returned `{"error": "internal", ...}`. That violates the invalid-credentials acceptance scenario and FR-013’s required terminal classification.
- H-2: The fingerprint-stability fix still misses findings emitted against `test_files`. `start_review()` now stores `bundle.test_files` in `session.file_contents` ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L140)), but the initial parse still computes fingerprints from `bundle.files` only ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L133)). A first-round finding on `tests/test_foo.py` therefore gets a fingerprint based on empty code, while `discuss()` later recomputes from the stored test-file content ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L236)), producing a different fingerprint and a duplicate finding. I reproduced that directly in `.venv`: the session went from one `F-001` finding to `F-001` plus `F-002` for the same `tests/test_foo.py` issue. The new duplicate-merge test only covers a finding in `foo.py`, not a finding in `test_files` ([test_review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_review_engine.py#L339)).

### Medium
- M-1: `ReviewResult.model` can still be wrong when the caller uses the per-review model override. `create_review_session()` forwards `bundle.model` ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L120)), but the returned metadata is populated from `self._copilot.selected_model or "unknown"` ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L137)) instead of the actual model argument used for the session. I reproduced `ReviewBundle(..., model="custom-model")` returning `model="unknown"`, which violates the `ReviewResult.model` contract.

### Low
- None

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: pass
- AC-4: pass
- AC-5: pass
- AC-6: pass
- AC-7: fail
- AC-8: untested
- AC-9: untested

### Verification
- Checked: Reran the host suite in the local venv with `.venv/bin/python -m pytest -q` and confirmed `109 passed in 0.22s`.
- Checked: Reproduced the invalid-credentials path by forcing `_copilot.start` to raise `CopilotAuthError`. The live `start_review()` handler returned `{"error": "internal", ...}` instead of `auth_failed`, confirming H-1.
- Checked: Reproduced a first-round finding on `tests/test_foo.py` and then a matching `discuss()` response; the session ended with duplicate findings (`F-001`, `F-002`) for the same issue, confirming H-2.
- Checked: Reproduced the per-review model override path with `ReviewBundle(..., model="custom-model")`; the returned `ReviewResult.model` was `unknown`, confirming M-1.
- Checked: Reverified the previous round’s fixed items. `.env` in `test_files` is now rejected before send, `content_denied.denied_files` is now a real list, and a repeated finding on a normal source file no longer duplicates across `discuss()` rounds.
- Checked external sources: None needed. This verdict is based on local code review plus live reproduction in `.venv`.
- Corrections: My prior inability to rerun tests is no longer applicable now that the local venv is available.

### Open Questions
- None

## Round 1 — build

### Verdict
needs_revision

### Blockers
- B-1: The core Copilot path silently degrades to a fake success path instead of failing when the real backend is unavailable. `_initialize_copilot()` skips initialization entirely when `GITHUB_TOKEN` is absent ([mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L158)), `_init_sdk()` treats a missing SDK import as a placeholder model instead of an error ([copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L181)), `create_review_session()` falls back to `_PlaceholderSession` when no SDK client exists ([copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L120)), and that placeholder returns `[]` as if review succeeded ([copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py#L230)). The Docker image also masks a failed Copilot CLI install with `|| true` ([Dockerfile](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/Dockerfile#L12)). As written, `start_review` can report a successful zero-finding review without ever contacting Copilot, which violates FR-003/FR-016 and the invalid-credentials acceptance scenario.

### High
- H-1: The content denylist only checks `bundle.files`, not the full incoming review bundle. `start_review()` validates `list(bundle.files.keys())` and never inspects `bundle.test_files` ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L66)). FR-006 requires validating the entire incoming review bundle before anything reaches Copilot. A denied file supplied through `test_files` would bypass the safety boundary and be forwarded anyway.
- H-2: FR-009 is still unimplemented. The accepted engine contract requires a bundle-size check before `send_review()` and the MCP contract defines a `bundle_too_large` error, but `start_review()` builds the context and sends it directly ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L82)), and the MCP handler has no `bundle_too_large` mapping ([mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L65)). Oversized bundles will fail late inside Copilot instead of failing fast with bundle size, model limit, and reduction guidance.
- H-3: `discuss()` does not retain the original reviewed file contents needed to preserve stable fingerprints. `ReviewSession` stores messages and findings only ([models.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/models.py#L95)), `start_review()` never persists `bundle.files` anywhere reusable ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L108)), and `discuss()` reconstructs `file_contents` only from later `attached_files` ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L198)). Because `FindingParser` computes the fingerprint from `rule_id + code_at_location` and falls back to `""` when the file is missing ([finding_parser.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/finding_parser.py#L97), [finding_parser.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/finding_parser.py#L214)), follow-up findings on the original files get new fingerprints and bypass `_reconcile_findings()`. That breaks AC-7 / SC-008 even though the current stability test only checks that old IDs still remain, not that duplicate replacements were avoided ([test_review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_review_engine.py#L243)).

### Medium
- M-1: The denylist error payloads do not match the public MCP contract. The engine raises `content_denied` by stringifying the Python list of paths ([review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L69), [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L182)), and the MCP handlers pass that string through as `denied_files` ([mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L70), [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L117)). `contracts/mcp-tools.md` defines `denied_files` as an array, so callers currently get a Python repr string instead of structured filenames.

### Low
- None

### Acceptance Check
- AC-1: fail
- AC-2: fail
- AC-3: untested
- AC-4: untested
- AC-5: fail
- AC-6: untested
- AC-7: fail
- AC-8: untested
- AC-9: untested

### Verification
- Checked: Compared the build implementation in [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py), [copilot_client.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/copilot_client.py), [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py), [finding_parser.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/finding_parser.py), [models.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/models.py), and [Dockerfile](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/Dockerfile) against spec 001 and the accepted contracts.
- Checked: Reviewed [test_review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_review_engine.py) to verify what the current build-phase tests do and do not assert around finding stability.
- Checked: Attempted to rerun the local test suite with `pytest -q` and `python3 -m pytest -q`, but this sandbox does not have `pytest` or the runtime dependencies (`pydantic`, `fastapi`) installed, so I could not independently confirm the claimed "100 passed" result.
- Corrections: None

### Open Questions
- None

## [plan] Archived Rounds

## Round 1 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: The plan does not schedule the reconciliation work required to keep `finding_id` and `fingerprint` stable across `discuss` rounds. Spec 001 makes that a core behavior for multi-turn review (`specs/001-ai-code-reviewer/spec.md:40`, `specs/001-ai-code-reviewer/spec.md:152-153`), but the only Phase 4 tasks are about status updates and generic `updated_findings` handling (`specs/001-ai-code-reviewer/tasks.md:83-90`). As written, the builder could replace or renumber findings after a rebuttal and still satisfy the current task list. Add an explicit failing test plus implementation task for matching follow-up results back to existing findings and preserving IDs/fingerprints across at least one discussion round.

### Medium
- M-1: FR-008, FR-010, and FR-011 are implemented in the plan but not made testable. T015/T020 create the reviewer prompt and deterministic context ordering (`specs/001-ai-code-reviewer/tasks.md:48`, `specs/001-ai-code-reviewer/tasks.md:68`), yet no test task asserts that the prompt sent to Copilot actually contains the category/evidence instructions or that bundle sections are assembled in the required order from the spec (`specs/001-ai-code-reviewer/spec.md:98-104`). A mocked happy-path `start_review` can pass while sending the wrong prompt. Add a prompt-construction test that inspects the exact payload passed to the Copilot client.
- M-2: Phase 6's container-verification steps contradict each other. T034 excludes `tests/` from the Docker build context (`specs/001-ai-code-reviewer/tasks.md:121`), but T036 later requires the full test suite to run inside the container (`specs/001-ai-code-reviewer/tasks.md:123`). Without a separate test image/stage or an explicit strategy for getting test files into the container, T036 cannot work as written. Pick one approach and encode it in the plan.

### Low
- None

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: untested
- AC-7: fail
- AC-8: untested
- AC-9: untested

### Verification
- Checked: Compared `specs/001-ai-code-reviewer/tasks.md` against `specs/001-ai-code-reviewer/spec.md`, `specs/001-ai-code-reviewer/plan.md`, `specs/001-ai-code-reviewer/contracts/mcp-tools.md`, `specs/001-ai-code-reviewer/contracts/review-engine.md`, and `specs/001-ai-code-reviewer/data-model.md` for requirement coverage, sequencing, and TDD fit.
- Checked external sources: Verified that the Docker dependency assumption in T004 is still current before deciding whether it was a plan defect. GitHub’s current Copilot CLI install docs still require installing `@github/copilot` and state Node.js 22+ is required, so I did not raise T004 as a finding. Sources used: https://docs.github.com/en/copilot/managing-copilot/configure-personal-settings/installing-the-github-copilot-cli and https://docs.github.com/en/copilot/how-tos/use-copilot-agents/copilot-sdk/getting-started
- Corrections: None

### Open Questions
- Should the builder preserve stable findings during `discuss` by reconciling on fingerprint/rule/location, by requiring Copilot to echo existing `finding_id` values, or by combining both? The next round should make that mechanism explicit in the task list.

## Round 2 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The renumbering pass is still internally inconsistent. `T023` is used twice, once for the US1 FastAPI health endpoint and again for the US2 `discuss` tests ([tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md:71), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md:84)). Phase 6 also says to record the Copilot API surface discovered in `T019`, but the build-phase spike actually lives in `T020` after the renumbering ([tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md:68), [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md:123)). Because the plan depends on task IDs for sequencing, MVP scope, and future round responses, duplicate/stale IDs leave the execution plan ambiguous. Reassign unique IDs and fix every cross-reference.
- M-2 (AP-002): The new prompt-construction test locks the plan to an interface that conflicts with the accepted Copilot client contract. T018 says the test should inspect the prompt passed to `CopilotReviewClient.send_review()` and verify that it begins with "system instructions" ([tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md:63)), but the client contract models reviewer persona separately as `create_review_session(system_prompt, ...)` and reserves `send_review(prompt)` for the review payload ([copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md:25), [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md:32)). A contract-compliant implementation could therefore fail the planned test, or the implementation would duplicate persona instructions in two places. Adjust T018 so it validates the correct boundary: `create_review_session()` receives the system prompt, while `send_review()` receives the ordered review context, or explicitly reconcile the contracts first.

### Low
- L-1: Round 2 again omits the required `### Verification` section in `builder.md` and substitutes only an anti-pattern self-check ([builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md:279)). The protocol requires the verification section on every round so the audit trail shows what was checked and whether any corrections were needed. Add it next round even if the entry is just a local consistency check and "no external claims this round."

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: untested
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification
- Checked: Compared the updated [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md), [plan.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/plan.md), [research.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/research.md), [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md), and [review-engine.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/review-engine.md) for task coverage, ID consistency, and contract alignment.
- Checked external sources: None needed. These findings are based on internal document consistency rather than external SDK/tool behavior.
- Corrections: None

### Open Questions
- Should the accepted interface treat reviewer persona as a `create_review_session(system_prompt=...)` concern, a `send_review(prompt=...)` concern, or both? The next round should make the task list match one answer.

## Round 3 — plan

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The task list now matches `copilot-client.md`, but it still conflicts with the accepted review-engine contract. T018 says `create_review_session(system_prompt=...)` carries the reviewer persona and `send_review(prompt=...)` carries only the ordered review context ([tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md:63)), which is consistent with [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md:25) and [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md:32). But [review-engine.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/review-engine.md:30) still says `start_review()` should "format reviewer prompt with persona + ordered context", and its Context Ordering section still defines a single assembled prompt whose first element is "System instructions / reviewer persona" ([review-engine.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/review-engine.md:107)). That leaves the build plan with two incompatible sources of truth for the same boundary. Reconcile the design docs so the plan, engine contract, and client contract all describe the same prompt assembly model.

### Low
- None

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: untested
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification
- Checked: Reviewed the updated [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md), [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md), and [review-engine.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/review-engine.md) for prompt-boundary consistency.
- Checked: Confirmed the task renumbering issue itself is resolved: `tasks.md` now defines 39 unique task IDs with no gaps, and the stale `T019` cross-reference is gone.
- Checked external sources: None needed. This verdict is based on internal document consistency.
- Corrections: None

### Open Questions
- Should `review-engine.md` be updated to treat reviewer persona as session configuration instead of part of the assembled review payload, or does Peter want the design to preserve the "single prompt" model and adjust `copilot-client.md`/T018 instead?

## Round 4 — plan

### Verdict
accepted

### Blockers
- None

### High
- None

### Medium
- None

### Low
- L-1: `tasks.md` still has one stale editorial reference after the `review-engine.md` contract rewrite. T021 says `start_review()` is implemented "per contracts/review-engine.md steps 1-10" ([tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md:69)), but [review-engine.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/review-engine.md:20) now documents 11 steps after splitting persona/session creation from review-context delivery. This does not block the plan, but it is worth cleaning up when the builder next touches `tasks.md`.

### Acceptance Check
- AC-1: untested
- AC-2: untested
- AC-3: untested
- AC-4: untested
- AC-5: untested
- AC-6: untested
- AC-7: untested
- AC-8: untested
- AC-9: untested

### Verification
- Checked: Compared the current [review-engine.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/review-engine.md), [copilot-client.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/copilot-client.md), and [tasks.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/tasks.md) for prompt-boundary consistency. The persona/session split is now aligned across all three.
- Checked: Grepped the feature docs for the old single-prompt wording (`single prompt`, `System instructions / reviewer persona`, `persona + ordered context`) and did not find any remaining prompt-model contradiction.
- Checked external sources: None needed. This verdict is based on internal document consistency.
- Corrections: The substantive Round 3 finding is resolved. I am leaving only the low-risk stale step-count reference above.

### Open Questions
- None

## [test] Archived Rounds

## Round 1 — test

### Verdict
needs_revision

### Blockers
- None

### High
- H-1: `discuss()` still misclassifies terminal Copilot failures as `internal` instead of a terminal classified error. The `start_review()` handler maps auth failures correctly at [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L116), but the `discuss()` handler only special-cases timeout and rate-limit errors at [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L160) and falls through to `{"error": "internal"}` for `CopilotAuthError` / `CopilotUnavailableError`. That contradicts the spec’s mid-conversation terminal-error requirement at [spec.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/spec.md#L73) and FR-013 at [spec.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/spec.md#L109). I reproduced both cases locally: patching `_engine.discuss` to raise `CopilotAuthError("bad token")` or `CopilotUnavailableError("model unavailable")` returned `{"error": "internal", ...}`. The new handler tests only cover the transient `discuss()` cases at [tests/test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_mcp_handlers.py#L218), while the auth mapping test is still only on `start_review()` at [tests/test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_mcp_handlers.py#L128).

### Medium
- M-1: The zero-findings edge case is still neither implemented nor actually covered by the new test suite. The spec says a review with no findings is a valid outcome and the session is marked `resolved` at [spec.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/spec.md#L74), but `start_review()` still creates every session with `SessionStatus.ACTIVE` at [review_engine.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/review_engine.py#L144). I reproduced this by forcing the parser to return `[]`; the stored session, `get_review_summary()`, and `list_sessions()` all reported `active`. The builder’s test-round write-up says this edge case is covered at [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L1030), but the cited handler success test only checks a mocked `finding_count == 0` response shape at [tests/test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_mcp_handlers.py#L241) and does not exercise `start_review()` or assert `resolved` session metadata. This leaves the AC-4 metadata path incorrect for zero-finding sessions.

### Low
- None

### Acceptance Check
- AC-1: pass
- AC-2: pass
- AC-3: pass
- AC-4: fail
- AC-5: pass
- AC-6: pass
- AC-7: pass
- AC-8: pass
- AC-9: pass

### Verification
- Checked: Ran host tests with coverage via `.venv/bin/python -m pytest --cov=server --cov-report=term-missing -q`; result was `149 passed in 0.67s` with `TOTAL 715 stmts, 68 missed, 90%`, matching the builder report.
- Checked: Ran in-container parity via `docker compose exec -T review-server python -m pytest tests/ -q`; result was `149 passed in 0.33s`.
- Checked: Revalidated MCP stdio startup in the running container. `initialize` returned a valid JSON-RPC result for `review-server` with protocol version `2024-11-05`.
- Checked: Reproduced H-1 locally by patching `server.mcp_server._engine.discuss` to raise `CopilotAuthError("bad token")` and `CopilotUnavailableError("model unavailable")`; both returned `{"error": "internal", "retryable": false}`.
- Checked: Reproduced M-1 locally by forcing `ReviewEngine._parser.parse` to return `[]`; the stored session, summary, and listed session all stayed `active` instead of `resolved`.
- Corrections: The previously accepted build-phase Docker and MCP bootstrap claims still hold. The remaining failures are test-phase runtime/spec mismatches that the new test suite did not catch.

### Open Questions
- None

## Round 2 — test

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1: The runtime fixes are in place, but the public MCP contract is now out of sync with the implementation and tests. [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L121) and [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L167) now return `{"error": "unavailable", ...}` for `CopilotUnavailableError`, and the new handler tests require that behavior at [tests/test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_mcp_handlers.py#L160) and [tests/test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_mcp_handlers.py#L261). But the accepted MCP tool contract still does not define `unavailable` for either `start_review` or `discuss` at [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md#L41) and [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md#L79). That changes the public interface after design/build acceptance without updating the source-of-truth contract. Either update the contract/docs to explicitly include the new terminal error code for both tools, or map model unavailability back onto the already-documented error surface.

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
- Checked: Ran host tests via `.venv/bin/python -m pytest -q`; result was `154 passed in 0.41s`.
- Checked: Ran host coverage via `.venv/bin/python -m pytest --cov=server --cov-report=term-missing -q`; result was `154 passed in 0.67s` with `TOTAL 724 stmts, 68 missed, 91%`, matching the builder report.
- Checked: Ran in-container parity via `docker compose exec -T review-server python -m pytest tests/ -q`; result was `154 passed in 0.38s`.
- Checked: Reproduced the previous round’s two failures locally. `discuss()` now returns `auth_failed` for `CopilotAuthError` and `unavailable` for `CopilotUnavailableError`; a `start_review()` response of `"[]"` now yields a `resolved` session in the store, summary, and session listing.
- Checked: Compared the updated handler/tests against [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md) and confirmed the new `unavailable` error code is not documented there.
- Corrections: My previous Round 1 findings H-1 and M-1 are resolved.

### Open Questions
- Should `CopilotUnavailableError` be a distinct public MCP error (`unavailable`) or should the implementation stay within the currently documented error surface? The next round should make code, tests, and `mcp-tools.md` all match one answer.

## Round 3 — test

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): Round 3 still leaves the MCP contract incomplete relative to the implemented handler surface. The builder says `mcp-tools.md` now documents "all error codes that exist in the implementation" and that the contract gap is resolved ([builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L74), [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L105)), but `start_review()` and `discuss()` still emit undocumented `unknown` / `internal` payloads ([mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L115), [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L127), [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L161), [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L173)), and `get_review_summary()` emits undocumented `session_not_found` / `unknown` errors while [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md#L94) has no error section for that tool. The handler tests also lock in part of that undocumented surface: `start_review()` still asserts `internal` on unexpected failures ([test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_mcp_handlers.py#L171)) and `get_review_summary()` asserts `session_not_found` ([test_mcp_handlers.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/tests/test_mcp_handlers.py#L294)). Because `mcp-tools.md` is the public source of truth for the MCP API, clients still cannot tell which non-success payloads are actually supported. Either document the full error surface for each tool or remove the undocumented responses.

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
- Checked: Reran the host suite with `.venv/bin/python -m pytest -q` and confirmed `154 passed in 0.38s`.
- Checked: Reran the handler-focused suite with `.venv/bin/python -m pytest tests/test_mcp_handlers.py -q` and confirmed `21 passed in 0.24s`.
- Checked: Compared [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md) against the actual handler returns in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py) and the builder’s Round 3 claims in [builder.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/agent-loop/001-ai-code-reviewer/builder.md#L74).
- Checked external sources: None needed. This is an internal contract / implementation consistency issue only.
- Corrections: My previous Round 2 finding about the missing `unavailable` contract entry is resolved. The remaining issue is the broader undocumented error surface above.

### Open Questions
- None

## Round 4 — test

### Verdict
needs_revision

### Blockers
- None

### High
- None

### Medium
- M-1 (AP-002): The contract still does not match the actual `internal` error payload. [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md#L53) and [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md#L94) document `internal` as always `{"retryable": false}`, but the handlers preserve `getattr(e, "retryable", False)` in the `internal` fallback at [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L117), [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L127), [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L163), and [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py#L173). I reproduced this in the venv by patching the engine to raise a custom `RuntimeError` subclass with `retryable = True`; both `start_review()` and `discuss()` returned `{"error": "internal", "message": "boom", "retryable": true}`. So clients still cannot rely on the contract to interpret the full error surface. Either document `internal.retryable` as variable, or normalize the handlers to always return `false` for `internal`.

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
- Checked: Reran the handler-focused suite with `.venv/bin/python -m pytest tests/test_mcp_handlers.py -q` and confirmed `21 passed in 0.22s`.
- Checked: Compared the current `internal` contract entries in [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md) against the fallback behavior in [mcp_server.py](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/server/mcp_server.py).
- Checked: Reproduced the mismatch locally in `.venv` with a custom exception carrying `retryable = True`; both `start_review()` and `discuss()` returned `internal` with `retryable: True`.
- Checked external sources: None needed. This is an internal code/contract consistency issue only.
- Corrections: My previous Round 3 finding is largely resolved: `unknown`, `internal`, and `get_review_summary` errors are now documented. The remaining mismatch is the `internal.retryable` field value above.

### Open Questions
- None

## Round 5 — test

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
- Checked: Re-read the updated `internal` contract entries in [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md#L53) and [mcp-tools.md](/Users/Peter_Petroczy/Documents/Projects/AgentInaDocker/specs/001-ai-code-reviewer/contracts/mcp-tools.md#L94). They now describe `retryable` as variable and explain that it reflects the original exception flag.
- Checked: Reproduced the judge’s prior edge case in `.venv` with a custom exception carrying `retryable = True`; `start_review()` and `discuss()` still return `{"error": "internal", "message": "boom", "retryable": true}`, which now matches the contract.
- Checked: Reran the handler-focused suite with `.venv/bin/python -m pytest tests/test_mcp_handlers.py -q` and confirmed `21 passed in 0.18s`.
- Checked external sources: None needed. This verdict is based on local contract/code review and runtime verification only.
- Corrections: My previous Round 4 finding about the `internal.retryable` mismatch is resolved. I do not see any remaining test-phase contract drift in the MCP handler surface.

### Open Questions
- None
