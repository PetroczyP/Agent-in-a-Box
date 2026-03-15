"""Tests for MCP tool handlers — T019, T027."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.models import (
    DiscussRequest,
    DiscussResult,
    Finding,
    ReviewBundle,
    ReviewResult,
    ReviewSummary,
    SessionInfo,
    SessionList,
    SummaryRequest,
)


class TestMCPToolRegistration:
    def test_start_review_tool_exists(self):
        from server.mcp_server import mcp
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "start_review" in tools

    def test_discuss_tool_exists(self):
        from server.mcp_server import mcp
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "discuss" in tools

    def test_get_review_summary_tool_exists(self):
        from server.mcp_server import mcp
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "get_review_summary" in tools

    def test_list_sessions_tool_exists(self):
        from server.mcp_server import mcp
        tools = {t.name for t in mcp._tool_manager.list_tools()}
        assert "list_sessions" in tools
