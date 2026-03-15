"""Shared fixtures for AgentinaBox tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from server.models import (
    Category,
    Confidence,
    Finding,
    FindingStatus,
    Location,
    ReviewBundle,
    Severity,
)


@pytest.fixture
def sample_review_bundle() -> ReviewBundle:
    """A minimal valid review bundle for testing."""
    return ReviewBundle(
        diff="--- a/foo.py\n+++ b/foo.py\n@@ -1,3 +1,4 @@\n+import os\n def main():\n     pass\n",
        files={"foo.py": "import os\ndef main():\n    pass\n"},
        test_files={"tests/test_foo.py": "def test_main():\n    assert True\n"},
        spec="Test spec content",
        conventions="Use snake_case",
        anti_patterns=None,
        test_results="1 passed",
        context="PR #42: Add os import",
        branch="feature/add-os-import",
        model=None,
        idempotency_token=None,
    )


@pytest.fixture
def sample_bundle_with_denied_files() -> ReviewBundle:
    """A review bundle containing files that should be denied."""
    return ReviewBundle(
        diff="--- a/.env\n+++ b/.env\n@@ -1 +1 @@\n-OLD=val\n+NEW=val\n",
        files={".env": "SECRET_KEY=abc123", "app.py": "print('hello')"},
        branch="feature/bad-files",
    )


@pytest.fixture
def sample_findings() -> list[Finding]:
    """A set of sample findings for testing."""
    return [
        Finding(
            finding_id="F-001",
            rule_id="missing-error-handling",
            severity=Severity.BUG,
            category=Category.CORRECTNESS,
            message="Function main() does not handle exceptions",
            primary_location=Location(file="foo.py", start_line=2, end_line=3),
            related_locations=[],
            fingerprint="abc123def456",
            confidence=Confidence.HIGH,
            evidence="def main():\n    pass",
            status=FindingStatus.OPEN,
        ),
        Finding(
            finding_id="F-002",
            rule_id="unused-import",
            severity=Severity.WARN,
            category=Category.STYLE,
            message="Import 'os' is unused",
            primary_location=Location(file="foo.py", start_line=1, end_line=1),
            related_locations=[],
            fingerprint="789ghi012jkl",
            confidence=Confidence.HIGH,
            evidence="import os",
            status=FindingStatus.OPEN,
        ),
        Finding(
            finding_id="F-003",
            rule_id="naming-convention",
            severity=Severity.NIT,
            category=Category.MAINTAINABILITY,
            message="Consider a more descriptive function name than 'main'",
            primary_location=Location(file="foo.py", start_line=2, end_line=2),
            related_locations=[],
            fingerprint="345mno678pqr",
            confidence=Confidence.LOW,
            evidence="def main():",
            status=FindingStatus.OPEN,
        ),
    ]


@pytest.fixture
def mock_copilot_client() -> AsyncMock:
    """A mock CopilotReviewClient for testing without actual SDK calls."""
    client = AsyncMock()
    client.is_connected = True
    client.selected_model = "gpt-4o"
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.select_model = AsyncMock(return_value="gpt-4o")
    client.create_review_session = AsyncMock(return_value="copilot-session-key-1")
    client.send_review = AsyncMock(return_value='[{"rule_id": "missing-error-handling", "severity": "BUG", "category": "correctness", "message": "Function main() does not handle exceptions", "file": "foo.py", "start_line": 2, "end_line": 3, "confidence": "high", "evidence": "def main():\\n    pass"}]')
    client.send_followup = AsyncMock(return_value='[{"rule_id": "missing-error-handling", "severity": "BUG", "category": "correctness", "message": "Good point, the error handling concern is valid given the context", "file": "foo.py", "start_line": 2, "end_line": 3, "confidence": "medium", "evidence": "def main():\\n    pass", "status": "dismissed"}]')
    return client


@pytest.fixture
def copilot_json_response() -> str:
    """A sample Copilot JSON response for finding parsing tests."""
    return """```json
[
    {
        "rule_id": "missing-error-handling",
        "severity": "BUG",
        "category": "correctness",
        "message": "Function does not handle exceptions from os calls",
        "file": "foo.py",
        "start_line": 2,
        "end_line": 3,
        "confidence": "high",
        "evidence": "def main():\\n    pass"
    },
    {
        "rule_id": "unused-import",
        "severity": "NIT",
        "category": "style",
        "message": "Import 'os' is not used anywhere",
        "file": "foo.py",
        "start_line": 1,
        "end_line": 1,
        "confidence": "high",
        "evidence": "import os"
    }
]
```"""
