"""Tests for CredentialResolver — T008, T022, T023 (RED).

Covers: Docker secret > env var > stored priority (FR-002), whitespace stripping,
returns None when no source, get_source(), logging source without token (FR-007),
SC-004 integration tests for all 4 source priority combinations (T022),
Docker secret trailing whitespace stripping (T023).
Per contract: specs/002-credential-setup/contracts/credential-resolver.md
"""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock

import pytest

from server.credential_resolver import CredentialResolver, CredentialSource, ResolvedCredential


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.load.return_value = None
    store.has_stored_credential.return_value = False
    return store


@pytest.fixture
def resolver(mock_store, tmp_path):
    """Resolver with non-existent Docker secret path and mocked store."""
    return CredentialResolver(
        store=mock_store,
        docker_secret_path=str(tmp_path / "github_token"),
    )


class TestResolve:
    def test_docker_secret_highest_priority(self, mock_store, tmp_path, monkeypatch):
        """FR-002: Docker secret > env var > stored."""
        secret_path = tmp_path / "github_token"
        secret_path.write_text("github_pat_from_docker_secret")
        monkeypatch.setenv("GITHUB_TOKEN", "github_pat_from_env")
        mock_store.load.return_value = "github_pat_from_stored"

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_from_docker_secret"
        assert result.source == CredentialSource.DOCKER_SECRET

    def test_env_var_second_priority(self, mock_store, tmp_path, monkeypatch):
        """FR-002: env var used when no Docker secret."""
        monkeypatch.setenv("GITHUB_TOKEN", "github_pat_from_env")
        mock_store.load.return_value = "github_pat_from_stored"

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_from_env"
        assert result.source == CredentialSource.ENV_VAR

    def test_stored_credential_third_priority(self, mock_store, tmp_path, monkeypatch):
        """FR-002: stored credential used when no Docker secret or env var."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mock_store.load.return_value = "github_pat_from_stored"

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_from_stored"
        assert result.source == CredentialSource.STORED

    def test_returns_none_when_no_source(self, resolver, monkeypatch):
        """No source available → returns None."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        result = resolver.resolve()
        assert result is None

    def test_whitespace_stripping_docker_secret(self, mock_store, tmp_path, monkeypatch):
        """Edge case: Docker secrets often have trailing newlines."""
        secret_path = tmp_path / "github_token"
        secret_path.write_text("  github_pat_test1234  \n")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_test1234"

    def test_whitespace_stripping_env_var(self, resolver, monkeypatch):
        """Whitespace stripping on env var."""
        monkeypatch.setenv("GITHUB_TOKEN", "  github_pat_test1234  ")
        result = resolver.resolve()
        assert result is not None
        assert result.token == "github_pat_test1234"

    def test_whitespace_stripping_stored(self, mock_store, tmp_path, monkeypatch):
        """Whitespace stripping on stored credential."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mock_store.load.return_value = "  github_pat_test1234  "

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_test1234"

    def test_empty_docker_secret_skipped(self, mock_store, tmp_path, monkeypatch):
        """Empty Docker secret file (after stripping) → skip to next source."""
        secret_path = tmp_path / "github_token"
        secret_path.write_text("   \n")
        monkeypatch.setenv("GITHUB_TOKEN", "github_pat_from_env")

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        result = resolver.resolve()

        assert result is not None
        assert result.source == CredentialSource.ENV_VAR

    def test_empty_env_var_skipped(self, resolver, monkeypatch):
        """Empty env var → skip to stored."""
        monkeypatch.setenv("GITHUB_TOKEN", "")
        result = resolver.resolve()
        assert result is None


class TestGetSource:
    def test_returns_docker_secret(self, mock_store, tmp_path, monkeypatch):
        secret_path = tmp_path / "github_token"
        secret_path.write_text("github_pat_test1234")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        assert resolver.get_source() == CredentialSource.DOCKER_SECRET

    def test_returns_env_var(self, resolver, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "github_pat_test1234")
        assert resolver.get_source() == CredentialSource.ENV_VAR

    def test_returns_stored(self, mock_store, tmp_path, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mock_store.load.return_value = "github_pat_test1234"
        mock_store.has_stored_credential.return_value = True
        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        assert resolver.get_source() == CredentialSource.STORED

    def test_returns_none(self, resolver, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert resolver.get_source() == CredentialSource.NONE


class TestSourcePriorityIntegration:
    """T022: SC-004 integration tests — all 4 credential source combinations.

    These tests explicitly verify the priority order documented in SC-004:
    1. Docker secret + env var → Docker secret wins (US3-AS1)
    2. env var only → env var used (US3-AS2)
    3. stored only → stored used (US3-AS3)
    4. none → returns None (US3-AS4)
    """

    def test_docker_secret_beats_env_var(self, mock_store, tmp_path, monkeypatch):
        """SC-004 combo 1 (US3-AS1): Docker secret + env var → Docker secret wins."""
        secret_path = tmp_path / "github_token"
        secret_path.write_text("github_pat_from_docker")
        monkeypatch.setenv("GITHUB_TOKEN", "github_pat_from_env")
        # No stored credential
        mock_store.load.return_value = None

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_from_docker"
        assert result.source == CredentialSource.DOCKER_SECRET
        # get_source() agrees
        assert resolver.get_source() == CredentialSource.DOCKER_SECRET

    def test_env_var_only(self, mock_store, tmp_path, monkeypatch):
        """SC-004 combo 2 (US3-AS2): env var only (no Docker secret, no stored) → env var used."""
        monkeypatch.setenv("GITHUB_TOKEN", "github_pat_from_env")
        mock_store.load.return_value = None

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_from_env"
        assert result.source == CredentialSource.ENV_VAR
        assert resolver.get_source() == CredentialSource.ENV_VAR

    def test_stored_only(self, mock_store, tmp_path, monkeypatch):
        """SC-004 combo 3 (US3-AS3): stored only (no Docker secret, no env var) → stored used."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mock_store.load.return_value = "github_pat_from_stored"
        mock_store.has_stored_credential.return_value = True

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_from_stored"
        assert result.source == CredentialSource.STORED
        assert resolver.get_source() == CredentialSource.STORED

    def test_no_source_returns_none(self, mock_store, tmp_path, monkeypatch):
        """SC-004 combo 4 (US3-AS4): no credential source → returns None."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mock_store.load.return_value = None

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        result = resolver.resolve()

        assert result is None
        assert resolver.get_source() == CredentialSource.NONE


class TestDockerSecretWhitespaceStripping:
    """T023: Docker secret trailing whitespace stripping edge cases.

    Docker secret files commonly have trailing newlines appended by the
    filesystem or by tooling that creates them. The resolver MUST strip
    all leading/trailing whitespace before use.
    """

    def test_trailing_newline_stripped(self, mock_store, tmp_path, monkeypatch):
        """Single trailing newline (most common Docker secret artifact)."""
        secret_path = tmp_path / "github_token"
        secret_path.write_text("github_pat_test1234\n")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_test1234"
        assert result.source == CredentialSource.DOCKER_SECRET

    def test_multiple_trailing_newlines_stripped(self, mock_store, tmp_path, monkeypatch):
        """Multiple trailing newlines stripped."""
        secret_path = tmp_path / "github_token"
        secret_path.write_text("github_pat_test1234\n\n\n")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_test1234"

    def test_leading_and_trailing_whitespace_stripped(self, mock_store, tmp_path, monkeypatch):
        """Both leading and trailing whitespace/newlines stripped."""
        secret_path = tmp_path / "github_token"
        secret_path.write_text("  \t github_pat_test1234 \t \n")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        result = resolver.resolve()

        assert result is not None
        assert result.token == "github_pat_test1234"

    def test_whitespace_only_secret_skipped(self, mock_store, tmp_path, monkeypatch):
        """Whitespace-only Docker secret file is treated as empty/missing."""
        secret_path = tmp_path / "github_token"
        secret_path.write_text("  \n\t\n  ")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mock_store.load.return_value = None

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        result = resolver.resolve()

        assert result is None


class TestResolverLogging:
    """L-1: Verify resolver logs source type without exposing token values (SC-003, FR-007)."""

    TOKEN = "github_pat_SECRETVALUE1234567890"

    def test_docker_secret_logs_source(self, mock_store, tmp_path, monkeypatch, caplog):
        secret_path = tmp_path / "github_token"
        secret_path.write_text(self.TOKEN)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))
        with caplog.at_level(logging.INFO, logger="server.credential_resolver"):
            resolver.resolve()

        assert "docker_secret" in caplog.text
        assert self.TOKEN not in caplog.text

    def test_env_var_logs_source(self, mock_store, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv("GITHUB_TOKEN", self.TOKEN)

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        with caplog.at_level(logging.INFO, logger="server.credential_resolver"):
            resolver.resolve()

        assert "env_var" in caplog.text
        assert self.TOKEN not in caplog.text

    def test_stored_logs_source(self, mock_store, tmp_path, monkeypatch, caplog):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mock_store.load.return_value = self.TOKEN

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        with caplog.at_level(logging.INFO, logger="server.credential_resolver"):
            resolver.resolve()

        assert "stored" in caplog.text
        assert self.TOKEN not in caplog.text

    def test_no_source_logs_message(self, resolver, monkeypatch, caplog):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        with caplog.at_level(logging.INFO, logger="server.credential_resolver"):
            resolver.resolve()

        assert "No credential source available" in caplog.text
        assert self.TOKEN not in caplog.text


class TestDockerSecretOSError:
    """C-3: _read_docker_secret catches OSError broadly, not just FileNotFoundError."""

    def test_permission_error_logs_warning_returns_none(self, mock_store, tmp_path, monkeypatch, caplog):
        """PermissionError on Docker secret logs warning, returns None, resolver continues."""
        import builtins

        secret_path = tmp_path / "github_token"
        monkeypatch.setenv("GITHUB_TOKEN", "github_pat_from_env")

        resolver = CredentialResolver(store=mock_store, docker_secret_path=str(secret_path))

        # Patch open() to raise PermissionError only for the secret path.
        # (chmod(0o000) is runner-dependent — fails under root / on Windows)
        _real_open = builtins.open

        def _open_permission_denied(path, *args, **kwargs):
            if str(path) == str(secret_path):
                raise PermissionError("Permission denied")
            return _real_open(path, *args, **kwargs)

        monkeypatch.setattr("builtins.open", _open_permission_denied)

        with caplog.at_level(logging.WARNING, logger="server.credential_resolver"):
            result = resolver.resolve()

        # Should fall through to env var, not crash
        assert result is not None
        assert result.source == CredentialSource.ENV_VAR
        assert "could not be read" in caplog.text


class TestStoreLoadOSError:
    """C-3 (Finding 6): resolve() catches OSError from store.load()."""

    def test_store_load_oserror_logs_warning_continues(self, mock_store, tmp_path, monkeypatch, caplog):
        """OSError from store.load() is caught; resolver returns None gracefully."""
        mock_store.load.side_effect = OSError("disk read error")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        resolver = CredentialResolver(
            store=mock_store,
            docker_secret_path=str(tmp_path / "nonexistent"),
        )
        with caplog.at_level(logging.WARNING, logger="server.credential_resolver"):
            result = resolver.resolve()

        assert result is None
        assert "Failed to read stored credential" in caplog.text


class TestResolvedCredentialFrozen:
    """S-3: ResolvedCredential is frozen and rejects empty tokens."""

    def test_empty_token_raises_value_error(self):
        """ResolvedCredential with empty string token raises ValueError."""
        with pytest.raises(ValueError, match="non-empty token"):
            ResolvedCredential(token="", source=CredentialSource.ENV_VAR)

    def test_frozen_prevents_mutation(self):
        """ResolvedCredential attributes cannot be modified after creation."""
        cred = ResolvedCredential(token="github_pat_test", source=CredentialSource.ENV_VAR)
        with pytest.raises(AttributeError):
            cred.token = "github_pat_other"

    def test_valid_token_succeeds(self):
        """ResolvedCredential with valid token creates normally."""
        cred = ResolvedCredential(token="github_pat_test", source=CredentialSource.STORED)
        assert cred.token == "github_pat_test"
        assert cred.source == CredentialSource.STORED
