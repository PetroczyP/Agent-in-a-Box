"""Token validator — T012.

Validates GitHub PAT format, GitHub authentication, and Copilot API access.
Three-step sequence: format check -> GitHub auth probe -> Copilot access check.

Per contracts/token-validator.md: verbose, diagnostic-style error messages
with specific URLs and remediation steps for each error type.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.request
import urllib.error
from typing import Callable

logger = logging.getLogger(__name__)

from server.copilot_client import (
    CopilotAuthError,
    CopilotReviewClient,
    CopilotUnavailableError,
)


class TokenValidationError(Exception):
    """Raised when token validation fails."""

    def __init__(self, message: str, error_type: str) -> None:
        self.message = message
        self.error_type = error_type
        super().__init__(message)


# --- Error message templates (verbatim from contract) ---

_MSG_FORMAT_EMPTY = """\
No token provided. Please paste a GitHub fine-grained PAT.
To create one:
  \u2022 Go to github.com/settings/tokens?type=beta
  \u2022 Click "Generate new token"
  \u2022 Under Account permissions, enable 'copilot_requests'
  \u2022 Copy the token (starts with github_pat_) and paste it here"""

_MSG_FORMAT_CLASSIC = """\
Classic PATs (ghp_) are not supported. AgentinaBox requires a fine-grained PAT
with the copilot_requests permission.
To create one:
  \u2022 Go to github.com/settings/tokens?type=beta
  \u2022 Click "Generate new token"
  \u2022 Under Account permissions, enable 'copilot_requests'
  \u2022 Copy the token (starts with github_pat_) and paste it here
Classic PATs cannot scope to individual permissions \u2014 a fine-grained PAT is required."""

_MSG_FORMAT_OAUTH = """\
OAuth app tokens (gho_) are not supported. AgentinaBox requires a personal access
token, not an OAuth token.
To create one:
  \u2022 Go to github.com/settings/tokens?type=beta
  \u2022 Click "Generate new token" (fine-grained)
  \u2022 Under Account permissions, enable 'copilot_requests'
  \u2022 Copy the token (starts with github_pat_) and paste it here"""

_MSG_FORMAT_GITHUB_APP = """\
GitHub App tokens (ghs_/ghu_) are not supported. AgentinaBox requires a personal
fine-grained PAT, not a GitHub App token.
To create one:
  \u2022 Go to github.com/settings/tokens?type=beta
  \u2022 Click "Generate new token" (fine-grained)
  \u2022 Under Account permissions, enable 'copilot_requests'
  \u2022 Copy the token (starts with github_pat_) and paste it here"""

_MSG_FORMAT_UNRECOGNIZED = """\
Unrecognized token format. Expected a fine-grained PAT starting with 'github_pat_'.
To create one:
  \u2022 Go to github.com/settings/tokens?type=beta
  \u2022 Click "Generate new token" (fine-grained)
  \u2022 Under Account permissions, enable 'copilot_requests'
  \u2022 Copy the token (starts with github_pat_) and paste it here"""

_MSG_AUTH_HIGH_CONFIDENCE = """\
Token authentication failed \u2014 the token appears to be expired or revoked.
To fix this:
  \u2022 Go to github.com/settings/tokens
  \u2022 Check if the token is still active
  \u2022 If expired, create a new fine-grained PAT with the 'copilot_requests' permission
  \u2022 Paste the new token here to try again"""

_MSG_AUTH_LOW_CONFIDENCE = """\
Token validation failed \u2014 we couldn't determine the exact cause. This can happen if:
  \u2022 The token is expired or revoked
  \u2022 The token lacks the 'copilot_requests' permission
  \u2022 Your account doesn't have a Copilot subscription
  \u2022 GitHub or Copilot is temporarily unavailable
Try creating a new fine-grained PAT at github.com/settings/tokens with the
'copilot_requests' permission, and ensure you have an active Copilot subscription
at github.com/settings/copilot."""

_MSG_PERMISSION = """\
Token authenticates to GitHub but cannot access Copilot. Common causes:
  \u2022 Missing permission: Edit the token at github.com/settings/tokens and ensure
    'copilot_requests' is enabled
  \u2022 No Copilot subscription: Check your plan at github.com/settings/copilot
  \u2022 Organization policy: Your org admin may need to enable Copilot for your account
If you've verified all of the above and it still fails, try creating a fresh token."""

