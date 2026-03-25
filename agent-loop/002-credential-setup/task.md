# Task: 002 — Credential Setup & Management

## Goal

Implement secure credential management for the AgentinaBox review server so users can configure, store, rotate, and resolve GitHub PATs through multiple sources (Docker secrets, environment variables, and encrypted persistent storage), with a web-based setup wizard for first-time configuration.

## Scope

**In scope** (from `specs/002-credential-setup/spec.md`):
- Fernet-encrypted credential storage in Docker named volume (`/data/`)
- Three-source credential resolution: Docker secret > env var > stored credential
- Fine-grained PAT format validation (reject classic PATs)
- Token validation via Copilot SDK `list_models()` call
- Web setup wizard at `localhost:8080` for first-time configuration
- Settings page for token viewing (masked) and rotation
- Localhost-only web UI binding
- Token never exposed in logs, responses, or UI

**Out of scope**:
- Dashboard UI (spec 003)
- Model configuration / selection UI (spec 005)
- Fallback backends (spec 006)
- External KMS or Vault integration
- Multi-user / RBAC

## Constraints

- Constitution: project-agnostic, no host volume mounts, security boundary, TDD, YAGNI
- Server-rendered Jinja2 templates, monospace dark theme, single CSS file
- Python 3.11+, FastAPI, Docker
- MCP server and web server are separate processes (no shared memory)

## Acceptance Criteria

- AC-1: Fresh container with no credentials → web setup wizard is displayed at `localhost:8080`
- AC-2: User pastes valid fine-grained PAT → server validates via Copilot SDK, encrypts, stores, redirects to credential status page
- AC-3: User pastes invalid token → distinct, verbose error messages for each failure mode: format error (wrong prefix), auth error (expired/revoked), permission error (cannot access Copilot — lists causes: missing copilot_requests, no subscription, org policy), SDK error (unavailable). Messages include specific URLs and remediation steps.
- AC-4: Container started with `GITHUB_TOKEN` env var or Docker secret → credential status page displayed (setup wizard skipped)
- AC-5: Stored token can be rotated via Settings page without container restart; next MCP connection uses new token
- AC-6: Credential sources follow priority: Docker secret > env var > stored credential
- AC-7: Token is never visible in plaintext in logs, API responses, or web UI
- AC-8: Web UI is only accessible via localhost (127.0.0.1 binding)
- AC-9: Encryption key loss → treated as no credential, setup wizard shown

## Spec Path

`specs/002-credential-setup/spec.md`

## Phase

`specify`
