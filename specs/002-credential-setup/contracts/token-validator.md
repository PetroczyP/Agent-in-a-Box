# Token Validator Contract: Credential Setup (002)

## Module: `server/token_validator.py`

Validates GitHub PAT format, GitHub authentication, and Copilot API access.

## Interface

```python
class TokenValidationError(Exception):
    """Raised when token validation fails."""
    message: str
    error_type: str  # "format", "auth", "permission", "sdk"


class TokenValidator:
    """Validates tokens via: format → GitHub auth probe → Copilot access check."""

    def __init__(self, copilot_client: CopilotReviewClient) -> None:
        """Initialize with Copilot client for SDK validation."""

    def validate_format(self, token: str) -> None:
        """Check token prefix. Raises TokenValidationError(error_type="format") on failure.

        Accepts: github_pat_ prefix
        Rejects with verbose, actionable messages including URLs:
          - Empty/whitespace-only: "No token provided. ..."
          - ghp_: "Classic PATs (ghp_) are not supported. ..."
          - gho_: "OAuth app tokens (gho_) are not supported. ..."
          - ghs_: "GitHub App server-to-server tokens (ghs_) are not supported. ..."
          - ghu_: "GitHub App user-to-server tokens (ghu_) are not supported. ..."
          - Other: "Unrecognized token format. ..."
        See Error Messages section below for full message templates.
        """

    async def _probe_github_auth(self, token: str) -> bool | None:
        """Diagnostic probe: check if token authenticates to GitHub.

        Makes GET https://api.github.com/user with Bearer auth.
        This is a diagnostic probe for error classification, NOT a validation gate.

        Returns:
          - True: HTTP 2xx — token authenticates to GitHub (auth confirmed)
          - None: non-401, non-2xx (403 rate limit, 5xx, network error) — inconclusive

        Raises:
          - TokenValidationError(error_type="auth"): HTTP 401 — token is definitely
            expired, revoked, or invalid. Message: "Token authentication failed —
            the token may be expired or revoked. Please create a new fine-grained PAT."

        Only 401 is treated as a definitive auth failure. Other non-2xx responses
        are NOT mapped to auth — they are returned as None (inconclusive) so the
        Copilot check can still run and provide its own classification.

        Uses urllib.request (stdlib) via asyncio.to_thread(). No new dependencies.
        """

    async def validate_copilot_access(
        self, token: str, github_auth_confirmed: bool | None
    ) -> None:
        """Validate Copilot API access via list_models().

        Uses github_auth_confirmed (from _probe_github_auth) for error classification:

        If CopilotAuthError is raised by the SDK:
          - github_auth_confirmed is True → error_type="permission"
            Token works for GitHub but not Copilot. Message covers the likely causes:
            missing copilot_requests permission, no Copilot subscription, or policy.
          - github_auth_confirmed is None (probe was inconclusive) → error_type="auth"
            Cannot distinguish auth from permission. Combined message covers both.

        If ImportError or CopilotUnavailableError:
          - error_type="sdk" regardless of github_auth_confirmed

        Per R-4 confidence model: we only claim "permission" when we have high
        confidence (GitHub auth was confirmed). Otherwise we fall back honestly.
        """

    async def validate(self, token: str) -> None:
        """Full validation: format → GitHub auth probe → Copilot access.

        Orchestration:
        1. validate_format(token) — local prefix check, no network
        2. github_confirmed = _probe_github_auth(token)
           - Raises "auth" on 401 (short-circuit, definitive)
           - Returns True on 2xx (auth confirmed)
           - Returns None on other failures (inconclusive, proceed)
        3. validate_copilot_access(token, github_auth_confirmed=github_confirmed)
           - True → "permission" on CopilotAuthError
           - None → "auth" (combined msg) on CopilotAuthError
           - "sdk" on ImportError/CopilotUnavailableError regardless

        The GitHub auth probe is diagnostic, not a gate. If it's inconclusive
        (returned None), the Copilot check still runs. The probe only gates
        on HTTP 401, which is a definitive "token is invalid" signal.
        """
```

## Error Messages

Per R-4 confidence model and coordinator decision (Option A: verbose, diagnostic-style messages).
All messages MUST be chatty — list possible causes and include specific URLs and remediation steps.

### format — Empty/whitespace
```
No token provided. Please paste a GitHub fine-grained PAT.
To create one:
  • Go to github.com/settings/tokens?type=beta
  • Click "Generate new token"
  • Under Account permissions, enable 'copilot_requests'
  • Copy the token (starts with github_pat_) and paste it here
```

