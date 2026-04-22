"""MCP client wrapper for the eval harness.

Provides async helpers to connect to the AgentinaBox reviewer MCP server
via ``docker exec`` stdio transport and call its tools (``start_review``,
``discuss``, ``get_review_summary``).

All functions return plain dicts — callers are responsible for converting
to Pydantic models.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

if TYPE_CHECKING:
    from server.models import ReviewBundle

logger = logging.getLogger(__name__)

# Retryable MCP error types (exponential backoff).
_RETRYABLE_ERRORS = {"rate_limited", "timeout"}
# Non-retryable errors that abort the run.
_ABORT_ERRORS = {"auth_failed", "unavailable"}
# Errors that signal the case should be skipped.
_SKIP_ERRORS = {"content_denied"}


class MCPRetryableError(RuntimeError):
    """Raised for retryable MCP errors (rate_limited, timeout)."""


class MCPAbortError(RuntimeError):
    """Raised for non-retryable MCP errors (auth_failed, unavailable)."""


class MCPSkipCaseError(RuntimeError):
    """Raised when the case should be skipped (content_denied)."""


@asynccontextmanager
async def connect(container: str) -> AsyncIterator[ClientSession]:
    """Create an MCP client session to the reviewer container via docker exec.

    Usage::

        async with connect("agentinabox-reviewer-1") as session:
            result = await call_start_review(session, bundle, "case-001")
    """
    server_params = StdioServerParameters(
        command="docker",
        args=["exec", "-i", container, "python", "-m", "server.mcp_server"],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def detect_container() -> str:
    """Auto-detect the running AgentinaBox container.

    Runs ``docker compose ps --format json`` and returns the name of the
    first container whose state is ``"running"``.

    Raises:
        RuntimeError: If docker compose fails or no running container exists.
    """
    proc = await asyncio.create_subprocess_exec(
        "docker", "compose", "ps", "--format", "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        msg = stderr.decode().strip() if stderr else "unknown error"
        raise RuntimeError(
            f"Docker compose failed (exit {proc.returncode}): {msg}"
        )

    containers = _parse_compose_ps_output(stdout.decode())

    running = [c for c in containers if c.get("State") == "running"]
    if not running:
        raise RuntimeError("No running container found via docker compose ps")

    return running[0]["Name"]


def _parse_compose_ps_output(raw: str) -> list[dict]:
    # Docker Compose <2.21 emits a JSON array; >=2.21 emits NDJSON (one
    # object per line). Handle both so callers don't need to know the
    # installed CLI version.
    stripped = raw.strip()
    if not stripped:
        return []
    try:
        if stripped.startswith("["):
            parsed = json.loads(stripped)
            return parsed if isinstance(parsed, list) else []
        return [json.loads(line) for line in stripped.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        # Upgrade to RuntimeError so callers (detect_container) see the
        # documented exception type instead of the raw JSONDecodeError
        # leaking through the abstraction.
        raise RuntimeError(
            f"Failed to parse `docker compose ps --format json` output: {exc}"
        ) from exc


def _redacted_payload_summary(text: str) -> str:
    # Reviewed bundles and model responses may contain secrets or customer
    # code; never echo the raw body. Emit only size + SHA-256 so operators
    # can correlate without exposing content (mirrors mcp-transport.md
    # parse-failure contract).
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return f"{len(text)}B sha256={digest[:16]}"


def _parse_tool_result(result: object, tool_name: str = "<unknown>") -> dict:
    """Extract and parse JSON from an MCP CallToolResult.

    1. Get the first item from ``result.content``
    2. Parse its ``.text`` as JSON
    3. Check for MCP error responses per mcp-transport.md
    4. Return as dict

    Raises:
        RuntimeError: If content is empty or text is not valid JSON.
        MCPRetryableError: For rate_limited or timeout errors.
        MCPAbortError: For auth_failed or unavailable errors.
        MCPSkipCaseError: For content_denied errors.
    """
    content = getattr(result, "content", [])
    if not content:
        raise RuntimeError(
            f"No content in MCP tool result for {tool_name} (empty content list)"
        )

    text = getattr(content[0], "text", None)
    if not isinstance(text, str):
        raise RuntimeError(
            f"MCP tool result for {tool_name} content[0] has no text attribute "
            f"(type={type(content[0]).__name__})"
        )
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError(
            f"Failed to parse MCP tool response for {tool_name} as JSON: "
            f"{exc} (payload {_redacted_payload_summary(text)})"
        ) from exc

    # Check for MCP error responses
    error_type = data.get("error") if isinstance(data, dict) else None
    if error_type:
        if error_type in _RETRYABLE_ERRORS:
            raise MCPRetryableError(
                f"MCP retryable error: {error_type}"
            )
        if error_type in _ABORT_ERRORS:
            raise MCPAbortError(
                f"MCP non-retryable error: {error_type}"
            )
        if error_type in _SKIP_ERRORS:
            raise MCPSkipCaseError(
                f"MCP skip case: {error_type}"
            )

    return data


async def _call_with_retry(
    session: ClientSession,
    tool_name: str,
    arguments: dict,
    max_retries: int = 3,
) -> dict:
    """Call an MCP tool with exponential backoff retry on retryable errors.

    Args:
        session: Active MCP client session.
        tool_name: Name of the MCP tool to call.
        arguments: Tool arguments dict.
        max_retries: Maximum retry attempts for retryable errors.

    Returns:
        Parsed result dict.

    Raises:
        MCPAbortError: On non-retryable errors.
        MCPSkipCaseError: On content_denied.
        RuntimeError: After exhausting retries or on parse failure.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            result = await session.call_tool(tool_name, arguments=arguments)
            return _parse_tool_result(result, tool_name=tool_name)
        except MCPRetryableError as exc:
            wait_time = 2 ** attempt
            logger.warning(
                "MCP %s (attempt %d/%d), waiting %ds: %s",
                tool_name, attempt + 1, max_retries, wait_time, exc,
            )
            last_error = exc
            await asyncio.sleep(wait_time)
        except (MCPAbortError, MCPSkipCaseError):
            raise

    raise RuntimeError(
        f"MCP {tool_name} failed after {max_retries} retries: {last_error}"
    )


