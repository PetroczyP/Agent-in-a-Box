# Implementation Plan: Credential Setup & Management

**Branch**: `002-credential-setup` | **Date**: 2026-03-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-credential-setup/spec.md`

## Summary

Implement secure credential management for AgentinaBox: Fernet-encrypted PAT storage in a Docker named volume, three-source credential resolution (Docker secret > env var > stored), format + Copilot SDK validation, and a server-rendered web UI for setup and rotation.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.128+, uvicorn, cryptography (Fernet), Jinja2, pydantic 2.12+
**Storage**: Fernet-encrypted files in Docker named volume (`/data/`)
**Testing**: pytest, pytest-asyncio
**Target Platform**: Linux (Docker container, `python:3.11-slim-bookworm` + Node.js 22)
**Project Type**: Web service (FastAPI) + MCP server (stdio)
**Constraints**: Localhost-only web UI, no shared memory between web/MCP processes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Project-Agnostic | PASS | Credential management is container-level, not project-specific |
| II. No Volume Mounts | PASS | `/data/` is a Docker named volume, not a host bind mount |
| III. Security Boundary | PASS | Fernet encryption at rest, localhost binding, fine-grained PAT only, never log tokens |
| IV. Test-First | PASS | TDD required for all modules |
| V. Model-Agnostic | PASS | Validation uses `list_models()` — no hardcoded model IDs |
| VI. Simplicity (YAGNI) | PASS | Jinja2 templates, query-param flash messages, no session middleware |

## Project Structure

### Documentation (this feature)

```text
specs/002-credential-setup/
  plan.md              # This file
  spec.md              # Feature specification (10 FRs, 3 user stories)
  research.md          # Phase 0: Fernet, Docker secrets, PAT prefixes, SDK errors, FastAPI patterns
  data-model.md        # Phase 1: StoredCredential, CredentialSource, ResolvedCredential, TokenValidationError
  contracts/           # Phase 1: 4 module contracts
    credential-store.md
    credential-resolver.md
    token-validator.md
    web-routes.md
  checklists/
    requirements.md    # Spec quality checklist
```

### Source Code (repository root)

```text
server/
  credential_store.py     # NEW — Fernet encrypt/decrypt, file I/O
  credential_resolver.py  # NEW — Multi-source resolution
  token_validator.py      # NEW — Format check + Copilot SDK validation
  web_routes.py           # NEW — FastAPI routes (/, /setup, /settings)
  main.py                 # MODIFIED — mount routes, templates, static
  mcp_server.py           # MODIFIED — use CredentialResolver in lifespan
  copilot_client.py       # MODIFIED — add NoCredentialError(CopilotError) class; existing _startup_error flow reused
  templates/              # NEW directory
    base.html             # Layout: nav, flash, footer (monospace dark theme)
    status.html           # GET / — source + masked token
    setup.html            # GET /setup — PAT instructions + form
    settings.html         # GET /settings — rotation form
  static/                 # NEW directory
    style.css             # Single CSS file (monospace dark theme)

tests/
  test_credential_store.py    # NEW
  test_credential_resolver.py # NEW
  test_token_validator.py     # NEW
  test_web_routes.py          # NEW

docker-compose.yml        # MODIFIED — volume, secrets, localhost binding
Dockerfile                # MODIFIED — /data/ directory, cryptography dep
requirements.txt          # MODIFIED — add cryptography>=44.0.0
```

**Structure Decision**: Flat module layout in `server/` consistent with existing codebase. No sub-packages — 4 new files alongside existing modules.

## Integration Points

### MCP Server (`mcp_server.py`)

Current `_initialize_copilot()` reads `os.environ.get("GITHUB_TOKEN")` directly. Must change to:

```python
async def _initialize_copilot():
    resolver = CredentialResolver(store=CredentialStore())
    resolved = resolver.resolve()
    if resolved is None:
        # No credential source available — store a clear error for MCP tools
        from server.copilot_client import NoCredentialError
        _copilot._startup_error = NoCredentialError(
            "No credential configured. Set up a token at localhost:8080, "
            "provide GITHUB_TOKEN env var, or mount a Docker secret at "
            "/run/secrets/github_token."
        )
        return
    token = resolved.token
    # ... rest unchanged
```

This satisfies FR-010 (credential resolution at MCP process startup).

**No-credential behavior**: When `resolve()` returns `None`, the server still starts but sets a descriptive `_startup_error` on the Copilot client. The `start_review` tool will surface this error via the `_startup_error` check in `create_review_session()` at `copilot_client.py:131-132`. Other tools do not reach this check: `discuss` calls `send_followup()` → `send_review()` on an existing session; `get_review_summary` and `list_sessions` access only the session store. The error message directs users to all 3 credential setup methods. This replaces the current misleading message ("Copilot SDK is not available. Ensure github-copilot-sdk is installed and GITHUB_TOKEN is set.") which is inaccurate for the no-credential case.

**Note**: `copilot_client.py` is minimally modified — add `NoCredentialError(CopilotError)` class (`retryable = False`) to the existing error hierarchy. The `_startup_error: CopilotError | None` type and `create_review_session()` check remain unchanged. The main change is in `mcp_server.py` which now sets a credential-specific `NoCredentialError` instead of silently returning.

**MCP error handler contract**: `NoCredentialError` requires a dedicated `except` clause in each MCP tool's error handler chain (alongside `CopilotAuthError`, `CopilotUnavailableError`, etc.) to prevent it falling through to the generic `except Exception` → `"internal"` branch. Mapping:

```python
from server.copilot_client import NoCredentialError

except NoCredentialError as e:
    return {"error": "no_credential", "message": str(e), "retryable": False}
```

This handler is required only in `start_review` — the sole MCP tool whose code path reaches `CopilotReviewClient.create_review_session()` and thus `_startup_error`. The `discuss` tool calls `send_followup()` → `send_review()`, which operates on an existing session and never checks `_startup_error`; if no credential was configured, no session could have been created, so `discuss` would hit `session_not_found` first. The read-only tools (`get_review_summary`, `list_sessions`) only access the session store and never touch the Copilot client. The `"no_credential"` error code is distinct from `"unavailable"` (SDK/service down) and `"auth_failed"` (bad token) — it tells the orchestrating agent that no credential is configured and directs the user to the 3 setup methods. RED coverage for this handler goes in `tests/test_mcp_handlers.py` following the existing error-mapping test pattern (e.g., `test_auth_error_maps_correctly`).

### Web Server (`main.py`)

Current minimal app with only `/health`. Must add:
- Jinja2Templates mount
- StaticFiles mount for CSS
- Include `web_routes` router
- Instantiate shared `CredentialStore`, `CredentialResolver`, `TokenValidator`

### Docker Configuration

`docker-compose.yml` changes:
- Port binding: `"8080:8080"` → `"127.0.0.1:8080:8080"` (FR-008)
- Add named volume: `review-data:/data`
- Add secrets section (optional, for Docker secret path)

`Dockerfile` changes:
- Add `RUN mkdir -p /data && chmod 700 /data`
- `cryptography` already pulled via `requirements.txt`
