"""Web routes for credential management UI — T015, T021.

Routes: GET / (status/redirect), GET /setup (wizard), POST /setup (validate+store),
GET /settings (view token/source), POST /settings/rotate (token rotation).
Per contract: specs/002-credential-setup/contracts/web-routes.md
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from server.credential_resolver import CredentialResolver, CredentialSource
from server.credential_store import CredentialStore
from server.token_validator import TokenValidationError, TokenValidator

logger = logging.getLogger(__name__)


# --- Flash message mapping (query param ?msg= values) ---

_FLASH_MESSAGES = {
    "saved": "Token saved successfully.",
    "rotated": "Token rotated successfully.",
}


def mask_token(token: str | None) -> str:
    """Mask token for display: actual prefix + '...' + last 4 chars.

    Derives the prefix from the token itself (e.g. github_pat_, ghp_, gho_).
    Returns empty string for None/empty input.
    """
    if not token:
        return ""
    # Known GitHub token prefixes, longest first for greedy match
    _KNOWN_PREFIXES = ("github_pat_", "ghs_", "ghu_", "gho_", "ghp_")
    prefix = ""
    for p in _KNOWN_PREFIXES:
        if token.startswith(p):
            prefix = p
            break
    if not prefix:
        if len(token) <= 4:
            return "..."
        prefix = token[:4]
    suffix_len = 4
    if len(token) <= len(prefix) + suffix_len:
        return prefix + "..."
    return prefix + "..." + token[-suffix_len:]


def create_router(
    templates: Jinja2Templates,
    store: CredentialStore,
    resolver: CredentialResolver,
    validator: TokenValidator,
) -> APIRouter:
    """Create and return an APIRouter with credential management routes."""
    router = APIRouter()

    @router.get("/")
    async def index(request: Request, msg: str | None = None):
        """Credential status page. Redirects to /setup if no credential."""
        resolved = resolver.resolve()
        if resolved is None:
            return RedirectResponse(url="/setup")

        message = _FLASH_MESSAGES.get(msg) if msg else None
        masked = mask_token(resolved.token)
        source = resolved.source.value

        return templates.TemplateResponse(
            request,
            "status.html",
            {
                "source": source,
                "masked_token": masked,
                "message": message,
            },
        )

    @router.get("/setup")
    async def setup_get(request: Request):
        """Setup wizard. Redirects to / if credential already configured."""
        resolved = resolver.resolve()
        if resolved is not None:
            return RedirectResponse(url="/")

        return templates.TemplateResponse(
            request,
            "setup.html",
            {"error": None},
        )

    @router.post("/setup")
    async def setup_post(request: Request, token: str = Form(...)):
        """Validate and store token. PRG pattern: redirect on success."""
        token = token.strip()
        try:
            await validator.validate(token)
        except TokenValidationError as e:
            logger.warning("Token validation failed: %s", e.error_type)
            return templates.TemplateResponse(
                request,
                "setup.html",
                {"error": str(e)},
            )

        try:
            store.store(token)
        except OSError as e:
            logger.error("Failed to persist credential: %s", e)
            return templates.TemplateResponse(
                request,
                "setup.html",
                {"error": "Failed to save the token to disk. Check that the /data/ volume is mounted and writable."},
            )

        logger.info("Token stored successfully (source: setup wizard)")
        return RedirectResponse(url="/?msg=saved", status_code=303)

    @router.get("/settings")
    async def settings_get(request: Request, msg: str | None = None):
        """Settings page — show masked token, source, rotation form (FR-006)."""
        resolved = resolver.resolve()
        source = resolved.source if resolved else CredentialSource.NONE
        can_rotate = source == CredentialSource.STORED

        masked = mask_token(resolved.token) if resolved else None
        message = _FLASH_MESSAGES.get(msg) if msg else None

        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "source": source.value,
                "masked_token": masked,
                "can_rotate": can_rotate,
                "message": message,
                "error": None,
            },
        )

    @router.post("/settings/rotate")
    async def settings_rotate(request: Request, token: str = Form(...)):
        """Rotate token — validate, replace, redirect (PRG pattern, FR-006).

        Only allowed when source is 'stored'. Rejects if externally managed.
        """
        resolved = resolver.resolve()
        source = resolved.source if resolved else CredentialSource.NONE

        if source != CredentialSource.STORED:
            # Externally managed — reject rotation
            logger.warning("Rotation rejected: credential source is %s", source)
            masked = mask_token(resolved.token) if resolved else None
            return templates.TemplateResponse(
                request,
                "settings.html",
                {
                    "source": source.value,
                    "masked_token": masked,
                    "can_rotate": False,
                    "message": None,
                    "error": "Token is managed externally and cannot be rotated here.",
                },
            )

        token = token.strip()
        try:
            await validator.validate(token)
        except TokenValidationError as e:
            # Validation failed — re-render with error, old token preserved
            logger.warning("Token validation failed: %s", e.error_type)
            masked = mask_token(resolved.token) if resolved else None
            return templates.TemplateResponse(
                request,
                "settings.html",
                {
                    "source": source.value,
                    "masked_token": masked,
                    "can_rotate": True,
                    "message": None,
                    "error": str(e),
                },
            )

        try:
            store.store(token)
        except OSError as e:
            logger.error("Failed to persist credential: %s", e)
            masked = mask_token(resolved.token) if resolved else None
            return templates.TemplateResponse(
                request,
                "settings.html",
                {
                    "source": source.value,
                    "masked_token": masked,
                    "can_rotate": True,
                    "message": None,
                    "error": "Failed to save the token to disk. Check that the /data/ volume is mounted and writable.",
                },
            )

        logger.info("Token rotated successfully")
        return RedirectResponse(url="/settings?msg=rotated", status_code=303)

    return router