_MSG_SDK = (
    "Copilot SDK unavailable \u2014 cannot validate token. "
    "This is a container configuration issue, not a problem with your token. "
    "The Copilot CLI may not be installed or failed to start.\n"
    "To fix this:\n"
    "  \u2022 Rebuild the container: docker compose build --no-cache\n"
    "  \u2022 Restart it: docker compose up -d\n"
    "  \u2022 Check container logs for errors: docker compose logs\n"
    "If the issue persists, verify the Dockerfile includes the Copilot CLI installation\n"
    "step (npm install -g @github/copilot).\n"
    "For Copilot CLI setup details, see: docs.github.com/en/copilot"
)


def _http_get_status(url: str, token: str) -> int:
    """Make a GET request with Bearer auth and return the HTTP status code.

    Uses urllib.request (stdlib). Module-level function for easy mocking in tests.
    """
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", "AgentinaBox-TokenValidator")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


class TokenValidator:
    """Validates tokens via: format -> GitHub auth probe -> Copilot access check."""

    def __init__(
        self,
        copilot_client_factory: Callable[[], CopilotReviewClient],
    ) -> None:
        """Initialize with a factory callable that creates CopilotReviewClient instances."""
        self._copilot_client_factory = copilot_client_factory

    def validate_format(self, token: str) -> None:
        """Check token prefix. Raises TokenValidationError(error_type="format") on failure.

        Accepts: github_pat_ prefix.
        Rejects with verbose, actionable messages including URLs.
        """
        if not token or not token.strip():
            raise TokenValidationError(_MSG_FORMAT_EMPTY, error_type="format")

        if token.startswith("ghp_"):
            raise TokenValidationError(_MSG_FORMAT_CLASSIC, error_type="format")

        if token.startswith("gho_"):
            raise TokenValidationError(_MSG_FORMAT_OAUTH, error_type="format")

        if token.startswith("ghs_") or token.startswith("ghu_"):
            raise TokenValidationError(_MSG_FORMAT_GITHUB_APP, error_type="format")

        if not token.startswith("github_pat_"):
            raise TokenValidationError(_MSG_FORMAT_UNRECOGNIZED, error_type="format")

    async def _probe_github_auth(self, token: str) -> bool | None:
        """Diagnostic probe: check if token authenticates to GitHub.

        Makes GET https://api.github.com/user with Bearer auth.
        Returns True on 2xx, raises on 401, returns None otherwise.
        """
        try:
            status = await asyncio.to_thread(
                _http_get_status, "https://api.github.com/user", token
            )
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            logger.warning("GitHub auth probe failed (network error): %s", type(e).__name__)
            return None

        if 200 <= status < 300:
            return True

        if status == 401:
            raise TokenValidationError(
                _MSG_AUTH_HIGH_CONFIDENCE, error_type="auth"
            )

        # Any other status (403, 5xx, etc.) — inconclusive
        return None

    async def validate_copilot_access(
        self, token: str, github_auth_confirmed: bool | None
    ) -> None:
        """Validate Copilot API access via list_models().

        Uses github_auth_confirmed (from _probe_github_auth) for error classification.
        Creates a temporary CopilotReviewClient, calls start(token), and stops it.
        """
        client = self._copilot_client_factory()
        try:
            await client.start(token)
            # start() can complete without raising even when SDK import failed
            # (_init_sdk swallows ImportError, leaving is_connected=False).
            if not client.is_connected:
                raise CopilotUnavailableError("SDK not connected after start")
        except (ImportError, CopilotUnavailableError):
            raise TokenValidationError(_MSG_SDK, error_type="sdk")
        except CopilotAuthError:
            if github_auth_confirmed is True:
                raise TokenValidationError(
                    _MSG_PERMISSION, error_type="permission"
                )
            else:
                # Inconclusive probe — cannot distinguish auth from permission
                raise TokenValidationError(
                    _MSG_AUTH_LOW_CONFIDENCE, error_type="auth"
                )
        except Exception as e:
            logger.error("Unexpected error during Copilot validation: %s", e, exc_info=True)
            raise TokenValidationError(
                "An unexpected error occurred while validating Copilot access. "
                "Check container logs for details and try again.",
                error_type="sdk",
            )
        finally:
            await client.stop()

    async def validate(self, token: str) -> None:
        """Full validation: format -> GitHub auth probe -> Copilot access.

        Three-step orchestration with short-circuiting on format and 401 auth errors.
        """
        # Normalize whitespace once at the boundary (paste artifacts, trailing newlines)
        token = token.strip()

        # Step 1: Format check (local, no network)
        self.validate_format(token)

        # Step 2: GitHub auth probe (diagnostic, short-circuits only on 401)
        github_confirmed = await self._probe_github_auth(token)

        # Step 3: Copilot access check
        await self.validate_copilot_access(token, github_auth_confirmed=github_confirmed)
