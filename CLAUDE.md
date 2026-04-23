# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AgentinaBox** is a Dockerized AI code review sidecar. It receives code via MCP tool calls, forwards it to GitHub Copilot (via the Copilot SDK), and returns SARIF-structured findings. It is project-agnostic — it knows nothing about the repo it reviews until the orchestrating agent tells it.

The project is in **active development**. Spec 001 (Core Review Server) is implemented on branch `001-ai-code-reviewer`.

## Architecture

- **MCP Server**: Exposes `start_review`, `discuss`, `get_review_summary`, `list_sessions` tools via stdio transport (`docker exec -i <container> python -m server.mcp_server`)
- **Inner Model**: GitHub Copilot SDK (Technical Preview) as primary; fallback to OpenAI, Anthropic, Gemini, Ollama
- **Web Dashboard**: FastAPI + Jinja2 server-rendered UI on `localhost:8080` (no SPA)
- **Container**: Single Docker container, `python:3.11-slim-bookworm` + Node.js 22, started with `docker compose up -d`
- **Security Boundary**: Container has NO filesystem access to host repo. All context arrives via MCP parameters. Only credential allowed in container is a fine-grained GitHub PAT (`github_pat_`) with `copilot_requests` permission.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web framework | FastAPI + uvicorn |
| MCP SDK | `mcp>=1.0.0` (Anthropic) |
| Copilot SDK | `github-copilot-sdk>=0.1.0` |
| Copilot CLI | `@github/copilot` (ACP server mode via `--acp`) |
| Templates | Jinja2 (server-side rendering) |
| Credential storage | Fernet encryption in Docker named volume (`/data/`) |
| Testing | pytest |
| Container | Docker Compose |

## Commands

Once implementation exists, these will be the primary commands:

```bash
# Build and run
docker compose up -d
docker compose down
docker compose build --no-cache   # rebuild after Dockerfile changes

# Run tests
pytest                            # all tests
pytest tests/test_foo.py          # single file
pytest tests/test_foo.py::test_bar  # single test
pytest -x                         # stop on first failure

# MCP connection (how Claude Code talks to the review server)
docker exec -i <container> python -m server.mcp_server
```

## Constitution (Non-Negotiable Principles)

The full constitution is at `.specify/memory/constitution.md`. Key rules:

1. **Project-Agnostic**: No hardcoded repo knowledge. All context via MCP tool calls.
2. **No Volume Mounts**: Container must NOT have direct filesystem access to host repo.
3. **Security Boundary**: No secrets enter container except the single GitHub PAT. Content denylist blocks `.env`, `*.pem`, `*.key`, `*credentials*`, `*secret*`.
4. **Test-First (TDD)**: RED-GREEN-REFACTOR. Write failing test before implementation.
5. **Model-Agnostic**: MCP interface stays the same regardless of inner model. Use `list_models()` at runtime, never hardcode model IDs.
6. **YAGNI**: No React, no WebSocket, no PostgreSQL, no premature abstractions.

## Spec Roadmap

Specs live in `specs/NNN-feature-name/spec.md`:

| Spec | Feature | Status |
|------|---------|--------|
| 001 | Core Review Server (MCP + Copilot SDK + Docker) | Implemented |
| 002 | Credential Setup (PAT encryption, onboarding) | Implemented |
| 003 | Review Dashboard (web UI) | Draft |
| 004 | Human Oversight (approval workflow) | Draft |
| 005 | Model Configuration | Draft |
| 006 | Fallback Backends (OpenAI, Anthropic, Gemini, Ollama) | Draft |
| 007 | Eval Harness | Implemented |
| 008 | Prompt Tuning for Structured Output | Implemented |
| 009 | Slack Integration | Backlog |
| 010 | Agent SDK Backends (Claude Agent SDK, Codex CLI) | Backlog |
| 011 | REST API Transport (CI/CD integration) | Backlog |
| 012 | Multi-Dimension Review Engine (parallel personas + synthesis) | Draft |
| 013 | Cross-Session Review Memory (regression detection, dismissal memory) | Backlog |
| 014 | Eval Harness Statistical Hardening | Backlog |

## Development Workflow

### Primary Workflow: Builder/Judge Loop

All feature work goes through a structured builder/judge loop. Use `/loop.build` — it orchestrates speckit commands automatically:

```
/loop.build new <description>          # create task, write spec
/loop.build <task-id>                  # address judge feedback (auto-detects if omitted)
/loop.build <task-id> <phase>          # advance to next phase
/loop.status                           # check current state
```

