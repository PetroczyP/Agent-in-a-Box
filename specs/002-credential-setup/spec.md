# Feature Specification: AgentinaBox — Credential Setup & Management

**Feature Branch**: `002-credential-setup`
**Created**: 2026-03-13
**Status**: Draft
**Depends on**: 001-ai-code-reviewer

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time Setup via Web UI (Priority: P1)

A colleague pulls the Docker image and runs `docker compose up -d`. They open `localhost:8080` in their browser. Since no credentials are stored, they see a setup wizard that guides them through creating a fine-grained GitHub PAT with the `copilot_requests` permission, pasting it, and verifying the connection. After successful setup, they are redirected to the main dashboard.

**Why this priority**: This is the primary path for non-technical colleagues to get started without using environment variables.

**Independent Test**: Can be tested by starting the container with no stored credentials and no `GITHUB_TOKEN` env var, opening `localhost:8080`, and verifying the setup wizard appears with clear instructions.

**Acceptance Scenarios**:

1. **Given** a fresh container with no stored credentials and no `GITHUB_TOKEN` env var, **When** a user opens `localhost:8080`, **Then** the setup wizard is displayed with instructions for creating a fine-grained PAT.
2. **Given** the setup wizard is displayed, **When** the user pastes a valid fine-grained PAT and clicks "Save & Test Connection", **Then** the server validates the token, encrypts and stores it, and redirects to the dashboard.
3. **Given** the setup wizard is displayed, **When** the user pastes an invalid token (classic PAT or expired), **Then** the server displays a specific error explaining why the token was rejected.
4. **Given** the container is started with `GITHUB_TOKEN` env var set to a valid fine-grained PAT, **When** a user opens `localhost:8080`, **Then** the dashboard is displayed directly (setup wizard is skipped).

---

### User Story 2 - Rotate or Change Token (Priority: P2)

A developer's token has expired or they want to switch accounts. They open the Settings page, see the masked current token, and click "Change." They paste a new token, the server validates it, re-encrypts, and confirms the update.

**Why this priority**: Token rotation is a maintenance necessity but not needed for initial setup.

**Independent Test**: Can be tested by setting up a token, then changing it via the Settings page and verifying the new token is used for subsequent Copilot calls.

**Acceptance Scenarios**:

1. **Given** a valid token is stored, **When** a user opens the Settings page, **Then** the token is displayed masked (only last 4 characters visible) with a "Change" button.
2. **Given** a user clicks "Change" and pastes a new valid token, **When** they click "Save & Test Connection", **Then** the old token is replaced with the new one (encrypted) and a success message is shown.
3. **Given** a user pastes a new invalid token, **When** they click "Save & Test Connection", **Then** the old token is preserved and an error message explains the rejection.

---

### User Story 3 - Multiple Credential Sources (Priority: P3)

A DevOps engineer configures the container for CI using Docker secrets instead of environment variables. The system discovers and uses credentials from the highest-priority source automatically: Docker secret > environment variable > stored credential. Docker secrets are preferred because they avoid accidental exposure through subprocess environments, crash dumps, and process inspection. Environment variables remain as a convenience path for local development.

**Why this priority**: Docker secrets support is for shared or production-like deployments where secret hygiene matters most.

**Independent Test**: Can be tested by providing credentials via Docker secret while a stored credential exists, and verifying the Docker secret takes precedence.

**Acceptance Scenarios**:

1. **Given** a Docker secret is mounted and an env var is also set, **When** the server starts, **Then** the Docker secret is used (highest priority).
2. **Given** an env var is set and no Docker secret is mounted, **When** the server starts, **Then** the env var is used.
3. **Given** only a stored credential exists, **When** the server starts, **Then** the stored credential is decrypted and used.

---

### Edge Cases

- What happens if the encryption key file is deleted but the encrypted credential remains?
- What happens if the stored credential becomes invalid between container restarts?
- How does the system behave if the Docker volume is shared between two container instances?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist credentials encrypted at rest in a Docker volume, never in plaintext
- **FR-002**: System MUST accept credentials via three methods in priority order: Docker secret > environment variable > stored credential. Docker secrets are the preferred method for shared or production-like environments; environment variables are a convenience path for local development
- **FR-003**: System MUST reject classic PATs and only accept fine-grained PATs with `copilot_requests` permission
- **FR-004**: System MUST provide a web-based setup wizard at `localhost:8080` when no credentials are configured
- **FR-005**: System MUST validate tokens by making a real Copilot SDK call (e.g., `list_models()`) before storing them. Generic GitHub API validation (`GET /user`) is insufficient — a token can have valid GitHub scopes but lack the Copilot permission or policy access needed for actual reviews. If the Copilot call fails, the token MUST be rejected with a specific error explaining that the token works for GitHub but not for Copilot
- **FR-006**: System MUST provide a Settings page to view (masked) and rotate stored tokens
- **FR-007**: System MUST never expose plaintext tokens in logs, API responses, or web UI output
- **FR-008**: System MUST bind the web UI to localhost only (not exposed to the network)

### Key Entities

- **Credential**: The stored GitHub fine-grained PAT. Encrypted at rest with a Fernet key. Has a creation date and last-validated timestamp.
- **Credential Source**: The origin of the active credential (env var, Docker secret, or stored). Determined at startup by priority order.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from opening `localhost:8080` to a validated, stored credential in under 2 minutes
- **SC-002**: Token rotation completes without downtime (no container restart needed)
- **SC-003**: Credentials are never exposed in any output visible to the user or in container logs
- **SC-004**: The system correctly prioritizes credential sources on every startup
