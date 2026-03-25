# Credential Store Contract: Credential Setup (002)

## Module: `server/credential_store.py`

Manages Fernet-encrypted credential persistence in the Docker named volume (`/data/`).

## Interface

```python
class CredentialStore:
    """Manages encrypted credential storage in /data/."""

    def __init__(self, data_dir: str = "/data") -> None:
        """Initialize with data directory path."""

    def store(self, token: str) -> None:
        """Encrypt and persist a token. Creates Fernet key on first use.

        Writes:
          - /data/.fernet_key (if not exists, chmod 600)
          - /data/credentials.enc (Fernet-encrypted token bytes)
          - /data/credential_meta.json (created_at, last_validated_at as ISO 8601)

        Uses os.replace() for atomic writes to minimize corruption risk.
        """

    def load(self) -> str | None:
        """Load and decrypt the stored token. Returns None if unavailable.

        Returns None when:
          - No credentials.enc file exists
          - No .fernet_key file exists (key loss — per spec edge case)
          - Decryption fails (corrupted file or key mismatch)

        Logs a warning (without token data) on key loss or decryption failure.
        """

    def delete(self) -> None:
        """Remove stored credential files (credentials.enc + credential_meta.json).

        Does NOT remove .fernet_key — it may be reused for future storage.
        """

    def get_metadata(self) -> CredentialMetadata | None:
        """Read credential_meta.json. Returns None if file doesn't exist."""

    def update_last_validated(self) -> None:
        """Update last_validated_at in credential_meta.json to now."""

    def has_stored_credential(self) -> bool:
        """Check if credentials.enc exists (without decrypting)."""
```

## Data Types

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CredentialMetadata:
    created_at: datetime
    last_validated_at: datetime
```

## Behavior

- **Fernet key lifecycle**: Auto-generated via `Fernet.generate_key()` on first `store()` call. Persisted at `/data/.fernet_key` with `chmod 600`. Never regenerated — loss invalidates all stored credentials.
- **Atomic writes**: All file writes use a temp file + `os.replace()` pattern.
- **No validation**: This module encrypts/decrypts only. Token validation is `TokenValidator`'s responsibility.
- **Thread safety**: Not required. Web server is single-process (uvicorn). MCP is per-invocation.

## Error Handling

- Key loss (`.fernet_key` missing but `credentials.enc` exists): log warning, return `None` from `load()`.
- Decryption failure (`InvalidToken` from Fernet): log warning, return `None` from `load()`.
- File I/O errors: propagate as-is (callers handle).

## Dependencies

- `cryptography.fernet.Fernet` — encryption/decryption
- Standard library: `os`, `json`, `datetime`
