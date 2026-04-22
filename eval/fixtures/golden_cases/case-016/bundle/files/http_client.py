"""Async HTTP client with retry logic and structured error handling."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
MAX_RETRIES = 3


class ApiClient:
    """Async HTTP client wrapper with retry, timeout, and resource management."""

    def __init__(
        self,
        base_url: str,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._headers = headers or {}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ApiClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=self._headers,
        )
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=0.5, max=10),
        reraise=True,
    )
    async def get_json(self, path: str) -> Any:
        """Send a GET request and return the parsed JSON response.

        Retries on transport errors (connection reset, DNS failure, etc.)
        up to MAX_RETRIES times with exponential backoff.

        Raises:
            RuntimeError: If called outside an async context manager.
            httpx.HTTPStatusError: On 4xx/5xx responses.
            httpx.TransportError: After exhausting retries.
        """
        if self._client is None:
            raise RuntimeError("ApiClient must be used as an async context manager")
        response = await self._client.get(path)
        response.raise_for_status()
        return response.json()

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=0.5, max=10),
        reraise=True,
    )
    async def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        """Send a POST request with JSON body and return the parsed response.

        Raises:
            RuntimeError: If called outside an async context manager.
            httpx.HTTPStatusError: On 4xx/5xx responses.
            httpx.TransportError: After exhausting retries.
        """
        if self._client is None:
            raise RuntimeError("ApiClient must be used as an async context manager")
        response = await self._client.post(path, json=payload)
        response.raise_for_status()
        return response.json()
