# Feature Specification: AgentinaBox — Core Review Server

**Feature Branch**: `001-ai-code-reviewer`
**Created**: 2026-03-13
**Status**: Draft
**Input**: User description: "Build the MVP Dockerized AI code review server: MCP tools + Copilot SDK integration + Docker container. Code in, findings out."

## Product Positioning

AgentinaBox is an **advisory** code review tool. It produces findings and enables multi-turn discussion, but it does NOT:

- Block merges or emit CI status checks
- Replace human approval or required reviews
- Count toward branch protection requirements

Human approval (spec 004) is **non-governing with respect to GitHub merge controls** — it does not emit status checks or affect branch protection. However, approval is **operational within AgentinaBox**: it transitions the session to `approved` (terminal state), after which further `discuss` calls are rejected. This distinction matters: the tool does not gate your CI, but it does enforce its own session lifecycle. This is aligned with GitHub's own Copilot code review, which is also advisory-only with respect to merge governance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit Code for Review (Priority: P1)

A developer using Claude Code finishes implementing a feature. Claude Code automatically gathers the diff, changed files, test files, spec artifacts, project rules, and test results into a review bundle. It calls the `start_review` MCP tool on the review server. The server validates the bundle against the content denylist, orders the context deterministically, and forwards it to GitHub Copilot via the Copilot SDK. Copilot returns structured findings classified by severity and review dimension, each with a stable ID and fingerprint for tracking across discussion rounds.

**Why this priority**: This is the core value proposition — without the ability to submit code and receive review findings, nothing else works. This story alone delivers a working MVP: code goes in, review findings come out.

**Independent Test**: Can be fully tested by calling `start_review` with a sample diff and verifying that findings are returned with SARIF-structured fields including `finding_id`, severity, category, file, line, and fingerprint.

**Acceptance Scenarios**:

1. **Given** the review server is running in Docker with valid Copilot credentials (via `GITHUB_TOKEN` env var), **When** Claude Code calls `start_review` with a diff, changed files, and project rules, **Then** the server returns a session ID and a list of SARIF-structured findings.
2. **Given** the review server is running but Copilot credentials are invalid, **When** Claude Code calls `start_review`, **Then** the server returns a clear error classifying the failure as terminal (not retryable).
3. **Given** the review server is running, **When** Claude Code calls `start_review` with an empty diff, **Then** the server returns a response indicating no changes to review.
4. **Given** the review bundle contains a file matching the content denylist (e.g., `.env`), **When** Claude Code calls `start_review`, **Then** the server rejects the bundle with an error listing the denied files, before forwarding anything to Copilot.
5. **Given** Claude Code calls `start_review` twice with the same idempotency token, **When** both calls reach the server, **Then** the second call returns the same session and findings as the first (no duplicate session created).

---

### User Story 2 - Multi-Turn Review Discussion (Priority: P2)

After receiving initial findings, Claude Code disagrees with some and wants to discuss them. It calls the `discuss` MCP tool with a rebuttal message and optionally attaches additional files the reviewer requested. Copilot responds, either accepting the rebuttal or standing firm. Findings maintain stable IDs and fingerprints across rounds so both sides can reference the same issue unambiguously. Claude Code then calls `get_review_summary` for a final report.

**Why this priority**: Multi-turn discussion is what distinguishes this from a one-shot linter. It enables the reviewer to be convinced by good arguments and lets Claude Code defend its design choices — producing higher-quality outcomes than a static checklist.

**Independent Test**: Can be tested by starting a review session, then calling `discuss` with a rebuttal to one finding (referenced by `finding_id`), verifying the response addresses that specific finding, and calling `get_review_summary` to confirm the finding status changed.

**Acceptance Scenarios**:

1. **Given** an active review session with 3 findings, **When** Claude Code calls `discuss` with a rebuttal referencing finding `F-002` by ID, **Then** Copilot responds addressing that specific finding (accepting or rejecting the rebuttal), and the finding's status is updated.
2. **Given** an active review session, **When** Claude Code calls `discuss` with additional files attached, **Then** the server validates the files against the content denylist before forwarding to Copilot.
3. **Given** an active review session where all findings are resolved, **When** Claude Code calls `get_review_summary`, **Then** the server returns a summary with finding counts by status, category, and severity.
4. **Given** a `discuss` call fails due to a transient error, **When** Claude Code retries with the same idempotency token, **Then** the retry is processed correctly without creating duplicate messages.

