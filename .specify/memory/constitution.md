<!--
  Sync Impact Report
  ===================
  Version change: 0.0.0 → 1.0.0
  Added sections:
    - Principle I: Project-Agnostic by Design
    - Principle II: Context via MCP, Not Volume Mounts
    - Principle III: Security Boundary Enforcement
    - Principle IV: Test-First Development
    - Principle V: Model-Agnostic Inner Architecture
    - Principle VI: Simplicity Over Sophistication
    - Section: Technical Constraints
    - Section: Development Workflow
    - Governance rules
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ (Constitution Check aligns)
    - .specify/templates/spec-template.md ✅ (requirements structure compatible)
    - .specify/templates/tasks-template.md ✅ (task categories cover all principles)
  Follow-up TODOs: none
-->

# AgentinaBox Constitution

## Core Principles

### I. Project-Agnostic by Design

This tool is a generic AI code review sidecar, not tied to any specific codebase. It MUST:

- Receive all project context through MCP tool calls (the review bundle)
- Know nothing about the repo it reviews until the orchestrating agent tells it
- Ship as a standalone Docker image publishable to ghcr.io
- Work with any AI coding agent that speaks MCP (Claude Code, Copilot CLI, etc.)

A colleague with Docker Desktop and a GitHub account with Copilot access MUST be able to run it out of the box with no project-specific configuration.

### II. Context via MCP, Not Volume Mounts

The container MUST NOT have direct file system access to the host repo. All review context arrives via structured MCP tool call parameters:

- **Allowed**: diff, changed file contents, test files, spec artifacts, project rules, anti-patterns, test results, free-form context
- **Blocked**: secrets (`.env`, `*.pem`), auth state (`.claude/`, `.git/credentials`), git history (`.git/`), dependencies (`node_modules/`, `.venv/`), build artifacts (`dist/`, `htmlcov/`)

The orchestrating agent (Claude Code) decides what to include. The reviewer MUST NOT have unsupervised access to browse the repo.

### III. Security Boundary Enforcement

The container runs a third-party model (Copilot). Secrets MUST NOT enter the container except the single GitHub fine-grained PAT required for Copilot API access. Specifically:

- Classic PATs (`ghp_`) are NOT supported; only fine-grained PATs (`github_pat_`) with `copilot_requests` permission
- Credentials MUST be encrypted at rest (Fernet) in the Docker volume
- The web UI (localhost:8080) MUST bind to `127.0.0.1` only
- No authentication is required for the web UI (it is localhost-only by design)

### IV. Test-First Development

All implementation work MUST follow the RED-GREEN-REFACTOR cycle:

- Write a failing test before writing implementation code
- Confirm the test fails for the right reason
- Write the minimal code to make the test pass
- Refactor only after green

Integration tests MUST cover: MCP tool handlers, Copilot SDK client wrapper, review session lifecycle, and credential storage/retrieval.

### V. Model-Agnostic Inner Architecture

The MCP interface to Claude Code MUST remain identical regardless of what model runs inside the review server. The architecture supports swapping the inner model without changing the external contract:

- Primary: GitHub Copilot SDK (Technical Preview)
- Fallbacks: OpenAI API, Anthropic API, Gemini API, Ollama (local)

Model IDs MUST NOT be hardcoded as constants that cause failures when retired. The server MUST use `list_models()` at runtime and fall back gracefully.

### VI. Simplicity Over Sophistication

Start simple. YAGNI applies aggressively:

- Server-rendered Jinja2 templates, not a React SPA
- `<meta refresh>` or SSE for live updates, not WebSocket
- SQLite or in-memory storage, not PostgreSQL
- Single CSS file with monospace dark theme
- Native HTML (`<details>/<summary>`) over JavaScript widgets
- No features, abstractions, or configurability beyond what is immediately needed

## Technical Constraints

| Constraint | Value |
|-----------|-------|
| Language | Python 3.11+ |
| Web framework | FastAPI + uvicorn |
| MCP SDK | `mcp>=1.0.0` (Anthropic) |
| Copilot SDK | `github-copilot-sdk>=0.1.0` (Technical Preview) |
| Container base | `python:3.11-slim-bookworm` + Node.js 22 (for Copilot CLI) |
| Copilot CLI | `@github/copilot` via npm, ACP server mode (`--acp`) |
| Port | 8080 (web UI), MCP via `docker exec` stdio |
| Credential storage | Fernet encryption in Docker named volume (`/data/`) |
| Template engine | Jinja2 (server-side rendering) |
| Testing | pytest, with real Copilot SDK calls where possible |

## Development Workflow

### Branch Strategy

- `main` branch is always deployable
- Feature work happens on feature branches (`###-feature-name`)
- Each feature branch maps to one spec in `.specify/specs/`

### Code Review

This project dogfoods itself: once the review server is functional, it MUST be used to review its own changes. Until then, Claude Code self-review applies.

### Commit Discipline

- Commit after each task or logical group
- Commit messages follow conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- No commits containing secrets, `.env` files, or credential material

### Docker-First Development

- All testing of the review server MUST be validated inside Docker, not just on the host
- `docker compose up -d` MUST be the only command a colleague needs to start
- The Dockerfile MUST produce a working image without manual post-build steps

## Governance

This constitution governs all development decisions for the AgentinaBox project. When a principle conflicts with expediency, the principle wins unless a Complexity Tracking entry justifies the deviation.

- **Amendments** require updating this file, incrementing the version, and propagating changes to dependent templates via the consistency checklist
- **Versioning** follows semantic versioning: MAJOR for principle removal/redefinition, MINOR for new principles or material expansion, PATCH for clarifications
- **Compliance** is verified at plan time (Constitution Check in plan template) and at review time (the review server itself enforces project rules)

**Version**: 1.0.0 | **Ratified**: 2026-03-13 | **Last Amended**: 2026-03-13
