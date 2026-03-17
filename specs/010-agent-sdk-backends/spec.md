# Feature Specification: AgentinaBox — Agent SDK Backends (Claude, Codex)

**Feature Branch**: `010-agent-sdk-backends`
**Created**: 2026-03-16
**Status**: Backlog (Draft)
**Depends on**: 001-ai-code-reviewer, 006-fallback-backends

## Summary

Extend AgentinaBox to support full agent SDKs/CLIs as inner backends — not just raw LLM API calls (covered by Spec 006), but agentic tools that have their own reasoning loops, built-in tools, and structured outputs. The user selects which backend to use from the web UI and provides the corresponding API key.

## Context & Research

### How this differs from Spec 006 (Fallback Backends)

Spec 006 covers using LLM APIs directly (OpenAI API, Anthropic API, Gemini API, Ollama). The agent loop, prompt engineering, and output parsing all happen in our code.

This spec covers using **agent SDKs** where the SDK itself runs an agent loop:

| Backend | SDK/CLI | Auth | Docker Support | Language |
|---------|---------|------|----------------|----------|
| GitHub Copilot | `github-copilot-sdk` + `@github/copilot` CLI | GitHub PAT (`copilot_requests`) | Current implementation | Python + Node.js |
| Claude | `claude-agent-sdk` (Python/TS) | `ANTHROPIC_API_KEY` | Officially recommended by Anthropic | Python or TypeScript |
| Codex | `@openai/codex` CLI + `@openai/codex-sdk` | `CODEX_API_KEY` | Needs Node.js 18+ | TypeScript (CLI is Rust) |

### Key Differences from API Backends

- **Agent SDKs have built-in tools** (file read, search, shell) — we'd use them in read-only mode
- **Agent SDKs manage their own context windows** and reasoning loops
- **Output format varies** — each SDK returns results differently, requiring per-backend output normalization
- **Resource usage is higher** — an agent loop inside a container uses more CPU/RAM than a single API call
- **Quality may be higher** — agent reasoning loops can iteratively refine findings

### Claude Agent SDK Specifics

- `query()` function streams messages as the agent works
- Built-in tools: `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebSearch`, `WebFetch`
- Supports subagents — can define a `code-reviewer` subagent with restricted tools
- Supports MCP server connections for additional tools
- Recommended container resources: 1 GiB RAM, 5 GiB disk, 1 CPU per instance
- Supports Bedrock, Vertex AI, and Azure AI Foundry as alternative model providers

### Codex CLI Specifics

- `codex exec` for non-interactive mode (no TUI)
- `--json` flag for JSONL event streaming
- `--output-schema` can enforce JSON schema on output (potential SARIF alignment)
- `--full-auto` or read-only mode available
- Requires Git repo by default (override with `--skip-git-repo-check`)
- MCP server support available

## Open Questions

- Should we run agent SDKs as subprocesses inside the existing container, or as separate sidecar containers?
- How do we handle the different resource requirements? (Claude SDK: 1 GiB RAM vs a simple API call: ~100 MiB)
- Should the UI show real-time agent progress (streaming), or just the final result?
- How do we normalize the vastly different output formats into our Finding structure?
- For Codex CLI's `--output-schema`, can we pass our SARIF-like schema directly?
- Should we support switching backends mid-session (for `discuss` follow-ups)?

## Rough User Stories

### US1 - Select Backend from Web UI (P1)

A user opens the AgentinaBox web dashboard, sees a dropdown with available backends (Copilot, Claude, Codex, plus any API backends from Spec 006). They select "Claude Agent SDK", enter their Anthropic API key, and start a review. The MCP interface to the orchestrating agent remains identical.

### US2 - Claude Agent SDK as Reviewer (P1)

The container uses `claude-agent-sdk` with a read-only subagent (`allowed_tools=["Read", "Glob", "Grep"]`) and the reviewer persona prompt. The agent reasons about the code using its built-in tools and returns findings that are normalized into the standard Finding structure.

### US3 - Codex CLI as Reviewer (P2)

The container uses `codex exec` in read-only mode with `--output-schema` pointing to the Finding schema. Codex analyzes the code and returns structured findings that are normalized into the standard format.

## Dependencies

- Spec 001 (Core Review Server) — must be stable
- Spec 006 (Fallback Backends) — the pluggable backend interface should be designed to accommodate both API and SDK backends
- Spec 005 (Model Configuration) — the UI picker for backend selection

## Technical Notes

- Container image size will increase significantly (Claude SDK + Codex CLI + dependencies)
- Consider multi-stage Docker builds or optional layers
- Resource limits per backend should be configurable
- Agent SDK backends may need longer timeouts than API backends (agent reasoning loops take time)
