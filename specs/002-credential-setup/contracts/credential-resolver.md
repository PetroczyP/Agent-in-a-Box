# Credential Resolver Contract: Credential Setup (002)

## Module: `server/credential_resolver.py`

Resolves the active credential from the highest-priority available source.

## Interface

```python
from enum import Enum

class CredentialSource(str, Enum):
    DOCKER_SECRET = "docker_secret"
    ENV_VAR = "env_var"
    STORED = "stored"
    NONE = "none"


@dataclass
class ResolvedCredential:
    """In-memory only. Never persisted."""
    token: str
    source: CredentialSource


class CredentialResolver:
    """Resolves credentials from multiple sources in priority order."""

    def __init__(
        self,
        store: CredentialStore,
        docker_secret_path: str = "/run/secrets/github_token",
    ) -> None:
        """Initialize with credential store and Docker secret path."""

    def resolve(self) -> ResolvedCredential | None:
        """Resolve credential from highest-priority source.

        Priority order (FR-002):
          1. Docker secret (file at /run/secrets/github_token)
          2. Environment variable (GITHUB_TOKEN)
          3. Stored credential (decrypted from /data/)

        Returns None if no source provides a credential.
        Strips whitespace from all sources (Docker secrets often have trailing newlines).
        """

    def get_source(self) -> CredentialSource:
        """Return the source type without exposing the token.

        Useful for the credential status page (FR-009).
        """
```

## Behavior

- **Priority order**: Docker secret > env var > stored. First non-empty source wins.
- **Whitespace stripping**: All sources are `.strip()`'d before use (spec edge case: Docker secret trailing newline).
- **No validation**: Returns whatever token the source provides. Validation is `TokenValidator`'s job.
- **No caching**: Each `resolve()` call reads fresh from sources. This supports FR-010 (MCP freshness).
- **Logging**: Logs the resolved source type (e.g., "Credential resolved from docker_secret"). Never logs the token value (FR-007).

## Dependencies

- `CredentialStore` — for reading stored credentials
- `os.environ` — for `GITHUB_TOKEN`
- File I/O — for Docker secret file
