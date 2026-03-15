"""MCP server with tool definitions — T022, T031, T034.

Exposes start_review, discuss, get_review_summary, list_sessions via stdio.
Per contracts/mcp-tools.md and research.md Decision 1 (FastMCP high-level API).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from server.copilot_client import (
    CopilotAuthError,
    CopilotRateLimitError,
    CopilotReviewClient,
    CopilotTimeoutError,
    CopilotUnavailableError,
)
from server.denylist import ContentDenylist
from server.models import (
    DiscussRequest,
    ReviewBundle,
    SummaryRequest,
)
from server.review_engine import BundleTooLargeError, ContentDeniedError, ReviewEngine
from server.store import SessionStore

# Initialize components
_store = SessionStore()
_denylist = ContentDenylist()
_copilot = CopilotReviewClient()
_engine = ReviewEngine(copilot=_copilot, store=_store, denylist=_denylist)


async def _initialize_copilot():
    """Initialize Copilot client on startup.

    If GITHUB_TOKEN is missing or SDK is unavailable, the server still starts.
    Tools will return clear errors when called without a working Copilot backend.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return
    try:
        await _copilot.start(github_token=token)
        if _copilot.is_connected:
            await _copilot.select_model()
    except Exception as e:
        # Store the error so tools can re-raise it with correct classification
        from server.copilot_client import CopilotError
        if isinstance(e, CopilotError):
            _copilot._startup_error = e
        # Non-CopilotError exceptions (e.g. unexpected crashes) leave the client
        # in uninitialized state; create_review_session will raise CopilotUnavailableError


@asynccontextmanager
async def _lifespan(app):
    """Initialize Copilot within the MCP server's event loop."""
    await _initialize_copilot()
    yield


mcp = FastMCP("review-server", lifespan=_lifespan)


@mcp.tool()
async def start_review(
    diff: str,
    files: dict[str, str],
    test_files: dict[str, str] | None = None,
    spec: str | None = None,
    conventions: str | None = None,
    anti_patterns: str | None = None,
    test_results: str | None = None,
    context: str | None = None,
    branch: str | None = None,
    model: str | None = None,
    idempotency_token: str | None = None,
) -> dict:
    """Start a new code review session.

    Validates the bundle against the content denylist, orders context
    deterministically, and forwards to GitHub Copilot for review.
    Returns SARIF-structured findings.
    """
    bundle = ReviewBundle(
        diff=diff,
        files=files,
        test_files=test_files,
        spec=spec,
        conventions=conventions,
        anti_patterns=anti_patterns,
        test_results=test_results,
        context=context,
        branch=branch,
        model=model,
        idempotency_token=idempotency_token,
    )
    try:
        result = await _engine.start_review(bundle)
        return result.model_dump()
    except ContentDeniedError as e:
        return {"error": "content_denied", "denied_files": e.denied_files, "retryable": False}
    except BundleTooLargeError as e:
        return {
            "error": "bundle_too_large",
            "bundle_size": e.bundle_size,
            "model_limit": e.model_limit,
            "guidance": e.guidance,
            "retryable": False,
        }
    except ValueError as e:
        msg = str(e)
        if "empty_diff" in msg:
            return {"error": "empty_diff", "retryable": False}
        if "idempotency_conflict" in msg:
            return {"error": "idempotency_conflict", "message": msg, "retryable": False}
        return {"error": "unknown", "message": msg, "retryable": False}
    except CopilotAuthError as e:
        return {"error": "auth_failed", "message": str(e), "retryable": False}
    except CopilotUnavailableError as e:
        return {"error": "unavailable", "message": str(e), "retryable": False}
    except CopilotTimeoutError as e:
        return {"error": "timeout", "message": str(e), "retryable": True}
    except CopilotRateLimitError as e:
        return {"error": "rate_limited", "message": str(e), "retryable": True}
    except Exception as e:
        retryable = getattr(e, "retryable", False)
        return {"error": "internal", "message": str(e), "retryable": retryable}


@mcp.tool()
async def discuss(
    session_id: str,
    message: str,
    additional_files: dict[str, str] | None = None,
    idempotency_token: str | None = None,
) -> dict:
    """Send a follow-up message in an active review session.

    Supports rebuttals referencing finding IDs, additional file attachments,
    and multi-turn discussion with the reviewer.
    """
    request = DiscussRequest(
        session_id=session_id,
        message=message,
        additional_files=additional_files,
        idempotency_token=idempotency_token,
    )
    try:
        result = await _engine.discuss(request)
        return result.model_dump()
    except ContentDeniedError as e:
        return {"error": "content_denied", "denied_files": e.denied_files, "retryable": False}
    except ValueError as e:
        msg = str(e)
        if "session_not_found" in msg:
            return {"error": "session_not_found", "retryable": False}
        if "session_not_active" in msg:
            return {"error": "session_not_active", "retryable": False}
        if "idempotency_conflict" in msg:
            return {"error": "idempotency_conflict", "message": msg, "retryable": False}
        return {"error": "unknown", "message": msg, "retryable": False}
    except CopilotAuthError as e:
        return {"error": "auth_failed", "message": str(e), "retryable": False}
    except CopilotUnavailableError as e:
        return {"error": "unavailable", "message": str(e), "retryable": False}
    except CopilotTimeoutError as e:
        return {"error": "timeout", "message": str(e), "retryable": True}
    except CopilotRateLimitError as e:
        return {"error": "rate_limited", "message": str(e), "retryable": True}
    except Exception as e:
        retryable = getattr(e, "retryable", False)
        return {"error": "internal", "message": str(e), "retryable": retryable}


@mcp.tool()
async def get_review_summary(session_id: str) -> dict:
    """Get a summary of a review session's findings.

    Returns finding counts by severity, category, and status.
    """
    request = SummaryRequest(session_id=session_id)
    try:
        result = await _engine.get_summary(request.session_id)
        return result.model_dump()
    except ValueError as e:
        msg = str(e)
        if "session_not_found" in msg:
            return {"error": "session_not_found", "retryable": False}
        return {"error": "unknown", "message": msg, "retryable": False}


@mcp.tool()
async def list_sessions() -> dict:
    """List all review sessions with metadata.

    Returns session IDs, branches, statuses, and finding counts.
    """
    result = await _engine.list_sessions()
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
