# Copilot Client Contract: Core Review Server (001)

## Module: `server/copilot_client.py`

Wraps the GitHub Copilot SDK. Provides a simplified interface for the review engine.

## Interface

```python
class CopilotReviewClient:
    """Manages Copilot SDK lifecycle and review sessions."""

    async def start(self, github_token: str) -> None:
        """Initialize CopilotClient, start CLI process, select model."""

    async def stop(self) -> None:
        """Graceful shutdown. Falls back to force_stop on error."""

    async def get_available_models(self) -> list[ModelInfo]:
        """Return available models from list_models()."""

    async def select_model(self, model_id: str | None = None) -> str:
        """Select model by ID or auto-select best available. Returns selected model ID."""

    async def create_review_session(
        self,
        system_prompt: str,
        model: str | None = None,
    ) -> str:
        """Create a Copilot session with reviewer persona. Returns internal session key."""

    async def send_review(
        self,
        session_key: str,
        prompt: str,
        timeout: float = 60.0,
    ) -> str:
        """Send review bundle to Copilot, wait for response. Returns response text."""

    async def send_followup(
        self,
        session_key: str,
        prompt: str,
        timeout: float = 30.0,
    ) -> str:
        """Send discuss message, wait for response. Returns response text."""

    @property
    def is_connected(self) -> bool:
        """Whether the Copilot client is connected and ready."""

    @property
    def selected_model(self) -> str | None:
        """Currently selected model ID."""
```

## Error Classification

The client wraps SDK exceptions into domain errors:

```python
class CopilotError(Exception):
    """Base for all Copilot client errors."""
    retryable: bool

class CopilotAuthError(CopilotError):
    """Auth failure — terminal."""
    retryable = False

class CopilotTimeoutError(CopilotError):
    """Request timed out — retryable."""
    retryable = True

class CopilotRateLimitError(CopilotError):
    """Rate limited — retryable."""
    retryable = True

class CopilotUnavailableError(CopilotError):
    """Model or service unavailable — terminal."""
    retryable = False
```

## SDK Mapping

The Copilot Python SDK (`github-copilot-sdk`) is Technical Preview (v0.1.x). The mapping below has been **validated against the installed SDK** in the local venv via `inspect.signature()`.

**Validated SDK interface** (from `github-copilot-sdk` installed in `.venv`):

| Our method | SDK call | Notes |
|-----------|----------|-------|
| `start()` | `CopilotClient({"github_token": ...})` + `await client.start()` | |
| `stop()` | `await client.stop()` / `await client.force_stop()` | |
| `get_available_models()` | `await client.list_models()` | |
| `create_review_session()` | `await client.create_session(config)` | `config` is a dict with required `on_permission_request` (callable), optional `system_message`, `model` |
| `send_review()` | `await session.send_and_wait({"prompt": ...}, timeout=60)` | Returns `SessionEvent \| None`; text is in `event.data.content` |
| `send_followup()` | Same as `send_review()` with `timeout=30` | |

**Fallback path** (if `send_and_wait` is unavailable — `send()` + event collection):

| Our method | SDK call |
|-----------|----------|
| `send_review()` | `await session.send({"prompt": ...})` returns message ID + `session.on(handler)` to collect `ASSISTANT_MESSAGE` events + wait for `SESSION_IDLE` with `asyncio.wait_for(timeout=60)` |
| `send_followup()` | Same pattern with `timeout=30` |

The wrapper abstracts this choice — callers always get `async def send_review(...) -> str` regardless of which SDK path is used internally.

**Build-phase validation results:**
1. `from copilot import CopilotClient` — confirmed
2. `create_session(config: SessionConfig)` — takes a dict, requires `on_permission_request` key
3. `send_and_wait(options, timeout)` — returns `SessionEvent | None` (not raw `str`)
4. `send(options)` — returns message ID `str`
5. Event subscription via `session.on(handler)` — handler receives `SessionEvent`, unsubscribe via returned callable
6. `PermissionHandler` class exists at `copilot.types.PermissionHandler` — `approve_all(request, invocation)` returns `PermissionRequestResult(kind="approved")`. Our handler uses the same `(request, invocation) -> PermissionRequestResult` signature.

## Configuration

| Config | Source | Default |
|--------|--------|---------|
| `github_token` | `GITHUB_TOKEN` env var only (MVP) | Required |
| `model` | auto-selected via preference list | Best available |

Encrypted credential storage (`/data/credentials.enc`) is deferred to spec 002.
