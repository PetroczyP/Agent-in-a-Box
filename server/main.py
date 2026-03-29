"""FastAPI app — T023 + T016.

FastAPI app with health check, static files, templates, and credential management routes.
Container CMD target: uvicorn server.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from server.copilot_client import CopilotReviewClient
from server.credential_resolver import CredentialResolver
from server.credential_store import CredentialStore
from server.token_validator import TokenValidator
from server.web_routes import create_router

app = FastAPI(title="AgentinaBox", version="0.1.0")

# --- Directories ---
_BASE_DIR = os.path.dirname(__file__)
_TEMPLATES_DIR = os.path.join(_BASE_DIR, "templates")
_STATIC_DIR = os.path.join(_BASE_DIR, "static")

# --- Shared dependencies ---
templates = Jinja2Templates(directory=_TEMPLATES_DIR)
store = CredentialStore()
resolver = CredentialResolver(store=store)
validator = TokenValidator(copilot_client_factory=CopilotReviewClient)

# --- Mount static files ---
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# --- Include credential management routes ---
app.include_router(create_router(templates=templates, store=store, resolver=resolver, validator=validator))


@app.get("/health")
async def health():
    """Health check endpoint for Docker monitoring (FR-018)."""
    return {"status": "ok"}
