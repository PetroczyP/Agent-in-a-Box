# Feature Specification: AgentinaBox — Model Configuration

**Feature Branch**: `005-model-configuration`
**Created**: 2026-03-13
**Status**: Draft
**Depends on**: 002-credential-setup

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose a Review Model via Settings (Priority: P1)

A developer opens the Settings page on `localhost:8080` and sees a list of AI models available under their Copilot subscription (fetched live). They select their preferred model for code reviews. The selection is persisted and used for all subsequent reviews unless overridden.

**Why this priority**: Model selection is the primary feature of this spec — letting users pick the reviewer's brain.

**Independent Test**: Can be tested by opening Settings, selecting a model, starting a review, and verifying the selected model was used.

**Acceptance Scenarios**:

1. **Given** valid credentials are configured, **When** a user opens the Settings page, **Then** a list of available models is displayed (fetched live from the Copilot subscription via `list_models()`).
2. **Given** a user selects a model and clicks "Save", **Then** the selection is persisted and used for all subsequent reviews.
3. **Given** no model is selected (default), **Then** the system auto-selects the best available model using a preference order.

---

### User Story 2 - Per-Review Model Override (Priority: P2)

Claude Code wants to use a specific model for a particular review (e.g., a more capable model for a complex change). It passes an optional `model` parameter in the `start_review` MCP call. The specified model is used for this review only, without changing the server's default.

**Why this priority**: Per-review override is a power-user feature that adds flexibility without affecting the default behavior.

**Independent Test**: Can be tested by setting a default model in Settings, then starting a review with a different model override, and verifying the override was used.

**Acceptance Scenarios**:

1. **Given** a default model is configured in Settings, **When** Claude Code passes `model: "some-model-id"` in `start_review`, **Then** the specified model is used for this review only.
2. **Given** a per-review model override is used, **When** the next review is started without an override, **Then** the server's default model is used.
3. **Given** Claude Code passes a model ID that is not available, **When** `start_review` is called, **Then** the server returns an error listing available models.

---

### Edge Cases

- What happens when `list_models()` returns an empty list?
- What happens when the configured default model is retired or becomes unavailable?
- How does the system handle model availability changes between subscription downgrades?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST discover available models at runtime via `list_models()` — no hardcoded model IDs that fail on retirement
- **FR-002**: System MUST provide a Settings page showing live-fetched available models with a selection interface
- **FR-003**: System MUST persist the selected model in the Docker volume configuration file
- **FR-004**: System MUST allow per-review model override via the `start_review` MCP tool parameter
- **FR-005**: System MUST fall back gracefully if the configured model becomes unavailable (auto-select next best)
- **FR-006**: System MUST display which model was used in each review session's metadata

### Key Entities

- **Server Config**: Extended with selected model ID, custom preference order, and last-fetched model list timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The Settings page displays the available model list within 3 seconds of opening
- **SC-002**: Model selection persists across container restarts
- **SC-003**: Per-review override works without requiring any server configuration change
- **SC-004**: The system never fails a review because a retired model is hardcoded — it falls back automatically
