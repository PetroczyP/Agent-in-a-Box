# Research: Core Review Server (001)

**Date**: 2026-03-13
**Purpose**: Resolve technical unknowns before design

## Decision 1: MCP Server SDK API Level

**Decision**: Use `FastMCP` high-level API from `mcp>=1.0.0`

**Rationale**: `FastMCP` provides `@mcp.tool()` decorators with automatic JSON Schema generation from type hints and docstrings. Pydantic models work natively for structured input/output validation. The low-level `Server` API exists but adds boilerplate without benefit for our use case.

**Alternatives rejected**:
- Low-level `mcp.server.lowlevel.Server` — manual schema definition, more code, no advantage
- HTTP+SSE transport — Claude Code uses stdio natively via `docker exec`; HTTP adds CORS/auth complexity

**Key patterns**:
```python
from mcp.server.fastmcp import FastMCP, Context
mcp = FastMCP("review-server")

@mcp.tool()
async def start_review(request: ReviewBundle) -> ReviewResult:
    """Start a code review session."""
    ...
```

## Decision 2: MCP Process Lifecycle

**Decision**: The MCP server is the sole entry point for MVP. It runs as a **long-lived process** per Claude Code session.

**Rationale**: MCP stdio is a persistent connection — when Claude Code runs `docker exec -i <container> python -m server.mcp_server`, that process stays alive for the entire Claude Code session. Multiple `start_review`, `discuss`, `get_review_summary`, and `list_sessions` calls all flow through the same process. This means:
- Copilot SDK sessions survive between tool calls (solving multi-turn `discuss`)
- In-memory session state is valid for the connection lifetime
- No cross-process communication needed for MVP

**Container architecture**:
- Container CMD: `uvicorn server.main:app` — FastAPI app with health check endpoint only (satisfies FR-018, keeps container alive for `docker exec`, aligns with task constraint of FastAPI + uvicorn)
- MCP server: invoked via `docker exec -i`, one long-lived process per Claude Code session
- Web dashboard routes: deferred to spec 003 (will extend the same FastAPI app)

**Alternatives rejected**:
- SQLite for cross-process sharing — unnecessary when MCP is long-lived; pulls in spec 003 scope
- Bare `http.server` for health check — violates task constraint specifying FastAPI + uvicorn
- MCP mounted as HTTP on FastAPI — `streamable_http_app()` has known issues (SDK #1367), and stdio is Claude Code's native transport

## Decision 3: Copilot SDK Integration

**Decision**: Use `github-copilot-sdk>=0.1.0`. The SDK is Technical Preview; the Python API was validated against the installed package during the build phase (see `contracts/copilot-client.md` for the full validated mapping).

**Rationale**: The SDK manages the Copilot CLI in ACP server mode (`--acp`) automatically. It provides session management, model selection, and auth handling.

**Integration paths** (validated in build phase):
- **Primary path**: `send_and_wait(options, timeout)` — returns `SessionEvent | None`; text is in `event.data.content`
- **Fallback path**: `send(options)` returns message ID + `session.on(handler)` to collect events + `asyncio.wait_for()` — used if `send_and_wait` is unavailable

See `contracts/copilot-client.md` for the full SDK mapping with both paths and the 6-item validation results.

**Validated SDK surface** (confirmed via `inspect.signature()` against installed `github-copilot-sdk` in `.venv`):
- `from copilot import CopilotClient` — main entry point
- `CopilotClient({"github_token": ...})` + `await client.start()` — initialization; constructor takes `CopilotClientOptions` dict, not kwargs
- `await client.create_session(config)` — `config` is a dict with required `on_permission_request` (callable), optional `system_message`, `model`
- `await session.send_and_wait(options, timeout)` — returns `SessionEvent | None`
- `await session.send(options)` — returns message ID `str`
- Event subscription via `session.on(handler)` — handler receives `SessionEvent`, unsubscribe via returned callable
- `await client.list_models()` — returns available models
- `copilot.types.PermissionHandler` exists — `approve_all(request, invocation)` returns `PermissionRequestResult(kind="approved")`
- The SDK spawns the Copilot CLI process and manages its lifecycle

**Alternatives rejected**:
- Direct HTTP to Copilot API — SDK handles auth, retries, rate limits, protocol negotiation

## Decision 4: Model Selection Strategy

**Decision**: `list_models()` at startup with preference-ordered fallback

**Rationale**: Models are retired without notice (GPT-5 retired 2026-02-17). Hardcoding IDs guarantees future failures. `list_models()` returns available models with capabilities and billing info.

**Pattern**:
```python
models = await client.list_models()
available_ids = {m.id for m in models if not m.policy or m.policy.state == "enabled"}
for preferred in MODEL_PREFERENCE:
    if preferred in available_ids:
        return preferred
return models[0].id
```

**ModelInfo fields used**: `id`, `name`, `policy.state`, `capabilities`

## Decision 5: Async Throughout

**Decision**: Full `asyncio` — all I/O is async

**Rationale**: Both MCP SDK and Copilot SDK are async-native. FastAPI is async-native. Mixing sync calls would require thread pools and add complexity. Whether via `send_and_wait()` or `send()` + event handlers, the Copilot SDK is async throughout.

**Alternatives rejected**:
- Sync Copilot SDK calls in threads — adds thread-safety concerns for session state, no benefit

## Decision 6: Session Storage

**Decision**: In-memory dict, keyed by `session_id`. Sessions are ephemeral — lost when the MCP process ends or the container restarts.

**Rationale**: MCP stdio is a long-lived connection (see Decision 2). All tool calls for one Claude Code session flow through the same process, so in-memory state works. This aligns exactly with FR-015: "maintain review session state in memory" and "all state is lost on container restart." No SQLite, no cross-process sharing needed for MVP.

**Future (spec 003)**: When the web dashboard needs to display sessions, a persistence layer (SQLite or similar) will be introduced. That's spec 003's scope, not ours.

## Decision 7: Fingerprint Algorithm

**Decision**: SHA-256 of `rule_id` + normalized code at `primary_location`

**Rationale**: The spec requires `fingerprint` for matching findings across rounds. Normalizing whitespace before hashing ensures minor formatting changes don't break fingerprint stability.

```python
import hashlib
def compute_fingerprint(rule_id: str, code_snippet: str) -> str:
    normalized = " ".join(code_snippet.split())
    return hashlib.sha256(f"{rule_id}:{normalized}".encode()).hexdigest()[:16]
```

## Decision 8: Content Denylist Implementation

**Decision**: `fnmatch`-based pattern matching against file paths

**Rationale**: The denylist patterns (`.env`, `*.pem`, `*.key`, etc.) are glob-style. Python's `fnmatch` handles these natively. Patterns are configurable but have sensible defaults from FR-006.

## Decision 9: SARIF Finding Parsing

**Decision**: Parse Copilot's free-text response into structured findings using a structured output prompt + JSON parsing

**Rationale**: The Copilot SDK doesn't return SARIF natively. We instruct the reviewer persona to output findings as JSON, then parse and validate with Pydantic. If parsing fails, the raw response is wrapped as a single finding.

## Open Questions

1. **Copilot SDK `customAgents`**: The `custom_agents` session config may provide a better persona mechanism than `system_message` alone. Needs validation during build phase.
2. **Copilot SDK stability**: The SDK is Technical Preview (v0.1.32). API may change. We should pin the exact version and have a fallback plan.
3. **Token limits**: `list_models()` returns `capabilities.limits` but the exact field for context window size needs verification.
