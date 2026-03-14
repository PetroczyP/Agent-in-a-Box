"""Tests for FastAPI health endpoint — test phase coverage for server/main.py."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_is_get_only(self, client):
        response = client.post("/health")
        assert response.status_code == 405

    def test_app_title(self):
        assert app.title == "AgentinaBox"
