"""Tests for finding parser — T010."""

from __future__ import annotations

import pytest

from server.finding_parser import FindingParser
from server.models import Category, Confidence, FindingStatus, Severity


@pytest.fixture
def parser() -> FindingParser:
    return FindingParser()


@pytest.fixture
def file_contents() -> dict[str, str]:
    return {"foo.py": "import os\ndef main():\n    pass\n"}


class TestJsonParsing:
    def test_valid_json_array(self, parser, file_contents):
        response = '[{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unused-import"
        assert findings[0].severity == Severity.NIT
        assert findings[0].category == Category.STYLE
        assert findings[0].status == FindingStatus.OPEN

    def test_json_in_code_fence(self, parser, file_contents, copilot_json_response):
        findings = parser.parse(copilot_json_response, file_contents)
        assert len(findings) == 2
        assert findings[0].severity == Severity.BUG
        assert findings[1].severity == Severity.NIT

    def test_finding_ids_are_sequential(self, parser, file_contents, copilot_json_response):
        findings = parser.parse(copilot_json_response, file_contents)
        assert findings[0].finding_id == "F-001"
        assert findings[1].finding_id == "F-002"

    def test_fingerprints_are_computed(self, parser, file_contents, copilot_json_response):
        findings = parser.parse(copilot_json_response, file_contents)
        assert findings[0].fingerprint is not None
        assert len(findings[0].fingerprint) == 16  # SHA-256 truncated to 16 hex chars

    def test_fingerprint_stability(self, parser, file_contents):
        """Same rule_id + code should produce same fingerprint."""
        response = '[{"rule_id": "test-rule", "severity": "NIT", "category": "style", "message": "Test", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "low", "evidence": "import os"}]'
        f1 = parser.parse(response, file_contents)
        f2 = parser.parse(response, file_contents)
        assert f1[0].fingerprint == f2[0].fingerprint


class TestMalformedJsonFallback:
    def test_malformed_json_falls_back_to_regex(self, parser, file_contents):
        """If JSON parsing fails, try regex-based extraction."""
        response = """Here are my findings:

**BUG** in `foo.py` (line 2-3): Missing error handling
The function does not handle exceptions.

**NIT** in `foo.py` (line 1): Unused import os
"""
        findings = parser.parse(response, file_contents)
        assert len(findings) >= 1  # Should extract at least one finding via regex


class TestUnparseableFallback:
    def test_completely_unparseable_wraps_as_single_nit(self, parser, file_contents):
        """If nothing is parseable, wrap the entire response as a single NIT finding."""
        response = "This is just free text with no structured content at all."
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.NIT
        assert findings[0].category == Category.STYLE
        assert findings[0].finding_id == "F-001"
        assert response in findings[0].message


class TestFingerprintComputation:
    def test_fingerprint_uses_rule_id_and_code(self, parser, file_contents):
        response1 = '[{"rule_id": "rule-a", "severity": "NIT", "category": "style", "message": "Test", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "low", "evidence": "import os"}]'
        response2 = '[{"rule_id": "rule-b", "severity": "NIT", "category": "style", "message": "Test", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "low", "evidence": "import os"}]'
        f1 = parser.parse(response1, file_contents)
        f2 = parser.parse(response2, file_contents)
        # Different rule_id → different fingerprint
        assert f1[0].fingerprint != f2[0].fingerprint

    def test_fingerprint_normalizes_whitespace(self, parser):
        """Whitespace differences in code should not change fingerprint."""
        files1 = {"foo.py": "import  os\ndef   main():\n    pass\n"}
        files2 = {"foo.py": "import os\ndef main():\n pass\n"}
        response = '[{"rule_id": "test", "severity": "NIT", "category": "style", "message": "Test", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "low", "evidence": "import os"}]'
        f1 = parser.parse(response, files1)
        f2 = parser.parse(response, files2)
        # Both should have same fingerprint since code normalizes whitespace
        assert f1[0].fingerprint == f2[0].fingerprint
