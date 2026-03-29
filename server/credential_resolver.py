"""Multi-source credential resolution — T009.

Resolves the active credential from the highest-priority available source.
Per contract: specs/002-credential-setup/contracts/credential-resolver.md
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum

from server.credential_store import CredentialStore

logger = logging.getLogger(__name__)


class CredentialSource(str, Enum):
    DOCKER_SECRET = "docker_secret"
    ENV_VAR = "env_var"
    STORED = "stored"
    NONE = "none"


@dataclass(frozen=True)
class ResolvedCredential:
    """In-memory only. Never persisted."""
    token: str
    source: CredentialSource

    def __post_init__(self):
        if not self.token:
            raise ValueError("ResolvedCredential requires a non-empty token")

    def __repr__(self) -> str:
        """Mask token in repr to prevent accidental exposure in logs/tracebacks."""
        return f"ResolvedCredential(token='***masked***', source={self.source!r})"


class CredentialResolver:
    """Resolves credentials from multiple sources in priority order."""

    def __init__(
        self,
        store: CredentialStore,
        docker_secret_path: str = "/run/secrets/github_token",
    ) -> None:
        self._store = store
        self._docker_secret_path = docker_secret_path

    def resolve(self) -> ResolvedCredential | None:
        """Resolve credential from highest-priority source.

        Priority order (FR-002):
          1. Docker secret (file at /run/secrets/github_token)
          2. Environment variable (GITHUB_TOKEN)
          3. Stored credential (decrypted from /data/)

        Returns None if no source provides a credential.
        """
        # 1. Docker secret
        token = self._read_docker_secret()
        if token:
            logger.info("Credential resolved from docker_secret")
            return ResolvedCredential(token=token, source=CredentialSource.DOCKER_SECRET)

        # 2. Environment variable
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if token:
            logger.info("Credential resolved from env_var")
            return ResolvedCredential(token=token, source=CredentialSource.ENV_VAR)

        # 3. Stored credential
        try:
            token = self._store.load()
        except OSError as e:
            logger.warning("Failed to read stored credential: %s", type(e).__name__)
            token = None
        if token:
            token = token.strip()
            if token:
                logger.info("Credential resolved from stored")
                return ResolvedCredential(token=token, source=CredentialSource.STORED)

        logger.info("No credential source available")
        return None

    def get_source(self) -> CredentialSource:
        """Return the source type without exposing the token."""
        if self._read_docker_secret():
            return CredentialSource.DOCKER_SECRET
        if os.environ.get("GITHUB_TOKEN", "").strip():
            return CredentialSource.ENV_VAR
        if self._store.has_stored_credential():
            return CredentialSource.STORED
        return CredentialSource.NONE

    def _read_docker_secret(self) -> str | None:
        """Read Docker secret file, strip whitespace. Returns None if missing/empty."""
        try:
            with open(self._docker_secret_path) as f:
                token = f.read().strip()
            return token if token else None
        except FileNotFoundError:
            return None
        except OSError as e:
            logger.warning(
                "Docker secret at %s exists but could not be read: %s",
                self._docker_secret_path, e,
            )
            return None
