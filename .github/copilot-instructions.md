# Copilot Instructions — Agent-in-a-Box

## Project Overview

AgentinaBox is a Dockerized AI code review sidecar. It receives code via MCP tool calls, forwards it to GitHub Copilot (via the Copilot SDK), and returns SARIF-structured findings. It is **project-agnostic** — it knows nothing about the repo it reviews until the orchestrating agent tells it.

## Architecture

- **MCP Server**: Exposes `start_review`, `discuss`, `get_review_summary`, `list_sessions` tools via stdio transport (`docker exec -i <container> python -m server.mcp_server`)
- **Inner Model**: GitHub Copilot SDK (Technical Preview). Fallback backends (OpenAI, Anthropic, Gemini, Ollama) are planned in spec 006 but not yet implemented.
- **Container**: Single Docker container (`python:3.11-slim-bookworm` + Node.js 22), started with `docker compose up -d`
- **Transport**: MCP stdio only. REST API transport is planned (spec 011) but NOT implemented yet.

## Non-Negotiable Principles (Constitution)

1. **Project-Agnostic**: No hardcoded repo knowledge. All context arrives via MCP tool parameters.
2. **No Volume Mounts**: The container must NEVER have direct filesystem access to the host repo.
3. **Security Boundary**: No secrets enter the container except a single GitHub PAT (`github_pat_`). The content denylist blocks `.env`, `*.pem`, `*.key`, `*credentials*`, `*secret*`.
4. **Model-Agnostic**: The MCP interface stays the same regardless of inner model. Use `list_models()` at runtime, never hardcode model IDs.
5. **YAGNI**: No React, no WebSocket, no PostgreSQL, no premature abstractions.

## Tech Stack

- Python 3.11+, FastAPI, uvicorn, Pydantic 2.12+
- `mcp>=1.0.0` (Anthropic FastMCP SDK), `github-copilot-sdk>=0.1.0`
- Jinja2 for server-rendered templates, `json-repair` for malformed JSON recovery
- pytest for testing, Docker Compose for container orchestration

## Conventions

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Server-rendered Jinja2 with monospace dark theme, no SPA frameworks
- In-memory session storage (ephemeral, per MCP process lifetime)
- All enums use `str, Enum` pattern for JSON serialization
