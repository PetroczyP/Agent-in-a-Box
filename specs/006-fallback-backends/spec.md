# Feature Specification: AgentinaBox — Fallback Model Backends

**Feature Branch**: `006-fallback-backends`
**Created**: 2026-03-13
**Status**: Draft
**Depends on**: 001-ai-code-reviewer

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use OpenAI as Review Backend (Priority: P1)

A developer finds the Copilot SDK too unstable (it is Technical Preview) or does not have a Copilot subscription. They configure the review server to use the OpenAI API instead. They provide an OpenAI API key, and the server routes review requests to an OpenAI model. The MCP interface to Claude Code remains identical — Claude Code does not know or care what model is answering inside the container.

**Why this priority**: OpenAI is the most mature alternative API. Supporting it first gives the widest safety net if Copilot SDK has issues.

**Independent Test**: Can be tested by configuring the server with an OpenAI API key and no Copilot credentials, starting a review via MCP, and verifying findings are returned.

**Acceptance Scenarios**:

1. **Given** the server is configured with an OpenAI API key and no Copilot credentials, **When** Claude Code calls `start_review`, **Then** the review is processed by the OpenAI model and findings are returned in the same format as Copilot reviews.
2. **Given** the server is configured with both Copilot and OpenAI credentials, **When** the Copilot SDK fails during a review, **Then** the server does NOT automatically fall back (backends are explicitly configured, not auto-detected).
3. **Given** an OpenAI-backed review, **When** Claude Code calls `discuss`, **Then** multi-turn discussion works identically to Copilot-backed reviews.

---

### User Story 2 - Use Anthropic API as Review Backend (Priority: P2)

A developer prefers using the Anthropic API (Claude models) as the inner reviewer. This creates an interesting dynamic: Claude Code (the orchestrator) sends code to Claude (the reviewer) for an independent second opinion. The value comes from the different system prompts and review-specific persona.

**Why this priority**: Anthropic API is production-stable and gives access to strong reasoning models.

**Independent Test**: Can be tested by configuring with an Anthropic API key, starting a review, and verifying findings arrive.

**Acceptance Scenarios**:

1. **Given** the server is configured with an Anthropic API key, **When** Claude Code calls `start_review`, **Then** the review is processed by the configured Claude model and findings are returned in standard format.

---

### User Story 3 - Use Local Models via Ollama (Priority: P3)

A developer wants fully offline, private code reviews using a locally running model via Ollama. They configure the server to point at an Ollama endpoint. Review quality may be lower, but no code leaves the local machine.

**Why this priority**: Ollama support is niche but important for air-gapped environments and privacy-sensitive codebases.

**Independent Test**: Can be tested by running Ollama locally, configuring the server to use it, and verifying a review completes (quality aside).

**Acceptance Scenarios**:

1. **Given** Ollama is running locally and the server is configured to use it, **When** Claude Code calls `start_review`, **Then** the review is processed locally and findings are returned.
2. **Given** the configured Ollama endpoint is unreachable, **When** Claude Code calls `start_review`, **Then** the server returns a clear error.

---

### Edge Cases

- What happens if a backend API key is invalid or expired?
- How does the system handle different response formats from different backends?
- Can the backend be switched between reviews without restarting the container?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support a pluggable backend interface so that review requests can be routed to any supported model API
- **FR-002**: System MUST support these backends: Copilot SDK (existing), OpenAI API, Anthropic API, Gemini API, and Ollama
- **FR-003**: System MUST use the same MCP tool interface regardless of which backend is active — Claude Code MUST NOT need to change its behavior
- **FR-004**: System MUST allow backend selection via configuration (not auto-detection)
- **FR-005**: System MUST validate backend credentials on startup and report clear errors for misconfiguration
- **FR-006**: Each backend MUST format its output into the same Finding structure (severity, file, line, description)

### Key Entities

- **Backend**: Represents a model API provider. Has a type (copilot/openai/anthropic/gemini/ollama), endpoint URL, credentials, and status (active/error).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adding a new backend requires implementing one interface — no changes to MCP tools, session management, or web UI
- **SC-002**: Reviews from all backends produce identically structured findings
- **SC-003**: Switching backends requires only a config change and container restart — no code changes
- **SC-004**: Each backend validates its credentials on startup and surfaces clear errors within 5 seconds
