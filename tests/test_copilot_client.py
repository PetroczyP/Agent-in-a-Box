"""Tests for Copilot client wrapper — T016."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.copilot_client import (
    CopilotAuthError,
    CopilotError,
    CopilotRateLimitError,
    CopilotReviewClient,
    CopilotTimeoutError,
    CopilotUnavailableError,
)


class TestCopilotReviewClientInit:
    async def test_start_sets_connected_when_sdk_available(self):
        client = CopilotReviewClient()
        assert client.is_connected is False

        async def mock_init_with_sdk():
            client._sdk_client = AsyncMock()
            client._available_models = [{"id": "gpt-4o", "name": "GPT-4o"}]

        with patch.object(client, "_init_sdk", side_effect=mock_init_with_sdk):
            await client.start(github_token="ghp_test123")
        assert client.is_connected is True

    async def test_start_requires_token(self):
        client = CopilotReviewClient()
        with pytest.raises(ValueError, match="github_token"):
            await client.start(github_token="")

    async def test_stop(self):
        client = CopilotReviewClient()

        async def mock_init_with_sdk():
            client._sdk_client = AsyncMock()
            client._available_models = [{"id": "gpt-4o", "name": "GPT-4o"}]

        with patch.object(client, "_init_sdk", side_effect=mock_init_with_sdk):
            await client.start(github_token="ghp_test123")
        await client.stop()
        assert client.is_connected is False


class TestSdkUnavailability:
    """B-1: Must fail, not silently degrade, when SDK is unavailable."""

    async def test_start_without_sdk_leaves_disconnected(self):
        """When SDK import fails, client must not report as connected."""
        client = CopilotReviewClient()

        async def mock_init_no_sdk():
            client._sdk_client = None
            client._available_models = []

        with patch.object(client, "_init_sdk", side_effect=mock_init_no_sdk):
            await client.start(github_token="ghp_test123")
        assert client.is_connected is False

    async def test_create_session_fails_when_sdk_unavailable(self):
        """create_review_session must raise, not return a placeholder."""
        client = CopilotReviewClient()
        client._connected = False
        client._sdk_client = None
        with pytest.raises(CopilotUnavailableError):
            await client.create_review_session(system_prompt="You are a reviewer")

    async def test_select_model_no_models_raises(self):
        """Must fail when no models available instead of falling back to gpt-4o."""
        client = CopilotReviewClient()
        client._available_models = []
        with pytest.raises(CopilotUnavailableError, match="No models available"):
            await client.select_model()


class TestStartupErrorPropagation:
    """H-1: Auth errors at startup must be re-raised at request time, not swallowed."""

    async def test_startup_auth_error_reraises_on_create_session(self):
        """If startup detected an auth error, create_review_session must raise CopilotAuthError."""
        client = CopilotReviewClient()
        client._startup_error = CopilotAuthError("bad token")
        with pytest.raises(CopilotAuthError, match="bad token"):
            await client.create_review_session(system_prompt="You are a reviewer")

    async def test_startup_error_takes_precedence_over_unavailable(self):
        """Startup auth error must be raised even when _sdk_client is None."""
        client = CopilotReviewClient()
        client._sdk_client = None
        client._startup_error = CopilotAuthError("invalid credentials")
        # Should raise CopilotAuthError, not CopilotUnavailableError
        with pytest.raises(CopilotAuthError):
            await client.create_review_session(system_prompt="test")

    async def test_successful_start_clears_previous_startup_error(self):
        """M-1: A successful start() must clear a stale _startup_error."""
        client = CopilotReviewClient()
        client._startup_error = CopilotAuthError("bad token")

        async def mock_init_with_sdk():
            client._sdk_client = AsyncMock()
            client._available_models = [{"id": "gpt-4o", "name": "GPT-4o"}]

        with patch.object(client, "_init_sdk", side_effect=mock_init_with_sdk):
            await client.start(github_token="ghp_good_token")

        assert client.is_connected is True
        assert client._startup_error is None
        # Should NOT raise the old auth error
        mock_session = AsyncMock()
        client._sdk_client.create_session = AsyncMock(return_value=mock_session)
        key = await client.create_review_session(system_prompt="test")
        assert key is not None


class TestModelSelection:
    async def test_select_model_auto(self):
        client = CopilotReviewClient()
        client._connected = True
        client._available_models = [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5"},
        ]
        model = await client.select_model()
        assert model is not None
        assert client.selected_model is not None

    async def test_select_model_explicit(self):
        client = CopilotReviewClient()
        client._connected = True
        client._available_models = [
            {"id": "gpt-4o", "name": "GPT-4o"},
        ]
        model = await client.select_model(model_id="gpt-4o")
        assert model == "gpt-4o"


class TestSessionCreation:
    async def test_create_review_session(self):
        client = CopilotReviewClient()
        client._connected = True
        client._selected_model = "gpt-4o"
        client._sdk_client = AsyncMock()
        mock_session = AsyncMock()
        client._sdk_client.create_session = AsyncMock(return_value=mock_session)

        key = await client.create_review_session(system_prompt="You are a reviewer")
        assert key is not None
        assert isinstance(key, str)

    async def test_create_session_passes_config_dict(self):
        """H-1: SDK create_session takes a config dict, not kwargs."""
        client = CopilotReviewClient()
        client._connected = True
        client._selected_model = "gpt-4o"
        client._sdk_client = AsyncMock()
        mock_session = AsyncMock()
        client._sdk_client.create_session = AsyncMock(return_value=mock_session)

        await client.create_review_session(
            system_prompt="You are a reviewer", model="custom-model"
        )

        # Verify create_session was called with a dict, not kwargs
        call_args = client._sdk_client.create_session.call_args
        config = call_args.args[0]
        assert isinstance(config, dict)
        assert callable(config["on_permission_request"])
        assert config["system_message"] == "You are a reviewer"
        assert config["model"] == "custom-model"

    def test_permission_handler_matches_sdk_contract(self):
        """H-1 R5: Permission handler must accept (request, invocation) and return approved result."""
        handler = CopilotReviewClient._approve_all_permissions
        # Must accept two arguments like PermissionHandler.approve_all
        mock_request = MagicMock()
        mock_invocation = {"session_id": "test-session"}
        result = handler(mock_request, mock_invocation)
        # Must return PermissionRequestResult(kind="approved") or equivalent dict
        if hasattr(result, "kind"):
            assert result.kind == "approved"
        else:
            assert result["kind"] == "approved"


class TestErrorClassification:
    def test_copilot_auth_error_is_not_retryable(self):
        err = CopilotAuthError("bad token")
        assert err.retryable is False

    def test_copilot_timeout_error_is_retryable(self):
        err = CopilotTimeoutError("timed out")
        assert err.retryable is True

    def test_copilot_rate_limit_error_is_retryable(self):
        err = CopilotRateLimitError("rate limited")
        assert err.retryable is True

    def test_copilot_unavailable_error_is_not_retryable(self):
        err = CopilotUnavailableError("model gone")
        assert err.retryable is False

    def test_base_error_hierarchy(self):
        assert issubclass(CopilotAuthError, CopilotError)
        assert issubclass(CopilotTimeoutError, CopilotError)
        assert issubclass(CopilotRateLimitError, CopilotError)
        assert issubclass(CopilotUnavailableError, CopilotError)


def _mock_session_event(content: str) -> MagicMock:
    """Create a mock SessionEvent with data.content."""
    event = MagicMock()
    event.data.content = content
    return event


class TestSendReview:
    async def test_send_review_returns_response(self):
        client = CopilotReviewClient()
        client._connected = True
        client._sessions = {"key-1": AsyncMock()}
        client._sessions["key-1"].send_and_wait = AsyncMock(
            return_value=_mock_session_event("review response")
        )

        response = await client.send_review("key-1", prompt="Review this code")
        assert response == "review response"

    async def test_send_followup_returns_response(self):
        client = CopilotReviewClient()
        client._connected = True
        client._sessions = {"key-1": AsyncMock()}
        client._sessions["key-1"].send_and_wait = AsyncMock(
            return_value=_mock_session_event("followup response")
        )

        response = await client.send_followup("key-1", prompt="I disagree")
        assert response == "followup response"

    async def test_send_review_handles_none_event(self):
        """send_and_wait can return None — must return empty string."""
        client = CopilotReviewClient()
        client._connected = True
        client._sessions = {"key-1": AsyncMock()}
        client._sessions["key-1"].send_and_wait = AsyncMock(return_value=None)

        response = await client.send_review("key-1", prompt="Review this code")
        assert response == ""

    async def test_send_review_session_not_found(self):
        """Must raise CopilotError for unknown session key."""
        client = CopilotReviewClient()
        client._sessions = {}
        with pytest.raises(CopilotError, match="not found"):
            await client.send_review("nonexistent", prompt="hello")

    async def test_send_review_timeout_raises_copilot_timeout(self):
        """Spec edge case: timeout on review → retryable CopilotTimeoutError."""
        import asyncio as _asyncio

        client = CopilotReviewClient()
        client._sessions = {"key-1": AsyncMock()}
        client._sessions["key-1"].send_and_wait = AsyncMock(
            side_effect=_asyncio.TimeoutError("timed out")
        )

        with pytest.raises(CopilotTimeoutError):
            await client.send_review("key-1", prompt="hello")

    async def test_send_review_event_with_no_data(self):
        """Event with no data attribute → empty string."""
        client = CopilotReviewClient()
        client._sessions = {"key-1": AsyncMock()}
        event = MagicMock(spec=[])  # no 'data' attribute
        client._sessions["key-1"].send_and_wait = AsyncMock(return_value=event)

        response = await client.send_review("key-1", prompt="hello")
        assert response == ""

    async def test_send_review_event_with_non_string_content(self):
        """Event data.content is not a string → empty string."""
        client = CopilotReviewClient()
        client._sessions = {"key-1": AsyncMock()}
        event = MagicMock()
        event.data.content = 12345  # not a string
        client._sessions["key-1"].send_and_wait = AsyncMock(return_value=event)

        response = await client.send_review("key-1", prompt="hello")
        assert response == ""


class TestStopEdgeCases:
    async def test_stop_clears_startup_error(self):
        """stop() must clear _startup_error so client can be reused."""
        client = CopilotReviewClient()
        client._startup_error = CopilotAuthError("old error")
        await client.stop()
        assert client._startup_error is None

    async def test_stop_with_force_stop_fallback(self):
        """If stop() raises, must fall back to force_stop()."""
        client = CopilotReviewClient()
        mock_sdk = AsyncMock()
        mock_sdk.stop = AsyncMock(side_effect=RuntimeError("stop failed"))
        mock_sdk.force_stop = AsyncMock()
        client._sdk_client = mock_sdk
        client._connected = True

        await client.stop()

        mock_sdk.force_stop.assert_awaited_once()
        assert client.is_connected is False

    async def test_stop_clears_sessions(self):
        """stop() must clear all tracked sessions."""
        client = CopilotReviewClient()
        client._sessions = {"k1": AsyncMock(), "k2": AsyncMock()}
        await client.stop()
        assert client._sessions == {}


class TestEventCollectionFallback:
    """Tests for the send() + on() fallback path when send_and_wait is unavailable."""

    async def test_fallback_path_collects_events(self):
        """When session has send() but not send_and_wait(), use event collection."""
        import asyncio as _asyncio

        client = CopilotReviewClient()

        # Create a session mock that has send() and on() but NOT send_and_wait
        session = MagicMock()
        del session.send_and_wait  # remove send_and_wait attribute

        collected_handler = None

        def mock_on(handler):
            nonlocal collected_handler
            collected_handler = handler
            return MagicMock()  # unsubscribe callable

        session.on = mock_on

        async def mock_send(options):
            # Simulate event delivery after send
            msg_event = MagicMock()
            msg_event.type = MagicMock()
            msg_event.type.value = "assistant_message"
            msg_event.data.content = "review result"
            collected_handler(msg_event)

            idle_event = MagicMock()
            idle_event.type = MagicMock()
            idle_event.type.value = "session_idle"
            collected_handler(idle_event)

        session.send = mock_send
        client._sessions = {"key-1": session}

        response = await client.send_review("key-1", prompt="hello", timeout=5.0)
        assert response == "review result"

    async def test_fallback_no_send_method_raises(self):
        """Session with neither send_and_wait nor send → CopilotUnavailableError."""
        client = CopilotReviewClient()
        session = MagicMock(spec=[])  # no send methods
        client._sessions = {"key-1": session}

        with pytest.raises(CopilotUnavailableError, match="no send method"):
            await client.send_review("key-1", prompt="hello")


class TestModelSelectionEdgeCases:
    async def test_select_first_available_when_no_preferred(self):
        """When no preferred model matches, select the first available."""
        client = CopilotReviewClient()
        client._available_models = [{"id": "some-obscure-model", "name": "Obscure"}]

        model = await client.select_model()
        assert model == "some-obscure-model"
        assert client.selected_model == "some-obscure-model"
