"""Edge case tests for credential management — T025.

Covers:
1. Fernet key loss with existing credential file (AC-9)
2. Decryption failure (corrupted file)
3. Copilot SDK unavailable during validation
4. Concurrent store/load (atomic writes)
5. Stored credential becomes invalid between restarts (EC-2)
6. ResolvedCredential.__repr__ doesn't expose token (security audit T024)
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from server.copilot_client import (
    CopilotAuthError,
    CopilotReviewClient,
    CopilotUnavailableError,
)
from server.credential_resolver import CredentialResolver, ResolvedCredential, CredentialSource
from server.credential_store import CredentialStore
from server.token_validator import TokenValidationError, TokenValidator


# ---------------------------------------------------------------------------
# 1. Fernet key loss with existing credential file (AC-9)
#
# Existing tests in test_credential_store.py cover:
#   - test_load_returns_none_on_missing_key (basic key-loss)
# Additional edge cases added here:
# ---------------------------------------------------------------------------


class TestFernetKeyLoss:
    def test_key_loss_logs_warning_without_token_data(self, tmp_path, caplog):
        """AC-9: Key loss logs a warning that does NOT contain any token data."""
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_secret_value_12345678")

        # Delete the key
        os.remove(tmp_path / ".fernet_key")

        import logging
        with caplog.at_level(logging.WARNING):
            result = store.load()

        assert result is None
        # Warning was logged
        assert any("Fernet key missing" in r.message for r in caplog.records)
        # Token value does NOT appear in any log message
        for record in caplog.records:
            assert "github_pat_secret_value_12345678" not in record.message

    def test_key_loss_with_resolver_falls_through(self, tmp_path, monkeypatch):
        """AC-9 + resolver: Key loss means stored source unavailable, resolver returns None."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_stored_token_1234")

        # Delete the key
        os.remove(tmp_path / ".fernet_key")

        resolver = CredentialResolver(
            store=store,
            docker_secret_path=str(tmp_path / "nonexistent_secret"),
        )
        result = resolver.resolve()
        assert result is None
        # get_source() is a lightweight check (file existence, not decryptability),
        # so it reports STORED even though the key is lost and resolve() returns None.
        assert resolver.get_source() == CredentialSource.STORED

    def test_key_loss_metadata_still_readable(self, tmp_path):
        """Key loss does not affect metadata reading (metadata is not encrypted)."""
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_test1234")

        # Delete the key
        os.remove(tmp_path / ".fernet_key")

        # Metadata is JSON, not encrypted — still readable
        meta = store.get_metadata()
        assert meta is not None
        assert meta.created_at is not None

    def test_key_loss_allows_fresh_store(self, tmp_path):
        """After key loss, store() creates a new key and stores successfully."""
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_original_token")

        # Delete the key
        os.remove(tmp_path / ".fernet_key")

        # Cannot load old credential
        assert store.load() is None

        # Store a new credential — should create a new key
        store.store("github_pat_new_token_5678")
        assert store.load() == "github_pat_new_token_5678"
        assert os.path.exists(tmp_path / ".fernet_key")


# ---------------------------------------------------------------------------
# 2. Decryption failure (corrupted file)
#
# Existing tests in test_credential_store.py cover:
#   - test_load_returns_none_on_corrupted_file (basic corruption)
# Additional edge cases added here:
# ---------------------------------------------------------------------------