---

### User Story 3 - List Active Sessions (Priority: P3)

Claude Code wants to check whether there are any active review sessions (e.g., to resume one or to avoid starting a duplicate). It calls the `list_sessions` MCP tool, which returns all sessions with their status, branch name, and finding counts.

**Why this priority**: Session management is essential for multi-review workflows but not needed for a single review to complete.

**Independent Test**: Can be tested by creating two review sessions, then calling `list_sessions` and verifying both appear with correct metadata.

**Acceptance Scenarios**:

1. **Given** two review sessions exist (one active, one resolved), **When** Claude Code calls `list_sessions`, **Then** both sessions are returned with their ID, status, branch name, round count, and finding counts by severity and category.
2. **Given** no review sessions exist, **When** Claude Code calls `list_sessions`, **Then** an empty list is returned.

---

### Edge Cases

- What happens when the Copilot SDK returns a transient error mid-conversation (rate limit, timeout)? → Classified as retryable; Claude Code can retry with same idempotency token.
- What happens when the Copilot SDK returns a terminal error (model unavailable, auth revoked)? → Classified as terminal; finding status set to error with clear message.
- How does the system handle a review session where Copilot returns no findings at all? → Valid outcome; session is marked resolved with zero findings.
- What happens when Claude Code sends a diff that exceeds Copilot's token limit? → Fail fast with bundle size, model limit, and reduction guidance (FR-010).
- How does the system behave if the Docker container is restarted during an active review session? → Sessions are lost (ephemeral MVP). Claude Code can start a new review.
- How does the system handle concurrent review sessions? → Each session is independent; no shared state between sessions.

## Requirements *(mandatory)*

### Functional Requirements

#### MCP Interface

- **FR-001**: System MUST expose MCP tools (`start_review`, `discuss`, `get_review_summary`, `list_sessions`) accessible via stdio transport
- **FR-002**: System MUST accept a structured review bundle containing diff, changed files, test files, spec artifacts, project rules, anti-patterns, test results, and free-form context
- **FR-003**: System MUST forward the review bundle to GitHub Copilot via the Copilot SDK and return SARIF-structured findings (see Finding entity below)
- **FR-004**: System MUST support multi-turn discussion where the calling agent can rebut findings (referenced by `finding_id`) and attach additional files
- **FR-005**: This tool is **advisory only**. It MUST NOT emit CI status checks, block merges, or count toward branch protection requirements

#### Content Safety

- **FR-006**: System MUST validate all incoming review bundles against a configurable content denylist before forwarding to Copilot. Default denylist patterns: `.env`, `*.pem`, `*.key`, `*credentials*`, `*secret*`, `*.p12`, `*.pfx`. Denied files MUST cause the request to be rejected with a clear error listing the denied files.
- **FR-007**: System MUST validate files attached in `discuss` calls against the same content denylist

#### Bundle Handling

- **FR-008**: System MUST order the review context deterministically before sending to the model: (1) system instructions / reviewer persona, (2) project rules and anti-patterns, (3) spec artifacts, (4) git diff, (5) changed file contents, (6) test files, (7) test results, (8) free-form context
- **FR-009**: System MUST fail fast with a clear error when the review bundle exceeds the model's context window. The error MUST include the bundle size (in tokens or characters), the model's limit, and a recommendation for Claude Code to reduce the bundle. The system MUST NOT silently truncate, chunk, or drop content.

#### Review Quality

- **FR-010**: System MUST instruct the reviewer to classify each finding by review dimension: correctness, design, tests, maintainability, security, or style. This classification MUST appear in the finding's `category` field.
- **FR-011**: System MUST require the reviewer to ground non-trivial findings (BUG, WARN) in evidence — quoting or referencing the specific code that triggers the finding