async def call_start_review(
    session: ClientSession,
    bundle: ReviewBundle,
    case_id: str,
    max_retries: int = 3,
) -> dict:
    """Call ``start_review`` MCP tool with retry/backoff.

    Sends the :class:`ReviewBundle` fields as a flat dict, excluding
    ``None``-valued optional fields.  Sets ``branch`` to
    ``eval-<case_id>``.

    Returns:
        Parsed ``ReviewResult`` dict.

    Raises:
        MCPAbortError: On non-retryable errors.
        MCPSkipCaseError: On content_denied.
        RuntimeError: After exhausting retries or on parse failure.
    """
    # Build arguments from bundle, excluding None values
    args = {
        k: v
        for k, v in bundle.model_dump().items()
        if v is not None
    }
    # Override branch for eval identification
    args["branch"] = f"eval-{case_id}"

    return await _call_with_retry(
        session, "start_review", args, max_retries=max_retries
    )


async def call_discuss(
    session: ClientSession,
    session_id: str,
    message: str,
    max_retries: int = 3,
) -> dict:
    """Call ``discuss`` MCP tool with retry/backoff.

    Returns:
        Parsed ``DiscussResult`` dict.

    Raises:
        MCPAbortError: On non-retryable errors.
        MCPSkipCaseError: On content_denied.
        RuntimeError: After exhausting retries or on parse failure.
    """
    return await _call_with_retry(
        session, "discuss",
        {"session_id": session_id, "message": message},
        max_retries=max_retries,
    )


async def call_get_review_summary(
    session: ClientSession,
    session_id: str,
    max_retries: int = 3,
) -> dict:
    """Call ``get_review_summary`` MCP tool with retry/backoff.

    Returns:
        Parsed ``ReviewSummary`` dict.

    Raises:
        MCPAbortError: On non-retryable errors.
        MCPSkipCaseError: On content_denied.
        RuntimeError: After exhausting retries or on parse failure.
    """
    return await _call_with_retry(
        session, "get_review_summary",
        {"session_id": session_id},
        max_retries=max_retries,
    )
