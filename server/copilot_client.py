"""Copilot SDK wrapper — T020.

Wraps the GitHub Copilot SDK. Provides a simplified interface for the review engine.
Per contracts/copilot-client.md: error classification, model selection, session management.

BUILD-PHASE SPIKE: The SDK is Technical Preview. This implementation uses a mock-friendly
abstraction layer. The actual SDK integration will be validated when running inside Docker
with `github-copilot-sdk` installed.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# --- Error hierarchy per copilot-client.md ---


class CopilotError(Exception):
    """Base for all Copilot client errors."""

    retryable: bool = False


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


class NoCredentialError(CopilotError):
    """No credential configured — terminal."""

    retryable = False


# Model preference order per research.md Decision 4
MODEL_PREFERENCE = [
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
]


class CopilotReviewClient:
    """Manages Copilot SDK lifecycle and review sessions.

    Per copilot-client.md contract. Abstracts SDK internals — callers always get
    `async def send_review(...) -> str` regardless of whether the SDK uses
    `send_and_wait` or `send` + event collection internally.
    """

    def __init__(self) -> None:
        self._connected = False
        self._sdk_client: Any = None
        self._selected_model: str | None = None
        self._available_models: list[dict[str, Any]] = []
        self._sessions: dict[str, Any] = {}
        self._github_token: str | None = None
        self._startup_error: CopilotError | None = None

    def set_startup_error(self, error: "CopilotError") -> None:
        """Set a startup error for deferred raising on first tool call."""
        self._startup_error = error

    async def start(self, github_token: str) -> None:
        """Initialize CopilotClient, start CLI process, select model."""
        if not github_token:
            raise ValueError("github_token is required")
        self._github_token = github_token
        self._startup_error = None  # Clear any previous startup error
        await self._init_sdk()
        self._connected = self._sdk_client is not None
        if self._connected:
            await self.select_model()

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._sessions.clear()
        self._connected = False
        self._startup_error = None
        self._github_token = None
        if self._sdk_client is not None:
            try:
                if hasattr(self._sdk_client, "stop"):
                    await self._sdk_client.stop()
            except Exception as e:
                logger.warning("SDK client stop failed (%s), attempting force_stop", type(e).__name__)
                try:
                    if hasattr(self._sdk_client, "force_stop"):
                        await self._sdk_client.force_stop()
                except Exception as e2:
                    logger.error("SDK client force_stop also failed (%s)", type(e2).__name__)
        self._sdk_client = None

    async def get_available_models(self) -> list[dict[str, Any]]:
        """Return available models from list_models()."""
        return self._available_models

    async def select_model(self, model_id: str | None = None) -> str:
        """Select model by ID or auto-select best available."""
        available_ids = {m["id"] for m in self._available_models}
        if model_id:
            if model_id not in available_ids:
                raise CopilotUnavailableError(f"Model {model_id} is not available")
            self._selected_model = model_id
            return model_id
        for preferred in MODEL_PREFERENCE:
            if preferred in available_ids:
                self._selected_model = preferred
                return preferred

        if self._available_models:
            self._selected_model = self._available_models[0]["id"]
            return self._selected_model

        raise CopilotUnavailableError("No models available from Copilot")

    async def create_review_session(
        self,
        system_prompt: str,
        model: str | None = None,
    ) -> str:
        """Create a Copilot session with reviewer persona. Returns internal session key."""
        if self._startup_error is not None:
            raise self._startup_error
        if self._sdk_client is None:
            raise CopilotUnavailableError(
                "Copilot SDK is not available. Ensure github-copilot-sdk is installed "
                "and GITHUB_TOKEN is set."
            )

        session_key = f"copilot-{uuid.uuid4().hex[:12]}"
        # SDK create_session takes a config dict with on_permission_request (required),
        # plus optional system_message and model.
        config: dict[str, Any] = {
            "on_permission_request": self._approve_all_permissions,
            "system_message": system_prompt,
        }
        resolved_model = model or self._selected_model
        if resolved_model:
            config["model"] = resolved_model
        session = await self._sdk_client.create_session(config)
        self._sessions[session_key] = session
        return session_key

    async def send_review(
        self,
        session_key: str,
        prompt: str,
        timeout: float = 60.0,
    ) -> str:
        """Send review bundle to Copilot, wait for response.

        SDK send_and_wait returns SessionEvent | None. We extract the text
        content from event.data.content. Falls back to send() + on() event
        collection if send_and_wait is unavailable.
        """
        session = self._sessions.get(session_key)
        if session is None:
            raise CopilotError(f"Session {session_key} not found")

        try:
            if hasattr(session, "send_and_wait"):
                event = await session.send_and_wait(
                    {"prompt": prompt}, timeout=timeout
                )
                return self._extract_content(event)
            elif hasattr(session, "send"):
                return await self._send_with_events(session, prompt, timeout)
            else:
                raise CopilotUnavailableError("Session has no send method")
        except TimeoutError as e:
            raise CopilotTimeoutError(f"Review timed out after {timeout}s") from e

    async def send_followup(
        self,
        session_key: str,
        prompt: str,
        timeout: float = 30.0,
    ) -> str:
        """Send discuss message, wait for response."""
        return await self.send_review(session_key, prompt, timeout)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def selected_model(self) -> str | None:
        return self._selected_model

    async def _init_sdk(self) -> None:
        """Initialize the Copilot SDK client.

        If the SDK is not installed (ImportError), the client remains uninitialized.
        Tools will fail with CopilotUnavailableError when called.
        """
        try:
            from copilot import CopilotClient

            self._sdk_client = CopilotClient({"github_token": self._github_token})
            await self._sdk_client.start()

            models = await self._sdk_client.list_models()
            self._available_models = [
                {"id": m.id, "name": getattr(m, "name", m.id)}
                for m in models
            ]
        except ImportError:
            self._sdk_client = None
            self._available_models = []
            self._startup_error = CopilotUnavailableError(
                "github-copilot-sdk is not installed"
            )
        except Exception as e:
            if self._sdk_client is not None:
                try:
                    await self._sdk_client.stop()
                except Exception:
                    pass
            self._sdk_client = None
            self._available_models = []
            err_str = str(e).lower()
            if "auth" in err_str or "401" in err_str or "403" in err_str:
                raise CopilotAuthError(str(e)) from e
            raise CopilotUnavailableError(str(e)) from e

    @staticmethod
    def _extract_content(event: Any) -> str:
        """Extract text content from a SessionEvent.

        SDK send_and_wait returns SessionEvent | None where
        event.data.content holds the assistant's text response.
        """
        if event is None:
            return ""
        data = getattr(event, "data", None)
        if data is None:
            return ""
        content = getattr(data, "content", None)
        return content if isinstance(content, str) else ""

    @staticmethod
    def _approve_all_permissions(request: Any, invocation: Any) -> Any:
        """Permission handler that approves all SDK permission requests.

        Matches the SDK's PermissionHandler.approve_all signature:
        (request: PermissionRequest, invocation: dict) -> PermissionRequestResult.

        The review server runs in a sandboxed Docker container with no
        filesystem access to the host. All context arrives via MCP parameters,
        so approving Copilot's internal permission requests is safe.

        We try to use the SDK's PermissionRequestResult if available,
        otherwise return a dict matching the expected shape.
        """
        try:
            from copilot.types import PermissionRequestResult
            return PermissionRequestResult(kind="approved")
        except ImportError:
            return {"kind": "approved"}

    async def _send_with_events(
        self,
        session: Any,
        prompt: str,
        timeout: float,
    ) -> str:
        """Fallback path: send() + on() event collection.

        Uses the SDK's on() handler API to collect assistant messages
        until the session becomes idle.
        """
        collected: list[str] = []
        idle_event = asyncio.Event()

        def handler(event: Any) -> None:
            event_type = getattr(event, "type", None)
            # Convert enum to string if needed
            type_str = event_type.value if hasattr(event_type, "value") else str(event_type)
            if "assistant" in type_str.lower() and "message" in type_str.lower():
                data = getattr(event, "data", None)
                content = getattr(data, "content", None) if data else None
                if isinstance(content, str):
                    collected.append(content)
            if "idle" in type_str.lower():
                idle_event.set()

        unsubscribe = session.on(handler)
        try:
            await session.send({"prompt": prompt})
            await asyncio.wait_for(idle_event.wait(), timeout=timeout)
        finally:
            unsubscribe()
        return "".join(collected)