### format — Classic PAT (ghp_)
```
Classic PATs (ghp_) are not supported. AgentinaBox requires a fine-grained PAT
with the copilot_requests permission.
To create one:
  • Go to github.com/settings/tokens?type=beta
  • Click "Generate new token"
  • Under Account permissions, enable 'copilot_requests'
  • Copy the token (starts with github_pat_) and paste it here
Classic PATs cannot scope to individual permissions — a fine-grained PAT is required.
```

### format — OAuth app token (gho_)
```
OAuth app tokens (gho_) are not supported. AgentinaBox requires a personal access
token, not an OAuth token.
To create one:
  • Go to github.com/settings/tokens?type=beta
  • Click "Generate new token" (fine-grained)
  • Under Account permissions, enable 'copilot_requests'
  • Copy the token (starts with github_pat_) and paste it here
```

### format — GitHub App tokens (ghs_, ghu_)
```
GitHub App tokens (ghs_/ghu_) are not supported. AgentinaBox requires a personal
fine-grained PAT, not a GitHub App token.
To create one:
  • Go to github.com/settings/tokens?type=beta
  • Click "Generate new token" (fine-grained)
  • Under Account permissions, enable 'copilot_requests'
  • Copy the token (starts with github_pat_) and paste it here
```

### format — Unrecognized
```
Unrecognized token format. Expected a fine-grained PAT starting with 'github_pat_'.
To create one:
  • Go to github.com/settings/tokens?type=beta
  • Click "Generate new token" (fine-grained)
  • Under Account permissions, enable 'copilot_requests'
  • Copy the token (starts with github_pat_) and paste it here
```

### auth — High confidence (HTTP 401 from GET /user)
```
Token authentication failed — the token appears to be expired or revoked.
To fix this:
  • Go to github.com/settings/tokens
  • Check if the token is still active
  • If expired, create a new fine-grained PAT with the 'copilot_requests' permission
  • Paste the new token here to try again
```

### auth — Low confidence (inconclusive probe + Copilot failure)
```
Token validation failed — we couldn't determine the exact cause. This can happen if:
  • The token is expired or revoked
  • The token lacks the 'copilot_requests' permission
  • Your account doesn't have a Copilot subscription
  • GitHub or Copilot is temporarily unavailable
Try creating a new fine-grained PAT at github.com/settings/tokens with the
'copilot_requests' permission, and ensure you have an active Copilot subscription
at github.com/settings/copilot.
```

### permission — High confidence (confirmed GitHub auth + Copilot failure)
```
Token authenticates to GitHub but cannot access Copilot. Common causes:
  • Missing permission: Edit the token at github.com/settings/tokens and ensure
    'copilot_requests' is enabled
  • No Copilot subscription: Check your plan at github.com/settings/copilot
  • Organization policy: Your org admin may need to enable Copilot for your account
If you've verified all of the above and it still fails, try creating a fresh token.
```

### sdk
```
Copilot SDK unavailable — cannot validate token. This is a container configuration
issue, not a problem with your token. The Copilot CLI may not be installed or
failed to start.
To fix this:
  • Rebuild the container: docker compose build --no-cache
  • Restart it: docker compose up -d
  • Check container logs for errors: docker compose logs
If the issue persists, verify the Dockerfile includes the Copilot CLI installation
step (npm install -g @github/copilot).
For Copilot CLI setup details, see: docs.github.com/en/copilot
```

## Behavior

- **Three-step sequence**: format → GitHub auth probe → Copilot access. Format short-circuits. Auth probe short-circuits only on 401.
- **Diagnostic probe, not gate**: `_probe_github_auth()` is purely for error classification. If inconclusive, the Copilot check still runs. The validator never blocks on a non-401 GET /user failure.
- **Confidence-based classification**: "permission" is only claimed when we have strong evidence (GitHub auth confirmed + Copilot failed). "auth" fallback is used when evidence is insufficient.
- **Temporary client**: `validate_copilot_access()` creates a temporary `CopilotReviewClient`, calls `start(token)`, and stops it. The token is not stored by the validator.
- **No side effects**: Validation does not store, persist, or cache anything. The caller (`web_routes`) decides whether to store after successful validation.

## Dependencies

- `CopilotReviewClient` — for `start()` + `list_models()` validation
- `CopilotAuthError`, `CopilotUnavailableError` — for error classification
- `urllib.request` (stdlib) — for GitHub API auth probe
- `asyncio.to_thread` (stdlib) — to run synchronous urllib in async context
