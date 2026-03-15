# Implementation Plan: Core Review Server

**Branch**: `001-ai-code-reviewer` | **Date**: 2026-03-13 | **Spec**: `specs/001-ai-code-reviewer/spec.md`
**Input**: Feature specification from `specs/001-ai-code-reviewer/spec.md`

## Summary

Build an MCP server inside a Docker container that receives code review bundles from Claude Code, forwards them to GitHub Copilot via the Copilot SDK, and returns SARIF-structured findings. Supports multi-turn discussion, content denylist validation, idempotency, and deterministic context ordering. The web dashboard (spec 003) and credential UI (spec 002) are out of scope — this is the core review engine only.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.128+, uvicorn, `mcp>=1.0.0` (FastMCP), `github-copilot-sdk>=0.1.0`, Pydantic 2.12+
**Storage**: In-memory (ephemeral, per MCP process lifetime per FR-015)
**Testing**: pytest + pytest-asyncio
**Target Platform**: Docker container (`python:3.11-slim-bookworm` + Node.js 22)
**Project Type**: MCP server + web service (hybrid)
**Performance Goals**: `start_review` < 30s, `discuss` < 15s (network permitting)
**Constraints**: No host filesystem access, single GitHub PAT only, advisory only (no CI integration)
**Scale/Scope**: Single user, handful of concurrent sessions, up to 50 changed files per review

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Project-Agnostic | PASS | All context via MCP tool parameters. No repo-specific code. |
| II. No Volume Mounts | PASS | Container has no host filesystem access. `docker exec -i` for MCP. |
| III. Security Boundary | PASS | Only `GITHUB_TOKEN` enters container. Content denylist validates all input. |
| IV. Test-First | PASS | TDD planned for build phase. |
| V. Model-Agnostic | PASS | `list_models()` at runtime, preference-ordered fallback, per-review override. |
| VI. Simplicity | PASS | No React, no WebSocket, no PostgreSQL, no SQLite. Pure in-memory for MVP. |

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-code-reviewer/
├── spec.md
├── plan.md              # This file
├── research.md          # Technical decisions and SDK research
├── data-model.md        # Entity definitions
├── contracts/
│   ├── mcp-tools.md     # MCP tool input/output schemas
│   ├── copilot-client.md # Copilot SDK wrapper interface
│   └── review-engine.md  # Review orchestration interface
└── tasks.md             # (generated in plan phase)
```

### Source Code (repository root)

```text
server/
├── __init__.py
├── main.py              # FastAPI app (container CMD): health check endpoint only for MVP
├── mcp_server.py        # MCP tool definitions (stdio entry point via docker exec)
├── review_engine.py     # Session management, prompt formatting, finding parsing
├── copilot_client.py    # Copilot SDK wrapper
├── models.py            # Pydantic models (ReviewSession, Finding, etc.)
├── denylist.py          # Content denylist validation
├── store.py             # In-memory session store
└── prompts.py           # Reviewer persona prompt templates

tests/
├── conftest.py          # Shared fixtures (mock Copilot client, sample bundles)
├── test_models.py       # Pydantic model validation
├── test_denylist.py     # Content denylist tests
├── test_review_engine.py # Review orchestration tests
├── test_mcp_tools.py    # MCP tool handler tests
├── test_copilot_client.py # Copilot SDK wrapper tests
├── test_store.py        # Session store tests
└── test_finding_parser.py # Finding parsing tests

Dockerfile
docker-compose.yml
pyproject.toml
requirements.txt
```

**Structure Decision**: Single-project layout with `server/` package. No `src/` wrapper — keeps imports simple (`from server.models import ...`). Tests at root level in `tests/`. No templates/static for MVP — web dashboard is spec 003. Container CMD is `uvicorn server.main:app` (FastAPI with health check endpoint only). MCP server is invoked via `docker exec -i`.

## Complexity Tracking

> No constitution violations. No complexity deviations to justify.
