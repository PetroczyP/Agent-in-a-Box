"""FastAPI app — T023.

Minimal FastAPI app with health check endpoint.
Container CMD target: uvicorn server.main:app --host 0.0.0.0 --port 8080
Per plan.md: health endpoint only for MVP. Web dashboard routes added in spec 003.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="AgentinaBox", version="0.1.0")


@app.get("/health")
async def health():
    """Health check endpoint for Docker monitoring (FR-018)."""
    return {"status": "ok"}
