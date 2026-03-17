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

### User Story 4 - Review Quality Signals (Priority: P2)

A team lead opens the dashboard and sees a "Review Quality" panel showing runtime health metrics: parser success rate, average findings per review, severity distribution, and dimension coverage. This tells them at a glance whether the reviewer is producing useful output or mostly falling back to unparseable NIT-wrap responses. No eval suite or golden cases are involved — these metrics are computed automatically from the real reviews happening on this instance.

**Why this priority**: Without quality visibility, users have no way to know if the reviewer is working well or silently degrading. This is the deployed user's equivalent of the developer eval harness (spec 007).

**Independent Test**: Can be tested by running 5+ reviews via MCP, then opening the dashboard and verifying the quality panel shows accurate aggregate metrics matching the actual review results.

**Acceptance Scenarios**:

1. **Given** 5+ completed review sessions, **When** a user views the dashboard, **Then** a "Review Quality" panel displays: parser success rate (% of reviews that returned structured JSON), average findings per review, severity breakdown (BUG/WARN/NIT counts), and category distribution across the 6 review dimensions.
2. **Given** a review where the parser fell back to NIT-wrap, **When** the quality panel is viewed, **Then** the parser success rate reflects the fallback and the session is flagged as "degraded parse."
3. **Given** reviews are only producing findings in 1-2 categories (e.g., always "style"), **When** the quality panel is viewed, **Then** a "dimension coverage" indicator shows which review dimensions are under-represented.

---

### User Story 5 - Finding Feedback (Priority: P3)

A developer is reading a review transcript and sees a finding that is clearly wrong (false positive) or notices the reviewer missed an obvious issue. They click a feedback button on the finding (thumbs down for bad findings, or "Report Missed Issue" for gaps). The feedback is logged with the session context (diff, findings, user's note) so the AgentinaBox maintainers can harvest it as a golden case candidate for the eval suite (spec 007).

**Why this priority**: This is the feedback loop that makes the product better over time. Without it, quality improvements depend on users filing detailed GitHub issues — which most won't do. A low-friction in-dashboard mechanism captures signal that would otherwise be lost.

**Independent Test**: Can be tested by viewing a finding in a transcript, clicking "Report Issue", entering a note, and verifying the feedback is stored and retrievable via the API.

**Acceptance Scenarios**:

1. **Given** a finding displayed in the transcript, **When** a user clicks the feedback button (thumbs down), **Then** a minimal form appears asking for an optional note (e.g., "this is intentional, not a bug").
2. **Given** a transcript with no finding for a known issue, **When** a user clicks "Report Missed Issue", **Then** a form appears asking: what was missed, where in the code, and an optional severity estimate.
3. **Given** feedback has been submitted, **When** the feedback is stored, **Then** it includes: the session ID, finding ID (if applicable), the review bundle (diff + files), the user's note, and a timestamp.
4. **Given** feedback exists, **When** an admin views the feedback log (API or dashboard page), **Then** all feedback entries are listed with enough context to create a golden test case.

---

### Edge Cases

- How does the dashboard behave if there are 100+ sessions?
- What happens if the user views a transcript for a session that is deleted or corrupted?
- How does the live update behave on slow or intermittent connections?
- What happens if the quality panel has fewer than 5 reviews to aggregate? → Show "insufficient data" rather than misleading metrics.

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

#### Review Quality Signals

- **FR-009**: System MUST compute and display runtime quality metrics from real review data: parser success rate, average findings per review, severity distribution, and category (dimension) coverage
- **FR-010**: System MUST flag sessions where the parser fell back to NIT-wrap as "degraded parse" in the session list
- **FR-011**: System MUST show a "dimension coverage" indicator highlighting under-represented review dimensions (fewer than 5% of total findings)
- **FR-012**: Quality metrics MUST be computed from the last N sessions (configurable, default: 50) — not all-time, to reflect current reviewer behavior

#### Finding Feedback

- **FR-013**: System MUST provide a feedback mechanism on individual findings (thumbs down / report issue) in the transcript view
- **FR-014**: System MUST provide a "Report Missed Issue" action on transcript pages for users to flag issues the reviewer should have caught
- **FR-015**: Feedback entries MUST be stored with full context: session ID, finding ID (if applicable), review bundle snapshot (diff + file names, NOT file contents — to respect the security boundary), user's note, and timestamp
- **FR-016**: System MUST provide an API endpoint to list and retrieve feedback entries for downstream consumption (eval suite golden case harvesting per spec 007)

### Key Entities

Reads Review Session, Message, and Finding entities defined in 001. Adds:

- **FindingFeedback** (new): A user-submitted report on a finding (false positive, missed issue, or general comment). Contains: feedback ID, session ID, finding ID (nullable — null for "missed issue" reports), feedback type (`false_positive`, `missed_issue`, `other`), user note, diff snapshot (file names + line ranges, not full contents), timestamp, and a `harvested` boolean (true once consumed by the eval suite).

**Persistence note**: Spec 001 stores sessions in memory only (ephemeral). This spec introduces lightweight persistence (SQLite in the Docker volume) so that resolved sessions survive container restarts and the dashboard can show historical sessions. This is a prerequisite for the export and compliance use cases in spec 004.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The session list loads within 1 second for up to 100 sessions
- **SC-002**: The transcript page updates within 5 seconds of a new message being exchanged
- **SC-003**: The dashboard is usable without any JavaScript enabled (except live updates)
- **SC-004**: A developer unfamiliar with the system can understand the review status within 10 seconds of opening the dashboard
- **SC-005**: The quality panel accurately reflects parser success rate within 1% of the actual rate computed from stored session data
- **SC-006**: A user can submit finding feedback in under 3 clicks from the transcript page