Phases: `specify` → `design` → `plan` → `build` → `test` → `release`

Codex (judge) reviews each phase. Coordination files live in `agent-loop/<task-id>/`.

### Builder/Judge Roles

- **Claude Code** is the **builder**. Owns `builder.md`. Never edit `judge.md`.
- **Codex** is the **judge**. Owns `judge.md`. Never edit `builder.md`.
- **Peter** is the coordinator and final decision-maker.
- Rounds are **append-only** (`## Round 1`, `## Round 2`, etc.). The only permitted modification is moving rounds to archive files via Context Management.
- Before writing a round, perform **context management checks** (see PROTOCOL.md):
  - **Phase compaction**: if `builder.md` contains rounds from a prior phase (compare round headers to `status.json` phase), write phase summary to `builder-archive.md`, move raw rounds there, clear `builder.md` to a back-reference line.
  - **Round archival**: if `builder.md` has 2+ round headers and you're writing round N >= 3, move rounds 1..N-2 to `builder-archive.md`.
- Read **Phase Summaries** from both archive files every round.
- Respond to judge findings using their IDs (H-1, M-2, etc.).
- Update `status.json` after each round.
- Read `agent-loop/PROTOCOL.md` when working on any task in `agent-loop/`.
- **Before marking `ready_for_judge`**:
  1. Run the `code-review` plugin for self-review on all changed files. Address any findings before proceeding.
  2. Scan `agent-loop/ANTIPATTERNS.md` and verify your output doesn't match any known anti-patterns.
  3. After receiving judge feedback, check if the findings reveal a new anti-pattern worth cataloging.

### Key Protocol Files

| File | Purpose |
|------|---------|
| `agent-loop/PROTOCOL.md` | Full protocol: roles, state transitions, escalation rules |
| `agent-loop/ANTIPATTERNS.md` | Known anti-patterns — check before each round, propose new entries after |
| `AGENTS.md` | Agent instructions with Always/Ask first/Never boundaries |
| `CODEX.md` | Codex-specific judge instructions |
| `CHEATSHEET.md` | Peter's quick-reference for the loop |

### Speckit Commands (called by `/loop.build` automatically)

- `/speckit.specify` — create/update spec
- `/speckit.plan` — generate implementation plan
- `/speckit.tasks` — generate task list
- `/speckit.implement` — execute tasks

### MCP Server Implementation

When implementing MCP server code (tasks T020-T022 in spec 001), use the `mcp-builder` skill at `.claude/skills/mcp-builder/`. Key references:
- `.claude/skills/mcp-builder/reference/python_mcp_server.md` — Python/FastMCP patterns, tool registration, quality checklist
- `.claude/skills/mcp-builder/reference/mcp_best_practices.md` — naming, error handling, response format standards

## Conventions

- **Branches**: `NNN-feature-name` matching spec numbers
- **Commits**: Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- **Simplicity**: Server-rendered Jinja2, `<meta refresh>` or SSE for updates, SQLite/in-memory storage, single CSS file with monospace dark theme, native HTML `<details>/<summary>` over JS widgets
- **Dogfooding**: Once functional, the review server reviews its own changes

## Active Technologies
- Python 3.11+ + FastAPI 0.128+, uvicorn, `mcp>=1.0.0` (FastMCP), `github-copilot-sdk>=0.1.0`, Pydantic 2.12+, Jinja2 (001-ai-code-reviewer)
- In-memory session storage (ephemeral, per MCP process lifetime) (001-ai-code-reviewer)
- Python 3.11+ + `json-repair` (new, for FR-007), existing: `mcp>=1.0.0`, `github-copilot-sdk>=0.1.0`, `pydantic>=2.12` (008-prompt-tuning)
- N/A (no new storage — modifies in-memory prompt strings and parser logic) (008-prompt-tuning)
- Python 3.11+ + `mcp>=1.0.0` (MCP client SDK), `anthropic>=0.86.0` (Tier 2 grader), `pydantic>=2.12` (models) (007-eval-harness)
- File-based (golden cases in `eval/fixtures/`, results in `eval/results/`). No database. (007-eval-harness)

## Recent Changes
- 008-prompt-tuning: Added Python 3.11+ + `json-repair` (new, for FR-007), existing: `mcp>=1.0.0`, `github-copilot-sdk>=0.1.0`, `pydantic>=2.12`
