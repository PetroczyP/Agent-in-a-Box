# Data Model — 002-credential-setup

## Entities

### StoredCredential

Persisted as encrypted file at `/data/credentials.enc`. Not a database record.

| Field | Type | Storage | Notes |
|-------|------|---------|-------|
| token | str | Fernet-encrypted in `/data/credentials.enc` | The raw PAT value. Never logged or displayed in plaintext. |
| created_at | datetime (ISO 8601) | Plaintext in `/data/credential_meta.json` | When the token was first stored. |
| last_validated_at | datetime (ISO 8601) | Plaintext in `/data/credential_meta.json` | When the token last passed `list_models()` validation. Updated on store and rotate. |

**File layout under `/data/`:**
```
/data/
  .fernet_key           # 44-byte Fernet key (chmod 600)
  credentials.enc       # Fernet-encrypted token bytes
  credential_meta.json  # {"created_at": "...", "last_validated_at": "..."}
```

**Rationale for separate metadata file**: The Fernet ciphertext is opaque binary. Metadata (timestamps) doesn't need encryption and is useful for the status page display without decrypting the token.

### CredentialSource (Enum)

```python
class CredentialSource(str, Enum):
    DOCKER_SECRET = "docker_secret"
    ENV_VAR = "env_var"
    STORED = "stored"
    NONE = "none"
```

### ResolvedCredential (Value Object)

In-memory only. Never persisted.

| Field | Type | Notes |
|-------|------|-------|
| token | str | The plaintext PAT value. |
| source | CredentialSource | Which source provided this token. |

### TokenValidationError (Exception)

| Field | Type | Notes |
|-------|------|-------|
| message | str | User-facing error message. |
| error_type | str | One of: `"format"`, `"auth"`, `"permission"`, `"sdk"`. |

**Error type mapping** (matches FR-005's 4 failure modes, see R-4 confidence model in research.md):
- `"format"` — token has rejected prefix or is empty (local check, no network)
- `"auth"` — token definitely fails GitHub authentication (`GET /user` returns 401 → expired/revoked), OR inconclusive fallback when GitHub auth probe returned non-401 non-2xx and Copilot also failed (combined message covers both auth and permission possibilities)
- `"permission"` — token confirmed to authenticate to GitHub (`GET /user` returned 2xx) but `list_models()` fails → cannot access Copilot. Verbose message lists common causes (missing `copilot_requests` permission, no Copilot subscription, org policy) with specific remediation steps and URLs
- `"sdk"` — Copilot SDK not installed or CLI won't start (ImportError / CopilotUnavailableError)

### NoCredentialError (CopilotError)

Raised internally when no credential source is available. Extends `CopilotError` (defined in `server/copilot_client.py`) so it fits the existing `_startup_error: CopilotError | None` type without changing the runtime error hierarchy. `retryable = False`. Does not escape the MCP tool boundary — caught by a dedicated handler in `start_review` and mapped to an error response payload.

| Field | Type | Notes |
|-------|------|-------|
| message | str | User-facing error message directing user to configure a credential. |

**Usage**: Set as `_startup_error` on `CopilotReviewClient` when `CredentialResolver.resolve()` returns `None` during MCP lifespan initialization. The existing `_startup_error` check in `create_review_session()` re-raises it via `CopilotError` base class. At the MCP tool boundary, only `start_review` reaches `create_review_session()` — a dedicated `except NoCredentialError` handler there maps it to `{"error": "no_credential", "message": str(e), "retryable": False}` (distinct from `"unavailable"` and `"auth_failed"`). Other tools never encounter this error: `discuss` calls `send_followup()` → `send_review()` on existing sessions (never checks `_startup_error`); `get_review_summary` and `list_sessions` access only the session store.

## Relationships

```
CredentialResolver --resolves--> ResolvedCredential
  reads from: Docker secret file, env var, CredentialStore

CredentialStore --manages--> StoredCredential
  encrypts/decrypts via: Fernet key

TokenValidator --validates--> token (str)
  step 1: validate_format() — local prefix check
  step 2: _probe_github_auth() — GET /user via urllib.request (diagnostic, not gate)
           returns True (auth confirmed), None (inconclusive), or raises auth on 401
  step 3: validate_copilot_access(token, github_auth_confirmed) — list_models()
           uses probe result for error classification
  raises: TokenValidationError (format | auth | permission | sdk)

Web Routes --uses--> CredentialResolver, CredentialStore, TokenValidator
MCP Server --uses--> CredentialResolver (read-only at startup)
  on resolve() == None → sets NoCredentialError as _startup_error
```