class TestDecryptionFailure:
    def test_corrupted_file_logs_warning_without_token_data(self, tmp_path, caplog):
        """Corrupted credential file logs a warning without exposing token data."""
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_secret_value_12345678")

        # Corrupt the encrypted file
        enc_path = tmp_path / "credentials.enc"
        enc_path.write_bytes(b"totally corrupted garbage data!!!")

        import logging
        with caplog.at_level(logging.WARNING):
            result = store.load()

        assert result is None
        # Warning was logged about decryption failure
        assert any("Failed to decrypt" in r.message for r in caplog.records)
        # Token value does NOT appear in any log message
        for record in caplog.records:
            assert "github_pat_secret_value_12345678" not in record.message

    def test_empty_encrypted_file_returns_none(self, tmp_path):
        """Empty credentials.enc file is handled gracefully."""
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_test1234")

        # Truncate the encrypted file to zero bytes
        enc_path = tmp_path / "credentials.enc"
        enc_path.write_bytes(b"")

        assert store.load() is None

    def test_partial_fernet_token_returns_none(self, tmp_path):
        """Partially valid Fernet ciphertext (truncated) returns None."""
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_test1234")

        # Read the encrypted file and truncate it partway
        enc_path = tmp_path / "credentials.enc"
        full_data = enc_path.read_bytes()
        enc_path.write_bytes(full_data[:len(full_data) // 2])

        assert store.load() is None

    def test_corruption_with_resolver_falls_through(self, tmp_path, monkeypatch):
        """Corrupted credential file means stored source unavailable."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_stored_token_1234")

        # Corrupt the file
        enc_path = tmp_path / "credentials.enc"
        enc_path.write_bytes(b"corrupted")

        resolver = CredentialResolver(
            store=store,
            docker_secret_path=str(tmp_path / "nonexistent_secret"),
        )
        result = resolver.resolve()
        assert result is None


# ---------------------------------------------------------------------------
# 3. Copilot SDK unavailable during validation
#
# Existing tests in test_token_validator.py cover:
#   - test_sdk_error_on_import_error
#   - test_sdk_error_on_unavailable
# Additional edge case: full validate() orchestration with SDK unavailable
# ---------------------------------------------------------------------------


class TestCopilotSdkUnavailable:
    @pytest.mark.asyncio
    async def test_full_validate_with_sdk_unavailable(self):
        """Full validation pipeline: format passes, auth probe passes, SDK fails.

        Verifies the "sdk" error type is produced with verbose container-level message.
        """
        mock_client = AsyncMock()
        mock_client.start = AsyncMock(
            side_effect=CopilotUnavailableError("CLI not found")
        )
        mock_client.stop = AsyncMock()

        validator = TokenValidator(copilot_client_factory=lambda: mock_client)

        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 200  # Auth probe succeeds
            with pytest.raises(TokenValidationError) as exc_info:
                await validator.validate("github_pat_valid_format_token")

        assert exc_info.value.error_type == "sdk"
        assert "container configuration issue" in exc_info.value.message
        assert "not a problem with your token" in exc_info.value.message
        assert "docker compose build --no-cache" in exc_info.value.message
        assert "docker compose logs" in exc_info.value.message
        assert "docs.github.com/en/copilot" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_sdk_error_does_not_echo_token(self):
        """SDK error message must NOT contain the submitted token value."""
        test_token = "github_pat_my_secret_pat_value_1234"
        mock_client = AsyncMock()
        mock_client.start = AsyncMock(
            side_effect=CopilotUnavailableError("CLI not found")
        )
        mock_client.stop = AsyncMock()

        validator = TokenValidator(copilot_client_factory=lambda: mock_client)

        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate_copilot_access(
                test_token, github_auth_confirmed=True
            )

        assert test_token not in exc_info.value.message


# ---------------------------------------------------------------------------
# 4. Concurrent store/load (atomic writes)
#
# Existing tests in test_credential_store.py cover:
#   - test_store_uses_atomic_writes (two sequential stores produce valid state)
# Additional edge cases for sequential store/load interleaving:
# ---------------------------------------------------------------------------


class TestAtomicWriteEdgeCases:
    def test_sequential_store_load_always_returns_latest(self, tmp_path):
        """Multiple sequential store+load cycles always return the latest value."""
        store = CredentialStore(data_dir=str(tmp_path))

        tokens = [f"github_pat_token_{i:04d}" for i in range(10)]
        for token in tokens:
            store.store(token)
            loaded = store.load()
            assert loaded == token, f"Expected {token}, got {loaded}"

    def test_store_does_not_leave_temp_files(self, tmp_path):
        """store() cleans up temporary files after atomic write."""
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_test1234")

        # No .tmp files should remain
        files = os.listdir(str(tmp_path))
        tmp_files = [f for f in files if f.endswith(".tmp")]
        assert tmp_files == [], f"Temp files left behind: {tmp_files}"

    def test_overwrite_preserves_created_at(self, tmp_path):
        """Storing a new token preserves original created_at timestamp."""
        store = CredentialStore(data_dir=str(tmp_path))
        store.store("github_pat_first_token")
        meta1 = store.get_metadata()
        assert meta1 is not None
        original_created = meta1.created_at

        store.store("github_pat_second_token")
        meta2 = store.get_metadata()
        assert meta2 is not None
        assert meta2.created_at == original_created
        # last_validated_at is None for both (never validated), just check consistency
        assert meta2.last_validated_at == meta1.last_validated_at


# ---------------------------------------------------------------------------
# 5. Stored credential becomes invalid between restarts (EC-2)
#
# When a stored credential was valid at store time but later becomes invalid
# (e.g., revoked on GitHub), the system must detect this on first MCP tool use
# and return "auth_failed" (not "no_credential" or "internal").
# ---------------------------------------------------------------------------


class TestStoredCredentialBecomesInvalid:
    @pytest.mark.asyncio
    async def test_auth_error_on_first_use_not_startup(self):
        """EC-2: Invalid stored credential detected at tool invocation, not startup.

        When CopilotReviewClient raises CopilotAuthError during start_review,
        the MCP handler maps it to error="auth_failed", not "no_credential"
        or "internal".
        """
        from server.mcp_server import start_review

        with patch("server.mcp_server._engine") as mock_engine:
            mock_engine.start_review = AsyncMock(
                side_effect=CopilotAuthError(
                    "Token authentication failed — the token appears to be "
                    "expired or revoked."
                )
            )

            response = await start_review(
                diff="--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n",
                files={"f.py": "new"},
            )

        assert response["error"] == "auth_failed"
        assert response["retryable"] is False
        # Verify it's NOT mapped to the wrong error types
        assert response["error"] != "no_credential"
        assert response["error"] != "internal"

    @pytest.mark.asyncio
    async def test_auth_error_message_does_not_expose_token(self):
        """EC-2 safety: Auth error messages must not contain plaintext tokens."""
        from server.mcp_server import start_review

        with patch("server.mcp_server._engine") as mock_engine:
            mock_engine.start_review = AsyncMock(
                side_effect=CopilotAuthError(
                    "Token authentication failed — the token appears to be "
                    "expired or revoked."
                )
            )

            response = await start_review(
                diff="--- a/f.py\n+++ b/f.py\n",
                files={"f.py": "pass"},
            )

        # Error message must not contain any PAT-like strings
        msg = response.get("message", "")
        assert "github_pat_" not in msg

    @pytest.mark.asyncio
    async def test_discuss_auth_error_maps_correctly(self):
        """EC-2 for discuss: Mid-session auth revocation maps to auth_failed."""
        from server.mcp_server import discuss

        with patch("server.mcp_server._engine") as mock_engine:
            mock_engine.discuss = AsyncMock(
                side_effect=CopilotAuthError(
                    "Token authentication failed during discussion."
                )
            )

            response = await discuss(
                session_id="s-123",
                message="Follow-up question",
            )

        assert response["error"] == "auth_failed"
        assert response["retryable"] is False
        assert response["error"] != "internal"


# ---------------------------------------------------------------------------
# 6. Security: ResolvedCredential.__repr__ doesn't expose token (T024 fix)
# ---------------------------------------------------------------------------


class TestResolvedCredentialRepr:
    def test_repr_does_not_contain_token(self):
        """ResolvedCredential repr must mask the token value."""
        token = "github_pat_my_super_secret_token_1234"
        cred = ResolvedCredential(token=token, source=CredentialSource.STORED)

        repr_str = repr(cred)
        assert token not in repr_str
        assert "***masked***" in repr_str
        assert "STORED" in repr_str

    def test_repr_for_all_sources(self):
        """Repr is safe regardless of credential source."""
        for source in CredentialSource:
            if source == CredentialSource.NONE:
                continue
            cred = ResolvedCredential(
                token="github_pat_secret_value", source=source
            )
            repr_str = repr(cred)
            assert "github_pat_secret_value" not in repr_str

    def test_token_still_accessible_via_attribute(self):
        """Despite masked repr, the actual token is accessible via .token."""
        token = "github_pat_actual_value_5678"
        cred = ResolvedCredential(token=token, source=CredentialSource.ENV_VAR)
        assert cred.token == token


# ---------------------------------------------------------------------------
# 7. Security: TokenValidator error messages don't echo submitted token
# ---------------------------------------------------------------------------


class TestTokenValidatorNoEcho:
    def test_format_errors_do_not_echo_token(self):
        """Format validation errors must not contain the submitted token."""
        validator = TokenValidator(copilot_client_factory=lambda: AsyncMock())

        bad_tokens = [
            "ghp_classic_secret_value",
            "gho_oauth_secret_value",
            "ghs_app_server_secret",
            "ghu_app_user_secret",
            "totally_random_secret_string",
        ]

        for token in bad_tokens:
            with pytest.raises(TokenValidationError) as exc_info:
                validator.validate_format(token)
            assert token not in exc_info.value.message, (
                f"Token '{token}' was echoed in error message"
            )

    @pytest.mark.asyncio
    async def test_auth_error_does_not_echo_token(self):
        """Auth validation error (401) must not contain the submitted token."""
        mock_client = AsyncMock()
        validator = TokenValidator(copilot_client_factory=lambda: mock_client)

        test_token = "github_pat_my_expired_secret_token"

        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 401
            with pytest.raises(TokenValidationError) as exc_info:
                await validator._probe_github_auth(test_token)

        assert test_token not in exc_info.value.message

    @pytest.mark.asyncio
    async def test_permission_error_does_not_echo_token(self):
        """Permission error must not contain the submitted token."""
        mock_client = AsyncMock()
        mock_client.start = AsyncMock(
            side_effect=CopilotAuthError("403 Forbidden")
        )
        mock_client.stop = AsyncMock()

        validator = TokenValidator(copilot_client_factory=lambda: mock_client)

        test_token = "github_pat_my_permission_denied_token"

        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate_copilot_access(
                test_token, github_auth_confirmed=True
            )

        assert test_token not in exc_info.value.message
