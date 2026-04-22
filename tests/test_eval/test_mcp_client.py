"""RED tests for MCP client wrapper (T009).

Tests MCP connection setup, tool calling, response parsing, and container
detection. All tests are fully mocked — no Docker or MCP server required.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.models import ReviewBundle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_content(data: dict) -> MagicMock:
    """Create a mock TextContent with JSON text."""
    tc = MagicMock()
    tc.type = "text"
    tc.text = json.dumps(data)
    return tc


def _make_call_tool_result(data: dict) -> MagicMock:
    """Create a mock CallToolResult whose content contains one TextContent."""
    result = MagicMock()
    result.content = [_make_text_content(data)]
    result.isError = False
    return result


def _sample_bundle() -> ReviewBundle:
    return ReviewBundle(
        diff="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new",
        files={"main.py": "print('hello')"},
        conventions="PEP 8",
        context="unit test context",
    )


# ===========================================================================
# TestConnect — async context manager wiring
# ===========================================================================


class TestConnect:
    """connect() must configure StdioServerParameters and yield a session."""

    @pytest.mark.asyncio
    async def test_server_params_constructed_correctly(self) -> None:
        """StdioServerParameters must use docker exec -i <container>."""
        from eval.mcp_client import connect

        captured_params = {}
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        @asynccontextmanager
        async def fake_stdio_client(params):
            captured_params["params"] = params
            yield (MagicMock(), MagicMock())

        @asynccontextmanager
        async def fake_client_session(read, write):
            yield mock_session

        with (
            patch("eval.mcp_client.stdio_client", fake_stdio_client),
            patch("eval.mcp_client.ClientSession", fake_client_session),
        ):
            async with connect("my-container") as session:
                pass

        params = captured_params["params"]
        assert params.command == "docker"
        assert params.args == [
            "exec", "-i", "my-container", "python", "-m", "server.mcp_server"
        ]

    @pytest.mark.asyncio
    async def test_session_initialized(self) -> None:
        """session.initialize() must be called before yielding."""
        from eval.mcp_client import connect

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        @asynccontextmanager
        async def fake_stdio_client(params):
            yield (MagicMock(), MagicMock())

        @asynccontextmanager
        async def fake_client_session(read, write):
            yield mock_session

        with (
            patch("eval.mcp_client.stdio_client", fake_stdio_client),
            patch("eval.mcp_client.ClientSession", fake_client_session),
        ):
            async with connect("test-box") as session:
                assert session is mock_session

        mock_session.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_yields_client_session(self) -> None:
        """connect() yields the ClientSession object."""
        from eval.mcp_client import connect

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        @asynccontextmanager
        async def fake_stdio_client(params):
            yield (MagicMock(), MagicMock())

        @asynccontextmanager
        async def fake_client_session(read, write):
            yield mock_session

        with (
            patch("eval.mcp_client.stdio_client", fake_stdio_client),
            patch("eval.mcp_client.ClientSession", fake_client_session),
        ):
            async with connect("box") as session:
                # Should be the mock session, not something else
                assert session is mock_session


# ===========================================================================
# TestCallStartReview — start_review tool arguments and parsing
# ===========================================================================


class TestCallStartReview:
    """call_start_review sends bundle fields and parses response."""

    @pytest.mark.asyncio
    async def test_sends_correct_arguments(self) -> None:
        """Tool call passes ReviewBundle fields as flat dict."""
        from eval.mcp_client import call_start_review

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result(
                {"session_id": "s-1", "model": "gpt-4", "findings": [],
                 "finding_count": 0, "severity_summary": {}}
            )
        )
        bundle = _sample_bundle()

        await call_start_review(mock_session, bundle, "case-001")

        mock_session.call_tool.assert_awaited_once()
        call_args = mock_session.call_tool.call_args
        assert call_args[0][0] == "start_review"  # tool name

        args = call_args[1]["arguments"] if "arguments" in call_args[1] else call_args[0][1]
        assert args["diff"] == bundle.diff
        assert args["files"] == bundle.files
        assert args["conventions"] == bundle.conventions
        assert args["context"] == bundle.context
        assert args["branch"] == "eval-case-001"

    @pytest.mark.asyncio
    async def test_excludes_none_fields(self) -> None:
        """None-valued optional fields should not be in the arguments dict."""
        from eval.mcp_client import call_start_review

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result(
                {"session_id": "s-1", "model": "gpt-4", "findings": [],
                 "finding_count": 0, "severity_summary": {}}
            )
        )
        # Bundle with only required fields set
        bundle = ReviewBundle(
            diff="diff content",
            files={"a.py": "code"},
        )

        await call_start_review(mock_session, bundle, "case-002")

        call_args = mock_session.call_tool.call_args
        args = call_args[1]["arguments"] if "arguments" in call_args[1] else call_args[0][1]
        # test_files, spec, conventions, etc. should be absent
        assert "test_files" not in args
        assert "spec" not in args
        assert "anti_patterns" not in args
        assert "test_results" not in args
        # branch should always be present
        assert args["branch"] == "eval-case-002"

    @pytest.mark.asyncio
    async def test_parses_text_content_as_json(self) -> None:
        """Response TextContent.text is parsed as JSON dict."""
        from eval.mcp_client import call_start_review

        expected = {
            "session_id": "sess-abc",
            "model": "gpt-4o",
            "findings": [{"finding_id": "F-1"}],
            "finding_count": 1,
            "severity_summary": {"BUG": 1},
        }
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result(expected)
        )

        result = await call_start_review(mock_session, _sample_bundle(), "c1")

        assert result == expected
        assert result["session_id"] == "sess-abc"
        assert result["finding_count"] == 1

    @pytest.mark.asyncio
    async def test_parse_failure_raises_runtime_error(self) -> None:
        """Non-JSON response raises RuntimeError with a redacted summary.

        Per mcp-transport.md, the raw payload MUST NOT appear in error logs —
        reviewed bundles may contain secrets. Assert the error carries the
        tool name and a size+hash summary, and explicitly verify the raw
        body is NOT echoed.
        """
        from eval.mcp_client import call_start_review

        bad_result = MagicMock()
        bad_tc = MagicMock()
        bad_tc.type = "text"
        bad_tc.text = "NOT VALID JSON {{{"
        bad_result.content = [bad_tc]
        bad_result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=bad_result)

        with pytest.raises(RuntimeError, match="start_review") as exc_info:
            await call_start_review(mock_session, _sample_bundle(), "c1")
        msg = str(exc_info.value)
        assert "NOT VALID JSON" not in msg
        assert "payload" in msg and "sha256=" in msg

    @pytest.mark.asyncio
    async def test_empty_content_raises_runtime_error(self) -> None:
        """Empty content list raises RuntimeError."""
        from eval.mcp_client import call_start_review

        empty_result = MagicMock()
        empty_result.content = []
        empty_result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=empty_result)

        with pytest.raises(RuntimeError, match="[Ee]mpty|[Nn]o content"):
            await call_start_review(mock_session, _sample_bundle(), "c1")


# ===========================================================================
# TestCallDiscuss — discuss tool
# ===========================================================================


class TestCallDiscuss:
    """call_discuss sends session_id + message and parses response."""

    @pytest.mark.asyncio
    async def test_sends_correct_arguments(self) -> None:
        """Tool call passes session_id and message."""
        from eval.mcp_client import call_discuss

        expected_response = {
            "response": "Finding dismissed.",
            "updated_findings": [],
            "finding_count_by_status": {"dismissed": 1},
        }
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result(expected_response)
        )

        await call_discuss(mock_session, "sess-123", "I disagree with F-001")

        mock_session.call_tool.assert_awaited_once()
        call_args = mock_session.call_tool.call_args
        assert call_args[0][0] == "discuss"
        args = call_args[1]["arguments"] if "arguments" in call_args[1] else call_args[0][1]
        assert args["session_id"] == "sess-123"
        assert args["message"] == "I disagree with F-001"

    @pytest.mark.asyncio
    async def test_parses_response(self) -> None:
        """Response is parsed as dict."""
        from eval.mcp_client import call_discuss

        expected = {
            "response": "Understood.",
            "updated_findings": [{"finding_id": "F-1"}],
            "finding_count_by_status": {"active": 0, "dismissed": 1},
        }
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result(expected)
        )

        result = await call_discuss(mock_session, "s-1", "msg")

        assert result == expected

    @pytest.mark.asyncio
    async def test_parse_failure_raises_runtime_error(self) -> None:
        """Non-JSON discuss response raises RuntimeError with a redacted summary."""
        from eval.mcp_client import call_discuss

        bad_result = MagicMock()
        bad_tc = MagicMock()
        bad_tc.type = "text"
        bad_tc.text = "<html>error</html>"
        bad_result.content = [bad_tc]
        bad_result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=bad_result)

        with pytest.raises(RuntimeError, match="discuss") as exc_info:
            await call_discuss(mock_session, "s-1", "msg")
        msg = str(exc_info.value)
        assert "<html>error</html>" not in msg
        assert "payload" in msg and "sha256=" in msg


# ===========================================================================
# TestCallGetReviewSummary — get_review_summary tool
# ===========================================================================


class TestCallGetReviewSummary:
    """call_get_review_summary sends session_id and parses response."""

    @pytest.mark.asyncio
    async def test_sends_correct_arguments(self) -> None:
        """Tool call passes session_id only."""
        from eval.mcp_client import call_get_review_summary

        expected_response = {
            "session_id": "sess-abc",
            "status": "completed",
            "model": "gpt-4",
            "round_count": 2,
            "findings": [],
            "finding_count": 0,
            "by_severity": {},
            "by_category": {},
            "by_status": {},
        }
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result(expected_response)
        )

        await call_get_review_summary(mock_session, "sess-abc")

        mock_session.call_tool.assert_awaited_once()
        call_args = mock_session.call_tool.call_args
        assert call_args[0][0] == "get_review_summary"
        args = call_args[1]["arguments"] if "arguments" in call_args[1] else call_args[0][1]
        assert args["session_id"] == "sess-abc"

    @pytest.mark.asyncio
    async def test_parses_response(self) -> None:
        """Response is parsed as dict."""
        from eval.mcp_client import call_get_review_summary

        expected = {
            "session_id": "s-1",
            "status": "completed",
            "model": "gpt-4",
            "round_count": 3,
            "findings": [{"finding_id": "F-1"}],
            "finding_count": 1,
            "by_severity": {"BUG": 1},
            "by_category": {"security": 1},
            "by_status": {"active": 1},
        }
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result(expected)
        )

        result = await call_get_review_summary(mock_session, "s-1")

        assert result == expected

    @pytest.mark.asyncio
    async def test_parse_failure_raises_runtime_error(self) -> None:
        """Non-JSON summary response raises RuntimeError with a redacted summary."""
        from eval.mcp_client import call_get_review_summary

        bad_result = MagicMock()
        bad_tc = MagicMock()
        bad_tc.type = "text"
        bad_tc.text = "Server Error 500"
        bad_result.content = [bad_tc]
        bad_result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=bad_result)

        with pytest.raises(RuntimeError, match="get_review_summary") as exc_info:
            await call_get_review_summary(mock_session, "s-1")
        msg = str(exc_info.value)
        assert "Server Error 500" not in msg
        assert "payload" in msg and "sha256=" in msg


# ===========================================================================
# TestDetectContainer — docker compose ps parsing
# ===========================================================================


class TestDetectContainer:
    """detect_container auto-discovers the running AgentinaBox container."""

    @pytest.mark.asyncio
    async def test_returns_first_running_container(self) -> None:
        """Parses docker compose ps --format json output."""
        from eval.mcp_client import detect_container

        docker_output = json.dumps([
            {"Name": "agentinabox-reviewer-1", "State": "running"},
        ])

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(docker_output.encode(), b"")
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            name = await detect_container()

        assert name == "agentinabox-reviewer-1"
        # Verify docker compose was called correctly
        mock_exec.assert_awaited_once()
        call_args = mock_exec.call_args[0]
        assert "docker" in call_args
        assert "compose" in call_args
        assert "ps" in call_args
        assert "--format" in call_args
        assert "json" in call_args

    @pytest.mark.asyncio
    async def test_multiple_containers_returns_first(self) -> None:
        """With multiple containers, returns the first running one."""
        from eval.mcp_client import detect_container

        docker_output = json.dumps([
            {"Name": "agentinabox-reviewer-1", "State": "running"},
            {"Name": "agentinabox-db-1", "State": "running"},
        ])

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(docker_output.encode(), b"")
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            name = await detect_container()

        assert name == "agentinabox-reviewer-1"

    @pytest.mark.asyncio
    async def test_no_running_containers_raises(self) -> None:
        """RuntimeError when no containers are running."""
        from eval.mcp_client import detect_container

        docker_output = json.dumps([])

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(docker_output.encode(), b"")
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="[Nn]o.*container"):
                await detect_container()

    @pytest.mark.asyncio
    async def test_docker_compose_failure_raises(self) -> None:
        """RuntimeError when docker compose command fails."""
        from eval.mcp_client import detect_container

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"Cannot connect to Docker daemon")
        )
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="[Dd]ocker|[Ff]ailed"):
                await detect_container()

    @pytest.mark.asyncio
    async def test_filters_non_running_containers(self) -> None:
        """Only running containers are considered."""
        from eval.mcp_client import detect_container

        docker_output = json.dumps([
            {"Name": "stopped-box", "State": "exited"},
            {"Name": "running-box", "State": "running"},
        ])

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(docker_output.encode(), b"")
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            name = await detect_container()

        assert name == "running-box"

    @pytest.mark.asyncio
    async def test_all_exited_raises(self) -> None:
        """RuntimeError when all containers are exited."""
        from eval.mcp_client import detect_container

        docker_output = json.dumps([
            {"Name": "box-1", "State": "exited"},
            {"Name": "box-2", "State": "exited"},
        ])

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(docker_output.encode(), b"")
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="[Nn]o.*container"):
                await detect_container()

    @pytest.mark.asyncio
    async def test_malformed_json_raises_runtime_error_not_json_error(self) -> None:
        """Malformed `docker compose ps` output surfaces as RuntimeError.

        ``detect_container`` documents RuntimeError as its failure mode; a
        raw ``json.JSONDecodeError`` leaking through would break the
        documented contract and the CLI's exit-code handling.
        """
        from eval.mcp_client import detect_container

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"not json at all { { {", b"")
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="docker compose ps"):
                await detect_container()


# ===========================================================================
# TestRetryBackoff — _parse_tool_result error classification & _call_with_retry
# ===========================================================================


class TestRetryBackoff:
    """Retry/backoff behaviour for MCP tool calls (FR-013)."""

    # ---- _parse_tool_result: retryable errors ----

    def test_parse_raises_retryable_for_rate_limited(self) -> None:
        from eval.mcp_client import MCPRetryableError, _parse_tool_result

        result = _make_call_tool_result({"error": "rate_limited"})
        with pytest.raises(MCPRetryableError, match="rate_limited"):
            _parse_tool_result(result)

    def test_parse_raises_retryable_for_timeout(self) -> None:
        from eval.mcp_client import MCPRetryableError, _parse_tool_result

        result = _make_call_tool_result({"error": "timeout"})
        with pytest.raises(MCPRetryableError, match="timeout"):
            _parse_tool_result(result)

    # ---- _parse_tool_result: abort errors ----

    def test_parse_raises_abort_for_auth_failed(self) -> None:
        from eval.mcp_client import MCPAbortError, _parse_tool_result

        result = _make_call_tool_result({"error": "auth_failed"})
        with pytest.raises(MCPAbortError, match="auth_failed"):
            _parse_tool_result(result)

    def test_parse_raises_abort_for_unavailable(self) -> None:
        from eval.mcp_client import MCPAbortError, _parse_tool_result

        result = _make_call_tool_result({"error": "unavailable"})
        with pytest.raises(MCPAbortError, match="unavailable"):
            _parse_tool_result(result)

    # ---- _parse_tool_result: skip errors ----

    def test_parse_raises_skip_for_content_denied(self) -> None:
        from eval.mcp_client import MCPSkipCaseError, _parse_tool_result

        result = _make_call_tool_result({"error": "content_denied"})
        with pytest.raises(MCPSkipCaseError, match="content_denied"):
            _parse_tool_result(result)

    # ---- _call_with_retry: retryable with exponential backoff ----

    @pytest.mark.asyncio
    async def test_call_with_retry_retries_on_retryable_error(self) -> None:
        """Retryable errors trigger exponential backoff retries."""
        from eval.mcp_client import MCPRetryableError, _call_with_retry

        mock_session = AsyncMock()
        # Fail twice with retryable, then succeed on third attempt
        mock_session.call_tool = AsyncMock(
            side_effect=[
                _make_call_tool_result({"error": "rate_limited"}),
                _make_call_tool_result({"error": "timeout"}),
                _make_call_tool_result({"ok": True}),
            ]
        )

        with patch(
            "eval.mcp_client.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            result = await _call_with_retry(
                mock_session, "start_review", {"a": 1}, max_retries=3
            )

        assert result == {"ok": True}
        assert mock_session.call_tool.await_count == 3
        # Backoff: 2^0=1s, 2^1=2s
        assert mock_sleep.await_count == 2
        mock_sleep.assert_any_await(1)
        mock_sleep.assert_any_await(2)

    # ---- _call_with_retry: abort raises immediately ----

    @pytest.mark.asyncio
    async def test_call_with_retry_aborts_immediately(self) -> None:
        """MCPAbortError propagates without retry."""
        from eval.mcp_client import MCPAbortError, _call_with_retry

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result({"error": "auth_failed"})
        )

        with patch(
            "eval.mcp_client.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            with pytest.raises(MCPAbortError, match="auth_failed"):
                await _call_with_retry(
                    mock_session, "start_review", {}, max_retries=3
                )

        mock_session.call_tool.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    # ---- _call_with_retry: skip raises immediately ----

    @pytest.mark.asyncio
    async def test_call_with_retry_skips_immediately(self) -> None:
        """MCPSkipCaseError propagates without retry."""
        from eval.mcp_client import MCPSkipCaseError, _call_with_retry

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result({"error": "content_denied"})
        )

        with patch(
            "eval.mcp_client.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            with pytest.raises(MCPSkipCaseError, match="content_denied"):
                await _call_with_retry(
                    mock_session, "discuss", {}, max_retries=3
                )

        mock_session.call_tool.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    # ---- _call_with_retry: exhausted retries ----

    @pytest.mark.asyncio
    async def test_call_with_retry_raises_runtime_after_exhaustion(self) -> None:
        """RuntimeError raised after all retries are exhausted."""
        from eval.mcp_client import _call_with_retry

        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_make_call_tool_result({"error": "rate_limited"})
        )

        with patch(
            "eval.mcp_client.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            with pytest.raises(RuntimeError, match="failed after 2 retries"):
                await _call_with_retry(
                    mock_session, "start_review", {}, max_retries=2
                )

        assert mock_session.call_tool.await_count == 2
        assert mock_sleep.await_count == 2
