"""Tests for MCP server configuration helpers — Issue #14."""

from __future__ import annotations

import os

import pytest

from server.mcp_server import _parse_timeout


class TestParseTimeout:
    """AC-5, AC-6: Env var parsing for timeout configuration."""

    def test_valid_value(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "180")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 180.0

    def test_valid_float_value(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "90.5")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 90.5

    def test_missing_env_var(self, monkeypatch):
        monkeypatch.delenv("REVIEW_TIMEOUT", raising=False)
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_empty_env_var(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_negative_value_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "-5")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_zero_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "0")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_non_numeric_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "abc")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_inf_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "inf")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_large_exponent_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "1e999")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_negative_inf_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "-inf")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0
