# Feature Specification: AgentinaBox — Review Dashboard

**Feature Branch**: `003-review-dashboard`
**Created**: 2026-03-13
**Status**: Draft
**Depends on**: 001-ai-code-reviewer

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Session List (Priority: P1)

A human developer opens `localhost:8080` and sees a list of all review sessions — active and resolved. Each row shows the session ID, branch name, number of discussion rounds, status, finding counts, and how long ago it started. The list updates automatically.

**Why this priority**: The session list is the entry point to all monitoring. Without it, the user cannot navigate to any transcript.

**Independent Test**: Can be tested by creating two review sessions via MCP, then opening `localhost:8080` and verifying both appear with correct metadata.

**Acceptance Scenarios**:

1. **Given** one or more review sessions exist, **When** a user opens `localhost:8080`, **Then** a session list is displayed showing session ID, branch name, round count, status, finding counts, and age.
2. **Given** no review sessions exist, **When** a user opens `localhost:8080`, **Then** a friendly empty state is shown with a brief explanation.
3. **Given** a new session is created via MCP while the page is open, **When** the page auto-refreshes, **Then** the new session appears in the list.

---

### User Story 2 - View Review Transcript (Priority: P2)

A developer clicks on a session in the list and sees the full conversation transcript. Each message shows the sender (Claude or Copilot), timestamp, and content. Findings are color-coded by severity. The transcript updates in near real-time as the review progresses.

**Why this priority**: The transcript is the core monitoring artifact — it provides visibility into the agent-to-agent discussion.

**Independent Test**: Can be tested by starting a review session, sending a few discussion rounds via MCP, and verifying the transcript displays all messages in order with correct metadata.

**Acceptance Scenarios**:

1. **Given** an active review session, **When** a user clicks on that session, **Then** the full transcript is displayed with messages labeled by sender (Claude/Copilot) and timestamps.
2. **Given** an active review session with ongoing discussion, **When** a user is viewing the transcript, **Then** new messages appear within a few seconds without manual page refresh.
3. **Given** findings in the transcript, **When** displayed, **Then** BUG findings are visually distinct from WARN and NIT findings.

---

### User Story 3 - View Raw JSON (Priority: P3)

A developer wants to see the raw data behind a review session for debugging or analysis. They click a "Raw JSON" toggle on the transcript page and see the full session data in JSON format.

**Why this priority**: Useful for debugging and transparency, but not needed for day-to-day monitoring.

**Independent Test**: Can be tested by opening a session transcript and toggling the Raw JSON view, verifying it shows valid JSON matching the session data.

**Acceptance Scenarios**:

1. **Given** a review session transcript is displayed, **When** a user clicks "Raw JSON", **Then** a collapsible section expands showing the full session data as formatted JSON.
2. **Given** the Raw JSON section is expanded, **When** the user clicks it again, **Then** it collapses.

---

### Edge Cases

- How does the dashboard behave if there are 100+ sessions?
- What happens if the user views a transcript for a session that is deleted or corrupted?
- How does the live update behave on slow or intermittent connections?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a session list page at `localhost:8080` with auto-refresh
- **FR-002**: System MUST provide a per-session transcript page showing all messages chronologically
- **FR-003**: System MUST visually distinguish finding severities (BUG/WARN/NIT) in the transcript
- **FR-004**: System MUST update the transcript view in near real-time (within 5 seconds) without manual refresh
- **FR-005**: System MUST provide a collapsible Raw JSON view on the transcript page
- **FR-006**: System MUST render using server-side templates (no JavaScript framework required)
- **FR-007**: System MUST use a monospace font and dark theme for log-viewer aesthetic
- **FR-008**: System MUST persist completed sessions to durable storage (Docker volume) so they survive container restarts. Active sessions in progress may remain in-memory only

### Key Entities

No new entities — this feature reads Review Session, Message, and Finding entities defined in 001.

**Persistence note**: Spec 001 stores sessions in memory only (ephemeral). This spec introduces lightweight persistence (SQLite in the Docker volume) so that resolved sessions survive container restarts and the dashboard can show historical sessions. This is a prerequisite for the export and compliance use cases in spec 004.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The session list loads within 1 second for up to 100 sessions
- **SC-002**: The transcript page updates within 5 seconds of a new message being exchanged
- **SC-003**: The dashboard is usable without any JavaScript enabled (except live updates)
- **SC-004**: A developer unfamiliar with the system can understand the review status within 10 seconds of opening the dashboard