#### Reliability

- **FR-012**: `start_review` and `discuss` MUST accept an optional client-generated `idempotency_token`. Repeated calls with the same token MUST return the same result without creating duplicate sessions or messages.
- **FR-013**: System MUST classify errors as either `retryable` (transient: rate limit, timeout, network) or `terminal` (auth failure, invalid request, model unavailable). The error response MUST include this classification.
- **FR-014**: System MUST enforce configurable timeout budgets on Copilot SDK calls. Defaults: 120 seconds for `start_review` (configurable via `REVIEW_TIMEOUT` env var), 60 seconds for `discuss` (configurable via `DISCUSS_TIMEOUT` env var). Env vars are resolved in the composition root and passed as constructor arguments; direct callers (e.g., tests) bypass env var parsing. On timeout, return a retryable error.

#### Infrastructure

- **FR-015**: System MUST maintain review session state in memory for the duration of a session. Sessions are ephemeral — all state is lost on container restart. Persistent storage is deferred to spec 003.
- **FR-016**: System MUST accept Copilot credentials via the `GITHUB_TOKEN` environment variable (fine-grained PAT with `copilot_requests` permission)
- **FR-017**: System MUST run entirely within a single Docker container started with a single compose command
- **FR-018**: System MUST provide a health check endpoint for Docker monitoring
- **FR-019**: System MUST auto-select the best available model via `list_models()` at startup

### Key Entities

- **Review Session**: Represents a single code review conversation. Has a unique ID, branch name, status, creation time, associated model, and token/request accounting metadata. Contains an ordered list of messages and findings. Status values across the full spec set are: `active` (review in progress), `resolved` (agents consider all findings addressed), `round_requested` (human requested further discussion — spec 004), `approved` (human signed off — spec 004, terminal state). The MVP (this spec) uses only `active` and `resolved`; later specs extend the state machine.

- **Message**: A single exchange in a review session. Has a sender (system/claude/copilot), content, timestamp, optional attached files, and an idempotency token for deduplication.

- **Finding** (SARIF-inspired): A specific issue identified during review, structured for stable tracking across discussion rounds and cross-run comparison.

  | Field | Description |
  |-------|-------------|
  | `finding_id` | Unique ID within the session (e.g., `F-001`). Stable across discussion rounds. |
  | `rule_id` | Identifies the class of issue (e.g., `race-condition`, `missing-error-handling`, `naming-convention`). Reusable across reviews. |
  | `severity` | `BUG` (likely defect), `WARN` (potential issue), `NIT` (suggestion/style) |
  | `category` | Review dimension: `correctness`, `design`, `tests`, `maintainability`, `security`, `style` |
  | `message` | Human-readable description of the issue |
  | `primary_location` | `{ file, start_line, end_line }` — where the issue occurs |
  | `related_locations` | Array of additional locations relevant to the finding (e.g., the other side of a race condition) |
  | `fingerprint` | Hash of `rule_id` + normalized code at `primary_location`. Used to match the "same" finding across rounds and runs. |
  | `confidence` | `high`, `medium`, `low` — how certain the reviewer is |
  | `evidence` | Quote from the code or explanation grounding the finding |
  | `status` | `open`, `accepted`, `dismissed`, `fixed` |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Claude Code can call `start_review` and receive SARIF-structured findings within 30 seconds (network latency permitting)
- **SC-002**: Multi-turn discussion rounds via `discuss` complete within 15 seconds per round
- **SC-003**: The system handles review bundles containing up to 50 changed files without failure
- **SC-004**: The Docker image can be built and started with `docker compose up -d` plus a `GITHUB_TOKEN` env var — nothing else required
- **SC-005**: Claude Code can connect to the review server via `docker exec -i <container> python -m server.mcp_server`
- **SC-006**: Content denylist blocks `.env` and credential files before they reach Copilot — verified by test
- **SC-007**: Duplicate `start_review` calls with the same idempotency token return the same session — verified by test
- **SC-008**: Findings maintain stable `finding_id` and `fingerprint` across discussion rounds — verified by test
