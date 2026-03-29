"""Tests for web routes — T011, T019 (RED).

Covers: GET / redirect to /setup when no credential (AC-1), GET / renders
status page, GET /setup renders wizard, GET /setup redirects when credential
exists, POST /setup validates + stores + redirects (AC-2), POST /setup with
invalid token re-renders with error (AC-3), mask_token() helper,
GET /settings shows masked token + source + form (US2-AS1), GET /settings
disables form for external sources (US2-AS4), GET /settings with no credential,
POST /settings/rotate with valid token replaces old + redirects (AC-5),
POST /settings/rotate with invalid token preserves old + shows error (US2-AS3),
POST /settings/rotate rejected when source is not stored,
POST /setup OSError handling, POST /settings/rotate OSError handling,
logging assertions.
Per contract: specs/002-credential-setup/contracts/web-routes.md
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from server.credential_resolver import CredentialSource, ResolvedCredential
from server.token_validator import TokenValidationError


def _create_test_app(resolver_result=None, resolver_source=CredentialSource.NONE):
    """Create a FastAPI test app with mocked dependencies."""
    from server.web_routes import create_router
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import os

    app = FastAPI()

    templates_dir = os.path.join(os.path.dirname(__file__), "..", "server", "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "..", "server", "static")

    templates = Jinja2Templates(directory=templates_dir)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    mock_store = MagicMock()
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = resolver_result
    mock_resolver.get_source.return_value = resolver_source
    mock_validator = AsyncMock()

    router = create_router(
        templates=templates,
        store=mock_store,
        resolver=mock_resolver,
        validator=mock_validator,
    )
    app.include_router(router)

    return app, mock_store, mock_resolver, mock_validator


class TestGetRoot:
    def test_redirects_to_setup_when_no_credential(self):
        """AC-1: No credential → redirect to /setup."""
        app, _, _, _ = _create_test_app(resolver_result=None)
        client = TestClient(app, follow_redirects=False)
        response = client.get("/")
        assert response.status_code in (302, 307)
        assert "/setup" in response.headers["location"]

    def test_renders_status_when_credential_exists(self):
        """Credential exists → render status page with source + masked token."""
        resolved = ResolvedCredential(token="github_pat_abcdefghXXXX", source=CredentialSource.STORED)
        app, _, _, _ = _create_test_app(resolver_result=resolved, resolver_source=CredentialSource.STORED)
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "XXXX" in response.text  # Masked token suffix visible
        assert "github_pat_abcdefghXXXX" not in response.text  # Full token NOT visible

    def test_flash_message_from_query_param(self):
        """?msg=saved → flash message displayed."""
        resolved = ResolvedCredential(token="github_pat_abcdefghXXXX", source=CredentialSource.STORED)
        app, _, _, _ = _create_test_app(resolver_result=resolved, resolver_source=CredentialSource.STORED)
        client = TestClient(app)
        response = client.get("/?msg=saved")
        assert response.status_code == 200
        assert "Token saved successfully" in response.text


class TestGetSetup:
    def test_renders_wizard_when_no_credential(self):
        """AC-1: No credential → setup wizard displayed."""
        app, _, _, _ = _create_test_app(resolver_result=None)
        client = TestClient(app)
        response = client.get("/setup")
        assert response.status_code == 200
        assert "github.com/settings/tokens" in response.text

    def test_redirects_when_credential_exists(self):
        """Credential already configured → redirect to /."""
        resolved = ResolvedCredential(token="github_pat_test1234", source=CredentialSource.STORED)
        app, _, _, _ = _create_test_app(resolver_result=resolved)
        client = TestClient(app, follow_redirects=False)
        response = client.get("/setup")
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/"


class TestPostSetup:
    def test_valid_token_stores_and_redirects(self):
        """AC-2: Valid token → validate, store, redirect to /?msg=saved."""
        app, mock_store, _, mock_validator = _create_test_app(resolver_result=None)
        mock_validator.validate = AsyncMock()  # No exception = success

        client = TestClient(app, follow_redirects=False)
        response = client.post("/setup", data={"token": "github_pat_valid_token"})
        assert response.status_code in (302, 303)
        assert "/?msg=saved" in response.headers["location"]
        mock_store.store.assert_called_once_with("github_pat_valid_token")

    def test_invalid_token_re_renders_with_error(self):
        """AC-3: Invalid token → re-render setup with error message."""
        app, mock_store, _, mock_validator = _create_test_app(resolver_result=None)
        mock_validator.validate = AsyncMock(
            side_effect=TokenValidationError("Classic PATs (ghp_) are not supported.", "format")
        )

        client = TestClient(app)
        response = client.post("/setup", data={"token": "ghp_bad_token"})
        assert response.status_code == 200
        assert "Classic PATs" in response.text
        mock_store.store.assert_not_called()

    def test_whitespace_stripped_before_store(self):
        """Token whitespace is stripped before storing."""
        app, mock_store, _, mock_validator = _create_test_app(resolver_result=None)
        mock_validator.validate = AsyncMock()
        client = TestClient(app, follow_redirects=False)
        response = client.post("/setup", data={"token": "  github_pat_valid_token  \n"})
        assert response.status_code in (302, 303)
        mock_store.store.assert_called_once_with("github_pat_valid_token")


class TestMaskToken:
    def test_masks_standard_token(self):
        from server.web_routes import mask_token
        result = mask_token("github_pat_abcdefghijklmnop1234")
        assert result.startswith("github_pat_")
        assert result.endswith("1234")
        assert "..." in result
        # Should NOT contain full token
        assert result != "github_pat_abcdefghijklmnop1234"

    def test_masks_classic_pat(self):
        """M-1: Classic PAT prefix derived from token, not hardcoded."""
        from server.web_routes import mask_token
        result = mask_token("ghp_abcdefghijklmnopqrstuvwxyz1234")
        assert result.startswith("ghp_")
        assert result.endswith("1234")
        assert "..." in result
        assert not result.startswith("github_pat_")

    def test_masks_oauth_token(self):
        """M-1: OAuth token prefix derived from token."""
        from server.web_routes import mask_token
        result = mask_token("gho_abcdefghijklmnopqrstuvwx5678")
        assert result.startswith("gho_")
        assert result.endswith("5678")

    def test_masks_unknown_prefix(self):
        """M-1: Unknown prefix shows first 4 chars."""
        from server.web_routes import mask_token
        result = mask_token("xyzw_abcdefghijklmnopqrst9999")
        assert result.startswith("xyzw")
        assert result.endswith("9999")
        assert "..." in result

    def test_masks_short_token(self):
        from server.web_routes import mask_token
        result = mask_token("github_pat_ab")
        # Even short tokens should be masked
        assert "..." in result

    def test_empty_input(self):
        from server.web_routes import mask_token
        assert mask_token("") == ""

    def test_none_input(self):
        from server.web_routes import mask_token
        assert mask_token(None) == ""

    def test_very_short_unknown_token(self):
        """mask_token handles very short tokens (<=4 chars) without known prefix."""
        from server.web_routes import mask_token
        assert mask_token("ab") == "..."
        assert mask_token("abcd") == "..."


class TestGetSettings:
    """T019: GET /settings tests."""

    def test_shows_masked_token_and_source_when_stored(self):
        """US2-AS1: Settings shows masked token + source + change form when source is stored."""
        resolved = ResolvedCredential(
            token="github_pat_abcdefghijklmnop1234",
            source=CredentialSource.STORED,
        )
        app, _, _, _ = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.STORED
        )
        client = TestClient(app)
        response = client.get("/settings")

        assert response.status_code == 200
        # Masked token visible (suffix)
        assert "1234" in response.text
        # Full token NOT visible
        assert "github_pat_abcdefghijklmnop1234" not in response.text
        # Source shown
        assert "Stored (encrypted)" in response.text
        # Change form visible (submit button present)
        assert 'action="/settings/rotate"' in response.text
        assert "Save" in response.text

    def test_disables_form_when_docker_secret(self):
        """US2-AS4: Form disabled when source is docker_secret."""
        resolved = ResolvedCredential(
            token="github_pat_docker_secret_token1234",
            source=CredentialSource.DOCKER_SECRET,
        )
        app, _, _, _ = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.DOCKER_SECRET
        )
        client = TestClient(app)
        response = client.get("/settings")

        assert response.status_code == 200
        # Source shown
        assert "Docker" in response.text
        # Change form NOT present
        assert 'action="/settings/rotate"' not in response.text
        # Externally managed explanation
        assert "managed externally" in response.text

    def test_disables_form_when_env_var(self):
        """US2-AS4: Form disabled when source is env_var."""
        resolved = ResolvedCredential(
            token="github_pat_env_var_token1234",
            source=CredentialSource.ENV_VAR,
        )
        app, _, _, _ = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.ENV_VAR
        )
        client = TestClient(app)
        response = client.get("/settings")

        assert response.status_code == 200
        # Source shown
        assert "Environment Variable" in response.text
        # Change form NOT present
        assert 'action="/settings/rotate"' not in response.text
        # Externally managed explanation
        assert "managed externally" in response.text

    def test_flash_message_rotated(self):
        """?msg=rotated → flash message displayed."""
        resolved = ResolvedCredential(
            token="github_pat_abcdefghijklmnop1234",
            source=CredentialSource.STORED,
        )
        app, _, _, _ = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.STORED
        )
        client = TestClient(app)
        response = client.get("/settings?msg=rotated")

        assert response.status_code == 200
        assert "Token rotated successfully" in response.text


class TestPostSettingsRotate:
    """T019: POST /settings/rotate tests."""

    def test_valid_token_replaces_and_redirects(self):
        """AC-5: Valid token → replaces old + redirects to /settings?msg=rotated."""
        resolved = ResolvedCredential(
            token="github_pat_old_token_abcd1234",
            source=CredentialSource.STORED,
        )
        app, mock_store, _, mock_validator = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.STORED
        )
        mock_validator.validate = AsyncMock()  # No exception = success

        client = TestClient(app, follow_redirects=False)
        response = client.post(
            "/settings/rotate", data={"token": "github_pat_new_valid_token"}
        )

        assert response.status_code == 303
        assert "/settings?msg=rotated" in response.headers["location"]
        mock_store.store.assert_called_once_with("github_pat_new_valid_token")

    def test_invalid_token_preserves_old_and_shows_error(self):
        """US2-AS3: Invalid token → preserves old token + shows error."""
        resolved = ResolvedCredential(
            token="github_pat_old_token_abcd1234",
            source=CredentialSource.STORED,
        )
        app, mock_store, _, mock_validator = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.STORED
        )
        mock_validator.validate = AsyncMock(
            side_effect=TokenValidationError(
                "Classic PATs (ghp_) are not supported.", "format"
            )
        )

        client = TestClient(app)
        response = client.post(
            "/settings/rotate", data={"token": "ghp_bad_token"}
        )

        assert response.status_code == 200
        assert "Classic PATs" in response.text
        # Old token still shown (masked)
        assert "1234" in response.text
        # store.store() NOT called — old token preserved
        mock_store.store.assert_not_called()

    def test_rejected_when_source_is_docker_secret(self):
        """Rotation rejected when source is docker_secret (externally managed)."""
        resolved = ResolvedCredential(
            token="github_pat_docker_secret_token1234",
            source=CredentialSource.DOCKER_SECRET,
        )
        app, mock_store, _, mock_validator = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.DOCKER_SECRET
        )

        client = TestClient(app)
        response = client.post(
            "/settings/rotate", data={"token": "github_pat_new_token"}
        )

        assert response.status_code == 200
        assert "managed externally" in response.text
        mock_store.store.assert_not_called()

    def test_rejected_when_source_is_env_var(self):
        """Rotation rejected when source is env_var (externally managed)."""
        resolved = ResolvedCredential(
            token="github_pat_env_var_token1234",
            source=CredentialSource.ENV_VAR,
        )
        app, mock_store, _, mock_validator = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.ENV_VAR
        )

        client = TestClient(app)
        response = client.post(
            "/settings/rotate", data={"token": "github_pat_new_token"}
        )

        assert response.status_code == 200
        assert "managed externally" in response.text
        mock_store.store.assert_not_called()

    def test_rotation_rejected_when_no_credential(self):
        """Rotation rejected when no credential is configured."""
        app, mock_store, _, _ = _create_test_app(
            resolver_result=None, resolver_source=CredentialSource.NONE
        )
        client = TestClient(app)
        response = client.post("/settings/rotate", data={"token": "github_pat_newtoken12345"})
        assert response.status_code == 200
        assert "No token is configured" in response.text
        mock_store.store.assert_not_called()


class TestGetSettingsNoCredential:
    """S-5: GET /settings with no credential configured."""

    def test_renders_without_error_when_no_credential(self):
        """Settings page renders successfully when no credential is configured."""
        app, _, _, _ = _create_test_app(
            resolver_result=None, resolver_source=CredentialSource.NONE
        )
        client = TestClient(app)
        response = client.get("/settings")

        assert response.status_code == 200
        # Source should show "Not configured"
        assert "not configured" in response.text.lower()
        # No rotation form should be visible (can_rotate is False)
        assert 'action="/settings/rotate"' not in response.text


class TestPostSetupOSError:
    """I-1: POST /setup when store.store() raises OSError."""

    def test_oserror_renders_error_not_500(self):
        """Store failure renders friendly error message, not a raw 500."""
        app, mock_store, _, mock_validator = _create_test_app(resolver_result=None)
        mock_validator.validate = AsyncMock()  # Validation passes
        mock_store.store.side_effect = OSError("Permission denied: /data/credential.enc")

        client = TestClient(app)
        response = client.post("/setup", data={"token": "github_pat_valid_token"})

        assert response.status_code == 200
        assert "/data/ volume is mounted and writable" in response.text
        # Should NOT be a 500
        assert response.status_code != 500

    def test_oserror_logs_error(self, caplog):
        """Store failure logs at ERROR level."""
        app, mock_store, _, mock_validator = _create_test_app(resolver_result=None)
        mock_validator.validate = AsyncMock()
        mock_store.store.side_effect = OSError("No space left on device")

        with caplog.at_level(logging.ERROR, logger="server.web_routes"):
            client = TestClient(app)
            client.post("/setup", data={"token": "github_pat_valid_token"})

        assert any("Failed to persist credential" in r.message for r in caplog.records)


class TestPostSettingsRotateOSError:
    """I-1: POST /settings/rotate when store.store() raises OSError."""

    def test_oserror_renders_error_not_500(self):
        """Store failure during rotation renders friendly error, not a raw 500."""
        resolved = ResolvedCredential(
            token="github_pat_old_token_abcd1234",
            source=CredentialSource.STORED,
        )
        app, mock_store, _, mock_validator = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.STORED
        )
        mock_validator.validate = AsyncMock()
        mock_store.store.side_effect = OSError("Read-only file system")

        client = TestClient(app)
        response = client.post(
            "/settings/rotate", data={"token": "github_pat_new_valid_token"}
        )

        assert response.status_code == 200
        assert "/data/ volume is mounted and writable" in response.text
        # Old masked token still visible
        assert "1234" in response.text

    def test_oserror_logs_error(self, caplog):
        """Store failure during rotation logs at ERROR level."""
        resolved = ResolvedCredential(
            token="github_pat_old_token_abcd1234",
            source=CredentialSource.STORED,
        )
        app, mock_store, _, mock_validator = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.STORED
        )
        mock_validator.validate = AsyncMock()
        mock_store.store.side_effect = OSError("Disk quota exceeded")

        with caplog.at_level(logging.ERROR, logger="server.web_routes"):
            client = TestClient(app)
            client.post(
                "/settings/rotate", data={"token": "github_pat_new_valid_token"}
            )

        assert any("Failed to persist credential" in r.message for r in caplog.records)


class TestLogging:
    """I-4: Verify logging events at appropriate levels."""

    def test_successful_setup_logs_info(self, caplog):
        """Successful token storage logs info message."""
        app, mock_store, _, mock_validator = _create_test_app(resolver_result=None)
        mock_validator.validate = AsyncMock()

        with caplog.at_level(logging.INFO, logger="server.web_routes"):
            client = TestClient(app, follow_redirects=False)
            client.post("/setup", data={"token": "github_pat_valid_token"})

        assert any(
            "Token stored successfully (source: setup wizard)" in r.message
            for r in caplog.records
        )

    def test_successful_rotation_logs_info(self, caplog):
        """Successful token rotation logs info message."""
        resolved = ResolvedCredential(
            token="github_pat_old_token_abcd1234",
            source=CredentialSource.STORED,
        )
        app, mock_store, _, mock_validator = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.STORED
        )
        mock_validator.validate = AsyncMock()

        with caplog.at_level(logging.INFO, logger="server.web_routes"):
            client = TestClient(app, follow_redirects=False)
            client.post(
                "/settings/rotate", data={"token": "github_pat_new_valid_token"}
            )

        assert any(
            "Token rotated successfully" in r.message for r in caplog.records
        )

    def test_validation_failure_logs_warning(self, caplog):
        """Validation failure logs warning with error_type (not the token)."""
        app, _, _, mock_validator = _create_test_app(resolver_result=None)
        mock_validator.validate = AsyncMock(
            side_effect=TokenValidationError("Bad format", "format")
        )

        with caplog.at_level(logging.WARNING, logger="server.web_routes"):
            client = TestClient(app)
            client.post("/setup", data={"token": "ghp_bad_token"})

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Token validation failed: format" in r.message for r in warning_records)
        # Token must NOT appear in any log message
        assert all("ghp_bad_token" not in r.message for r in caplog.records)

    def test_rotation_rejected_logs_warning(self, caplog):
        """Rotation rejection for external source logs warning."""
        resolved = ResolvedCredential(
            token="github_pat_docker_secret_token1234",
            source=CredentialSource.DOCKER_SECRET,
        )
        app, _, _, _ = _create_test_app(
            resolver_result=resolved, resolver_source=CredentialSource.DOCKER_SECRET
        )

        with caplog.at_level(logging.WARNING, logger="server.web_routes"):
            client = TestClient(app)
            client.post(
                "/settings/rotate", data={"token": "github_pat_new_token"}
            )

        assert any(
            "Rotation rejected: credential source is" in r.message
            for r in caplog.records
        )
