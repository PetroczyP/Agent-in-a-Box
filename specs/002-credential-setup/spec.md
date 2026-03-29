# Feature Specification: AgentinaBox — Credential Setup & Management

**Feature Branch**: `002-credential-setup`
**Created**: 2026-03-13
**Status**: Draft
**Depends on**: 001-ai-code-reviewer

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time Setup via Web UI (Priority: P1)

A colleague pulls the Docker image and runs `docker compose up -d`. They open `localhost:8080` in their browser. Since no credentials are stored, they see a setup wizard that guides them through creating a fine-grained GitHub PAT with the `copilot_requests` permission, pasting it, and verifying the connection. After successful setup, they are redirected to a credential status page showing the active credential source and masked token.

**Why this priority**: This is the primary path for non-technical colleagues to get started without using environment variables.

**Independent Test**: Can be tested by starting the container with no stored credentials and no `GITHUB_TOKEN` env var, opening `localhost:8080`, and verifying the setup wizard appears with clear instructions.

**Acceptance Scenarios**:

1. **Given** a fresh container with no stored credentials and no `GITHUB_TOKEN` env var, **When** a user opens `localhost:8080`, **Then** the setup wizard is displayed with instructions for creating a fine-grained PAT.
2. **Given** the setup wizard is displayed, **When** the user pastes a valid fine-grained PAT and clicks "Save & Test Connection", **Then** the server validates the token format, validates Copilot access via `list_models()`, encrypts and stores the token, and redirects to the credential status page.
3. **Given** the setup wizard is displayed, **When** the user pastes a token with a rejected prefix (e.g., `ghp_`, `gho_`, `ghs_`, `ghu_`) or an empty string, **Then** the server displays a format error identifying the specific rejected token type with remediation steps and a URL (e.g., "Classic PATs (ghp_) are not supported. AgentinaBox requires a fine-grained PAT with the copilot_requests permission. To create one: go to github.com/settings/tokens?type=beta, click 'Generate new token', and enable the copilot_requests permission under Account permissions."). The token is NOT stored.
4. **Given** the setup wizard is displayed, **When** the user pastes a fine-grained PAT that is expired or revoked, **Then** the server displays an auth error with remediation steps (e.g., "Token authentication failed — the token appears to be expired or revoked. To fix this: go to github.com/settings/tokens, check if the token is still active, and create a new fine-grained PAT with the copilot_requests permission if needed."). The token is NOT stored.
5. **Given** the setup wizard is displayed, **When** the user pastes a fine-grained PAT that authenticates to GitHub but cannot access Copilot, **Then** the server displays a permission error listing common causes and remediation steps (e.g., "Token authenticates to GitHub but cannot access Copilot. Common causes: (1) Missing permission — edit the token at github.com/settings/tokens and ensure copilot_requests is enabled. (2) No Copilot subscription — check your plan at github.com/settings/copilot. (3) Organization policy — your org admin may need to enable Copilot for your account."). The token is NOT stored.
6. **Given** the setup wizard is displayed and the Copilot SDK is not installed or cannot start, **When** the user pastes a valid fine-grained PAT and clicks "Save & Test Connection", **Then** the server displays an SDK error explaining this is a container issue (not a token problem) with rebuild steps (e.g., "Copilot SDK unavailable — cannot validate token. This is a container configuration issue, not a problem with your token. The Copilot CLI may not be installed or failed to start. To fix this: run 'docker compose build --no-cache' to rebuild the container, then 'docker compose up -d' to restart it. If the issue persists, check the container logs with 'docker compose logs'. For Copilot CLI setup details, see docs.github.com/en/copilot."). The token is NOT stored.
7. **Given** the container is started with `GITHUB_TOKEN` env var or a Docker secret, **When** a user opens `localhost:8080`, **Then** the credential status page is displayed directly (setup wizard is skipped).

---

### User Story 2 - Rotate or Change Token (Priority: P2)

A developer's token has expired or they want to switch accounts. They open the Settings page, see the masked current token, and click "Change." They paste a new token, the server validates it, re-encrypts, and confirms the update.

**Why this priority**: Token rotation is a maintenance necessity but not needed for initial setup.

**Independent Test**: Can be tested by setting up a token, then changing it via the Settings page and verifying the new token is used for subsequent Copilot calls.

**Acceptance Scenarios**:

