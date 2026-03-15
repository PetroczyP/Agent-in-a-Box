# Feature Specification: AgentinaBox — Human Oversight

**Feature Branch**: `004-human-oversight`
**Created**: 2026-03-13
**Status**: Draft
**Depends on**: 003-review-dashboard

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Approve or Close a Review (Priority: P1)

A human developer has been monitoring a review session. The agents have finished discussing. The developer clicks "Approve & Close" to mark the review as approved, or "Request Another Round" to send the agents back for further discussion. This gives humans the final say on whether a review is truly complete.

**Why this priority**: Human approval is the primary oversight mechanism — the core reason this dashboard exists beyond passive monitoring.

**Independent Test**: Can be tested by completing a review discussion, then clicking "Approve & Close" from the web UI and verifying the session status changes and no further MCP discussion calls are accepted.

**Acceptance Scenarios**:

1. **Given** an active review session with all findings resolved, **When** a human clicks "Approve & Close", **Then** the session status changes to "approved" and subsequent `discuss` calls return an error indicating the session is closed.
2. **Given** an active review session, **When** a human clicks "Request Another Round", **Then** the session status changes to "round_requested", a system message is added to the transcript with the human's reason, and subsequent `get_review_summary` and `list_sessions` calls expose this status so Claude Code can detect the request and act on it.
3. **Given** a resolved (approved) session, **When** viewed in the session list, **Then** it is visually marked as approved and the action buttons are disabled.

---

### User Story 2 - Export Review Session (Priority: P2)

A developer wants to save a review transcript for post-mortem analysis, compliance, or team sharing. They click "Export" on a session and download a JSON file containing the full session data: all messages, findings, statuses, and metadata.

**Why this priority**: Export is important for archival and team communication but not required for the review workflow itself.

**Independent Test**: Can be tested by completing a review session, clicking "Export", and verifying the downloaded JSON file contains all session data.

**Acceptance Scenarios**:

1. **Given** a review session (active or resolved), **When** a user clicks "Export", **Then** a JSON file is downloaded containing the full session data.
2. **Given** an exported JSON file, **When** inspected, **Then** it contains all messages, findings with statuses, session metadata, and timestamps.
3. **Given** a session with credentials mentioned in error messages, **When** exported, **Then** no credential material appears in the export.

---

### Edge Cases

- What happens if a human approves a session while Claude Code is mid-discussion?
- Can a human re-open an approved session?
- What happens if two humans try to approve the same session simultaneously?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide "Approve & Close" and "Request Another Round" buttons on active session transcript pages
- **FR-002**: System MUST prevent further MCP `discuss` calls on sessions that have been approved and closed
- **FR-003**: System MUST provide a JSON export endpoint for any session (`/api/sessions/{id}/export`). The default export MUST include session metadata, messages (sender, content, timestamps), and findings (all SARIF fields including status). The default export MUST NOT include raw file bodies or attached file contents from the review bundle. A separate opt-in parameter (`?include_attachments=true`) MAY be supported to include attached file contents when explicitly requested
- **FR-004**: System MUST strip any credential material from exported session data. This includes tokens, keys, and any secret-like values that may appear in error messages or system messages
- **FR-005**: System MUST record human actions (approve, request round) in the session transcript as system messages
- **FR-006**: When a human requests another round, the system MUST transition the session to `round_requested` status. This status MUST be visible to Claude Code via `list_sessions` and `get_review_summary` MCP tools, enabling Claude Code to detect the request on its next MCP status check, without introducing separate callback/webhook channels.
- **FR-007**: The system MUST allow a human to provide an optional reason/instruction when requesting another round (e.g., "Look more carefully at the error handling in api.js"). This reason MUST be included in the system message and visible to Claude Code in the next `get_review_summary` response.

### Key Entities

Extends Review Session with additional status values and the following state machine:

```
active → resolved (all findings addressed by agents)
active → approved (human approves directly)
resolved → approved (human confirms resolution)
resolved → round_requested (human wants more discussion)
round_requested → active (Claude Code resumes discussion)
approved → (terminal — no further transitions)
```

Note: "resolved" means the agents consider all findings addressed. "approved" means a human has signed off. These are distinct — a session can be resolved without human approval.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A human can approve or request another round within 2 clicks from the transcript page
- **SC-002**: Export produces a valid, complete JSON file within 2 seconds for sessions with up to 50 messages
- **SC-003**: No credential material appears in any exported session data
