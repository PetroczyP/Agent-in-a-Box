"""Fernet-encrypted credential storage — T007.

Manages encrypted credential persistence in the Docker named volume (/data/).
Per contract: specs/002-credential-setup/contracts/credential-store.md
"""

from __future__ import annotations

import json
import logging
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


@dataclass
class CredentialMetadata:
    created_at: datetime
    last_validated_at: datetime


class CredentialStore:
    """Manages encrypted credential storage in /data/."""

    def __init__(self, data_dir: str = "/data") -> None:
        self._data_dir = data_dir
        self._key_path = os.path.join(data_dir, ".fernet_key")
        self._enc_path = os.path.join(data_dir, "credentials.enc")
        self._meta_path = os.path.join(data_dir, "credential_meta.json")

    def store(self, token: str) -> None:
        """Encrypt and persist a token. Creates Fernet key on first use."""
        key = self._get_or_create_key()
        f = Fernet(key)
        encrypted = f.encrypt(token.encode("utf-8"))

        # Atomic write for credentials.enc
        tmp_enc = self._enc_path + ".tmp"
        with open(tmp_enc, "wb") as fh:
            fh.write(encrypted)
        os.replace(tmp_enc, self._enc_path)

        # Write metadata
        now = datetime.now(timezone.utc).isoformat()
        existing_meta = self._read_meta_dict()
        meta = {
            "created_at": existing_meta.get("created_at", now),
            "last_validated_at": now,
        }
        tmp_meta = self._meta_path + ".tmp"
        with open(tmp_meta, "w") as fh:
            json.dump(meta, fh)
        os.replace(tmp_meta, self._meta_path)

    def load(self) -> str | None:
        """Load and decrypt the stored token. Returns None if unavailable."""
        if not os.path.exists(self._enc_path):
            return None
        if not os.path.exists(self._key_path):
            logger.warning("Fernet key missing but credentials.enc exists — treating as no credential")
            return None
        try:
            with open(self._key_path, "rb") as fh:
                key = fh.read()
            f = Fernet(key)
            with open(self._enc_path, "rb") as fh:
                encrypted = fh.read()
            return f.decrypt(encrypted).decode("utf-8")
        except (InvalidToken, ValueError) as e:
            logger.warning("Failed to decrypt credential: %s", type(e).__name__)
            return None

    def delete(self) -> None:
        """Remove stored credential files. Does NOT remove .fernet_key."""
        for path in (self._enc_path, self._meta_path):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def get_metadata(self) -> CredentialMetadata | None:
        """Read credential_meta.json. Returns None if file doesn't exist or is malformed."""
        meta = self._read_meta_dict()
        if not meta:
            return None
        try:
            return CredentialMetadata(
                created_at=datetime.fromisoformat(meta["created_at"]),
                last_validated_at=datetime.fromisoformat(meta["last_validated_at"]),
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("credential_meta.json has malformed data (%s) — returning None", type(e).__name__)
            return None

    def update_last_validated(self) -> None:
        """Update last_validated_at in credential_meta.json to now."""
        meta = self._read_meta_dict()
        if not meta:
            return
        meta["last_validated_at"] = datetime.now(timezone.utc).isoformat()
        tmp_meta = self._meta_path + ".tmp"
        with open(tmp_meta, "w") as fh:
            json.dump(meta, fh)
        os.replace(tmp_meta, self._meta_path)

    def has_stored_credential(self) -> bool:
        """Check if credentials.enc exists (without decrypting)."""
        return os.path.exists(self._enc_path)

    def _get_or_create_key(self) -> bytes:
        """Get existing Fernet key or generate a new one."""
        if os.path.exists(self._key_path):
            with open(self._key_path, "rb") as fh:
                return fh.read()
        key = Fernet.generate_key()
        # Atomic write with restrictive permissions
        tmp_key = self._key_path + ".tmp"
        fd = os.open(tmp_key, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as fh:
            fh.write(key)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_key, self._key_path)
        # Ensure final file has correct permissions
        os.chmod(self._key_path, stat.S_IRUSR | stat.S_IWUSR)
        return key

    def _read_meta_dict(self) -> dict:
        """Read credential_meta.json as dict. Returns {} if missing or corrupted."""
        if not os.path.exists(self._meta_path):
            return {}
        try:
            with open(self._meta_path) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("credential_meta.json is corrupted (%s) — treating as empty", type(e).__name__)
            return {}