1. **Given** a valid token is stored, **When** a user opens the Settings page, **Then** the token is displayed masked (prefix + last 4 characters visible, e.g., `github_pat_...XXXX`) with a "Change" button, and the credential source is shown (stored, env var, or Docker secret).
2. **Given** a user clicks "Change" and pastes a new valid token, **When** they click "Save & Test Connection", **Then** the old token is replaced with the new one (encrypted) and a success message is shown.
3. **Given** a user pastes a new invalid token, **When** they click "Save & Test Connection", **Then** the old token is preserved and an error message explains the rejection.
4. **Given** the active credential comes from a Docker secret or env var (not stored), **When** a user opens the Settings page, **Then** the credential source is shown as "Docker secret" or "Environment variable" and the change form is hidden with a note explaining that the token is managed externally.

---

### User Story 3 - Multiple Credential Sources (Priority: P3)

A DevOps engineer configures the container for CI using Docker secrets instead of environment variables. The system discovers and uses credentials from the highest-priority source automatically: Docker secret > environment variable > stored credential. Docker secrets are preferred because they avoid accidental exposure through subprocess environments, crash dumps, and process inspection. Environment variables remain as a convenience path for local development.

**Why this priority**: Docker secrets support is for shared or production-like deployments where secret hygiene matters most.

**Independent Test**: Can be tested by providing credentials via Docker secret while a stored credential exists, and verifying the Docker secret takes precedence.

**Acceptance Scenarios**:

1. **Given** a Docker secret is mounted at `/run/secrets/github_token` and an env var `GITHUB_TOKEN` is also set, **When** the server starts, **Then** the Docker secret is used (highest priority).
2. **Given** an env var `GITHUB_TOKEN` is set and no Docker secret is mounted, **When** the server starts, **Then** the env var is used.
3. **Given** only a stored credential exists (no Docker secret, no env var), **When** the server starts, **Then** the stored credential is decrypted and used.
4. **Given** no credential source is available (no Docker secret, no env var, no stored credential), **When** the server starts, **Then** the web UI redirects to the setup wizard and MCP tools return a clear "no credential configured" error.

---

### Edge Cases

- **Encryption key deleted, credential remains**: If the Fernet key file is deleted but the encrypted credential file still exists, the system MUST treat this as "no stored credential." The encrypted credential cannot be decrypted and MUST NOT be used. The system logs a warning (without exposing credential data) and falls back to the next available source or shows the setup wizard.
- **Stored credential invalid between restarts**: If a stored credential becomes invalid (e.g., token expired or revoked on GitHub) between container restarts, the system does NOT re-validate stored credentials at startup. The failure is detected on first MCP tool invocation (during `CopilotReviewClient.start()`), and the tool returns a clear auth error. The user can then rotate the token via the Settings page.
- **Docker volume shared between instances**: Sharing the `/data/` Docker volume between two running container instances is unsupported. The system uses atomic file writes (`os.replace()`) to minimize corruption risk, but does NOT implement locking or coordination between instances. If shared, behavior is undefined.
- **Copilot SDK unavailable during validation**: If the Copilot SDK is not installed or the CLI process cannot start, token format validation still succeeds but Copilot validation fails with a verbose error explaining the issue is container-level, not token-level, with rebuild steps (see US1-AS6 for full example message). The token is NOT stored.
- **Docker secret file has trailing whitespace/newline**: Docker secret files often contain a trailing newline. The system MUST strip leading and trailing whitespace from Docker secret file contents before use.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist credentials encrypted at rest using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) in a Docker named volume, never in plaintext. The Fernet key MUST be auto-generated on first use and persisted in the same volume. If the Fernet key is lost, the system MUST treat the encrypted credential as unavailable and require re-entry.
- **FR-002**: System MUST accept credentials via three methods in priority order: Docker secret (read from `/run/secrets/github_token`) > environment variable (`GITHUB_TOKEN`) > stored credential (decrypted from volume). Docker secrets are the preferred method for shared or production-like environments; environment variables are a convenience path for local development. The system MUST resolve the credential source fresh on each process startup.
- **FR-003**: System MUST reject tokens with these prefixes: `ghp_` (classic PAT), `gho_` (OAuth app token), `ghs_` (GitHub App server-to-server token), `ghu_` (GitHub App user-to-server token). System MUST only accept tokens with the `github_pat_` prefix (fine-grained PAT). Error messages MUST identify the specific rejected token type and explain what is expected.
- **FR-004**: System MUST provide a web-based setup wizard at `localhost:8080` when no credentials are configured via any source. The setup wizard MUST include step-by-step instructions for creating a fine-grained PAT with the `copilot_requests` permission.
- **FR-005**: System MUST validate tokens by making a real Copilot SDK call (`list_models()`) before storing them. Generic GitHub API validation (`GET /user`) is insufficient as the sole check — a token can have valid GitHub scopes but lack the Copilot permission or policy access needed for actual reviews. Validation failures MUST produce distinct, verbose, actionable error messages for each failure mode. Messages MUST list possible causes and include specific URLs and remediation steps the user can follow to self-diagnose:
  - **Format error**: Token has a rejected prefix or is empty → identify the rejected type, explain the expected format, and link to token creation at `github.com/settings/tokens?type=beta`
  - **Auth error**: Token is expired, revoked, or otherwise fails GitHub authentication → link to `github.com/settings/tokens` and advise creating a new token with step-by-step instructions
  - **Permission error**: Token authenticates to GitHub but cannot access Copilot (e.g., missing `copilot_requests` permission, no Copilot subscription, or org policy restriction) → list all common causes with remediation steps and URLs for each (`github.com/settings/tokens`, `github.com/settings/copilot`)
  - **SDK error**: Copilot SDK is not installed or CLI process cannot start → identify the SDK as the problem (not the token), provide rebuild commands (`docker compose build --no-cache`), suggest checking container logs, and link to Copilot documentation (`docs.github.com/en/copilot`)
- **FR-006**: System MUST provide a Settings page to view (masked) and rotate stored tokens. The masked display MUST show the token prefix and last 4 characters only (e.g., `github_pat_...XXXX`). When the active credential comes from a Docker secret or env var, the Settings page MUST show the source and disable the rotation form.
- **FR-007**: System MUST never expose plaintext tokens in logs, API responses, or web UI output. Error messages from token validation MUST NOT echo back the submitted token value. Log messages about credential resolution MUST log the source type (e.g., "docker_secret", "env_var", "stored") but never the token value.
- **FR-008**: System MUST bind the web UI port to localhost only via Docker port mapping (`127.0.0.1:8080:8080`). The web server inside the container MAY bind to all interfaces (`0.0.0.0`) since Docker's port mapping restricts host-side access.
- **FR-009**: System MUST provide a credential status page at the root URL (`/`) showing the active credential source and masked token. The page MUST NOT claim connection status or validity — credential validation only occurs during token setup/rotation and on first MCP use, not at page load. This page is owned by this spec and serves as the post-setup redirect destination. Spec 003 (Review Dashboard) may later expand or replace this page, but this spec MUST NOT depend on spec 003 for the post-setup experience.
- **FR-010**: Credential resolution for MCP MUST occur at MCP process startup (within the lifespan context). Each MCP connection via `docker exec` starts a fresh process and resolves the latest available credential. Token rotation via the web UI takes effect on the next MCP connection, not within an active session. Long-lived MCP sessions (if a client holds the stdio pipe open) use the token that was active when the session started; this is expected behavior, consistent with how environment variables bind at process start.

### Key Entities

- **Credential**: The stored GitHub fine-grained PAT. Encrypted at rest with a Fernet key. Has a creation date and last-validated timestamp.
- **Credential Source**: The origin of the active credential. One of: `docker_secret`, `env_var`, `stored`, `none`. Determined at startup by priority order (FR-002).
- **Fernet Key**: A 44-character URL-safe base64 symmetric key used for credential encryption/decryption. Auto-generated on first use, persisted in the Docker volume. Loss of this key invalidates all stored credentials.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from opening `localhost:8080` to a validated, stored credential in under 2 minutes
- **SC-002**: Token rotation completes without downtime (no container restart needed). The next MCP connection (new `docker exec` invocation) after rotation uses the new token. Active MCP sessions continue with the token they started with.
- **SC-003**: Credentials are never exposed in any output visible to the user or in container logs. Verified by grep of all log output and HTTP response bodies.
- **SC-004**: The system correctly prioritizes credential sources on every startup. Verified by testing all 4 combinations (Docker secret + env var, env var only, stored only, none).
- **SC-005**: Invalid tokens (classic PAT, missing Copilot permission, expired) are rejected with specific, actionable error messages that help the user self-correct.
