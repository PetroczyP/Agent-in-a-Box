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


class TestFallbackRegression:
    """T003-T005: Regression tests locking all 3 fallback tiers (FR-009, SC-007).

    These MUST pass before AND after all parser/prompt changes.
    """

    def test_json_parse_path(self, parser, file_contents):
        """T003: Valid JSON array → _try_json succeeds, returns structured findings."""
        response = '[{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unused-import"
        assert findings[0].severity == Severity.NIT
        # Verify it took the JSON path (not regex or NIT-wrap)
        assert findings[0].category == Category.STYLE
        assert findings[0].confidence == Confidence.HIGH

    def test_regex_fallback_path(self, parser, file_contents):
        """T004: Semi-structured text with **BUG** pattern → _try_regex succeeds."""
        response = """I found several issues in this code:

**BUG** in `foo.py` (line 2-3): Missing error handling in main function
This function should catch exceptions.

**WARN** in `foo.py` (line 1): Unused import detected
The os module is imported but never used.
"""
        findings = parser.parse(response, file_contents)
        assert len(findings) >= 2
        severities = {f.severity for f in findings}
        assert Severity.BUG in severities
        assert Severity.WARN in severities or Severity.NIT in severities

    def test_nit_wrap_fallback_path(self, parser, file_contents):
        """T005: Pure conversational text → _wrap_as_nit fires, returns single NIT."""
        response = "The code looks reasonable overall. I noticed a few things that could be improved but nothing critical. Consider adding more documentation."
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.NIT
        assert findings[0].rule_id == "unparseable-response"
        assert findings[0].confidence == Confidence.LOW
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


# ---------------------------------------------------------------------------
# Phase 4 / User Story 2 — Robust Parsing of Mixed Output
# ---------------------------------------------------------------------------

class TestMixedOutputParsing:
    """T013: Mixed output — JSON embedded in prose (FR-003)."""

    def test_json_fence_surrounded_by_prose(self, parser, file_contents):
        """JSON inside ```json fence with surrounding prose is extracted."""
        response = """Here are my findings from the code review:

```json
[{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import os", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os"}]
```

Let me know if you have any questions about these findings."""
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unused-import"
        assert findings[0].severity == Severity.NIT

    def test_bare_json_array_in_prose(self, parser, file_contents):
        """Bare JSON in prose → NIT-wrap (trust model: ambiguous zone)."""
        response = """I reviewed the code and found the following issues:

[{"rule_id": "missing-error-handling", "severity": "BUG", "category": "correctness", "message": "No exception handling", "file": "foo.py", "start_line": 2, "end_line": 3, "confidence": "high", "evidence": "def main()"}]

Those are the issues I found. Happy to discuss further."""
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_multiple_json_blocks_merged(self, parser, file_contents):
        """Multiple JSON blocks in one response are merged into a single list."""
        response = """Here are the bugs:

```json
[{"rule_id": "missing-error-handling", "severity": "BUG", "category": "correctness", "message": "No error handling", "file": "foo.py", "start_line": 2, "end_line": 3, "confidence": "high", "evidence": "def main()"}]
```

And here are the style issues:

```json
[{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "medium", "evidence": "import os"}]
```
"""
        findings = parser.parse(response, file_contents)
        assert len(findings) == 2
        rule_ids = {f.rule_id for f in findings}
        assert "missing-error-handling" in rule_ids
        assert "unused-import" in rule_ids


class TestObjectUnwrap:
    """T014: Object wrapper unwrap — {"findings": [...]} (FR-004)."""

    def test_findings_key_unwrap(self, parser, file_contents):
        """{"findings": [...]} is unwrapped to extract the inner array."""
        response = '{"findings": [{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os"}]}'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unused-import"

    def test_results_key_unwrap(self, parser, file_contents):
        """{"results": [...]} is unwrapped — works for any key that maps to a list."""
        response = '{"results": [{"rule_id": "naming-convention", "severity": "WARN", "category": "style", "message": "Bad name", "file": "foo.py", "start_line": 2, "end_line": 2, "confidence": "medium", "evidence": "def main()"}]}'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "naming-convention"

    def test_object_unwrap_in_code_fence(self, parser, file_contents):
        """Object wrapper inside a code fence is also unwrapped."""
        response = """```json
{"findings": [{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os"}]}
```"""
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unused-import"


class TestTruncatedJsonRepair:
    """T015: Truncated JSON repair via json-repair (FR-007)."""

    def test_unclosed_bracket(self, parser, file_contents):
        """Unclosed JSON bracket is repaired and parsed."""
        response = '[{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os"}'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unused-import"

    def test_trailing_comma(self, parser, file_contents):
        """Trailing comma in JSON array is repaired and parsed."""
        response = '[{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os"},]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unused-import"

    def test_truncated_string(self, parser, file_contents):
        """Truncated string value is repaired and parsed."""
        response = '[{"rule_id": "unused-import", "severity": "NIT", "category": "style", "message": "Unused import", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unused-import"

    def test_non_json_text_skips_repair(self, parser, file_contents):
        """Plain text without JSON-like characters does not go through repair."""
        response = "The code looks fine overall. No major issues found."
        findings = parser.parse(response, file_contents)
        # Should fall through to NIT-wrap, not crash in repair
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"


class TestRepairedEmptyArray:
    """Malformed/truncated JSON handling via json-repair (FR-007).

    Empty repair results are always treated as noise — if _try_json()
    couldn't parse it, json_repair extracting [] is incidental, not
    a real "no findings" response. Legitimate empty arrays go through
    _try_json() (bare "[]", prose ending with "[]", code-fenced "[]").

    Truncated JSON with actual findings (e.g., '[{"severity":"BUG"')
    still extracts correctly because len(items) > 0.
    """

    def test_bare_open_bracket(self, parser, file_contents):
        """A truncated '[' → NIT-wrap. Model was cut off before writing
        findings; returning 'no findings' would be misleading."""
        findings = parser.parse("[", file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_fenced_open_bracket(self, parser, file_contents):
        """A fenced truncated array → NIT-wrap. Truncation before content
        means we have no evidence of 'no findings'."""
        findings = parser.parse("```json\n[\n```", file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_empty_object_wrapper(self, parser, file_contents):
        """'{"findings": []}' is valid JSON → _try_json() handles it → []."""
        findings = parser.parse('{"findings": []}', file_contents)
        assert findings == []

    def test_malformed_empty_object_wrapper(self, parser, file_contents):
        """Truncated '{"findings": [' → NIT-wrap. Same rationale as
        test_bare_open_bracket — truncation ≠ 'no findings'."""
        findings = parser.parse('{"findings": [', file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"


class TestEdgeCasesFromSpec:
    """Edge case tests from spec.md Edge Cases section."""

    def test_missing_fields_use_defaults(self, parser, file_contents):
        """Missing fields should get defaults, not crash (spec edge case 3)."""
        response = '[{"message": "Something looks off"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "code-issue"  # inferred from message
        assert findings[0].severity == Severity.NIT  # default
        assert findings[0].category == Category.STYLE  # inferred from message
        assert findings[0].confidence == Confidence.MEDIUM  # default

    def test_extra_fields_are_ignored(self, parser, file_contents):
        """Extra fields in finding dicts should be silently ignored (spec edge case 3)."""
        response = '[{"rule_id": "test", "severity": "BUG", "category": "correctness", "message": "Bug found", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "import os", "custom_field": "should be ignored", "another_extra": 42}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "test"
        assert findings[0].severity == Severity.BUG

    def test_known_severity_aliases_map_correctly(self, parser, file_contents):
        """Known severity aliases like CRITICAL should map to BUG, not default to NIT."""
        response = '[{"rule_id": "test", "severity": "CRITICAL", "category": "correctness", "message": "Test", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "x"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG

    def test_unknown_severity_defaults_to_nit(self, parser, file_contents):
        """Truly unknown severity string should default to NIT."""
        response = '[{"rule_id": "test", "severity": "BANANA", "category": "correctness", "message": "Test", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "x"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.NIT

    def test_invalid_category_inferred_from_message(self, parser, file_contents):
        """Invalid category string should be inferred from message content."""
        response = '[{"rule_id": "r", "severity": "BUG", "category": "unknown_category", "message": "Something looks off", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "x"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        # No specific keywords in message → falls back to STYLE
        assert findings[0].category == Category.STYLE

    def test_invalid_category_inferred_as_security(self, parser, file_contents):
        """Invalid category with security keywords in message should infer security."""
        response = '[{"rule_id": "r", "severity": "BUG", "category": "vuln", "message": "SQL injection vulnerability", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "x"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].category == Category.SECURITY

    def test_invalid_confidence_defaults_to_medium(self, parser, file_contents):
        """Invalid confidence string should default to medium."""
        response = '[{"rule_id": "test", "severity": "BUG", "category": "correctness", "message": "Test", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "very_sure", "evidence": "x"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].confidence == Confidence.MEDIUM

    def test_invalid_status_defaults_to_open(self, parser, file_contents):
        """Invalid status string should default to open."""
        response = '[{"rule_id": "test", "severity": "BUG", "category": "correctness", "message": "Test", "file": "foo.py", "start_line": 1, "end_line": 1, "confidence": "high", "evidence": "x", "status": "pending_review"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].status == FindingStatus.OPEN


class TestRealModelResponseFormats:
    """Tests based on actual model (Claude via Copilot SDK) response formats."""

    def test_copilot_format_with_description_and_line(self, parser):
        """Real format: severity=critical, line (not start_line), description (not message)."""
        files = {"app.py": "import subprocess\n\ndef run(cmd):\n    subprocess.call(cmd, shell=True)\n"}
        response = '[{"severity":"critical","line":4,"description":"Command injection via shell=True with unsanitized input","suggestion":"Use subprocess.run with a list"}]'
        findings = parser.parse(response, files)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.BUG  # critical → BUG
        assert f.primary_location.file == "app.py"  # inferred from single file
        assert f.primary_location.start_line == 4
        assert "Command injection" in f.message  # from "description" key
        assert f.category == Category.SECURITY  # inferred: "injection"
        assert f.rule_id == "command-injection"  # inferred
        assert f.evidence  # auto-extracted from file

    def test_copilot_format_with_title_field(self, parser):
        """Real format: model uses 'title' as finding name, 'description' as detail."""
        files = {"db.py": "password = 'admin123'\ndb_url = f'postgres://root:{password}@host/db'\n"}
        response = '[{"severity":"high","line":1,"title":"Hardcoded credentials","description":"Password is hardcoded in source code, exposing it to anyone with repo access."}]'
        findings = parser.parse(response, files)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.BUG  # high → BUG
        assert f.primary_location.file == "db.py"
        # "description" is preferred over "title" (more detailed)
        assert "hardcoded in source code" in f.message
        assert f.category == Category.SECURITY  # "hardcod" in message

    def test_copilot_multi_finding_response(self, parser):
        """Real format: multiple findings in one response, no file field."""
        files = {"example.py": "import os\nimport subprocess\n\ndef run(user_input):\n    subprocess.call(user_input, shell=True)\n\ndef get_config():\n    password = 'admin123'\n    return f'postgres://root:{password}@localhost/prod'\n"}
        response = """```json
[
  {"severity":"critical","line":5,"title":"Command injection","description":"shell=True with unsanitized input allows arbitrary command execution"},
  {"severity":"high","line":8,"title":"Hardcoded password","description":"Database password hardcoded in source code"}
]
```"""
        findings = parser.parse(response, files)
        assert len(findings) == 2
        assert findings[0].severity == Severity.BUG
        assert findings[0].primary_location.start_line == 5
        assert findings[0].primary_location.file == "example.py"  # inferred
        assert findings[1].severity == Severity.BUG
        assert findings[1].primary_location.start_line == 8
        # Unique fingerprints
        assert findings[0].fingerprint != findings[1].fingerprint


class TestSeverityMapping:
    """Comprehensive tests for severity alias mapping."""

    @pytest.mark.parametrize("raw,expected", [
        ("BUG", Severity.BUG),
        ("WARN", Severity.WARN),
        ("NIT", Severity.NIT),
        ("critical", Severity.BUG),
        ("CRITICAL", Severity.BUG),
        ("error", Severity.BUG),
        ("high", Severity.BUG),
        ("MAJOR", Severity.BUG),
        ("warning", Severity.WARN),
        ("medium", Severity.WARN),
        ("MODERATE", Severity.WARN),
        ("low", Severity.NIT),
        ("minor", Severity.NIT),
        ("info", Severity.NIT),
        ("SUGGESTION", Severity.NIT),
        ("trivial", Severity.NIT),
        ("UNKNOWN_SEVERITY", Severity.NIT),  # unmapped → default NIT
    ])
    def test_severity_mapping(self, parser, file_contents, raw, expected):
        response = f'[{{"severity": "{raw}", "message": "X", "file": "foo.py", "start_line": 1, "end_line": 1}}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == expected


class TestFileInference:
    """Tests for file path inference when model omits file field."""

    def test_single_file_inferred(self, parser):
        """When there's one file and model omits file, infer it."""
        files = {"only_file.py": "x = 1\n"}
        response = '[{"severity": "NIT", "message": "Unused var", "line": 1}]'
        findings = parser.parse(response, files)
        assert findings[0].primary_location.file == "only_file.py"

    def test_multiple_files_not_inferred(self, parser):
        """When there are multiple files and model omits file, default to unknown."""
        files = {"a.py": "x = 1\n", "b.py": "y = 2\n"}
        response = '[{"severity": "NIT", "message": "Unused var", "line": 1}]'
        findings = parser.parse(response, files)
        assert findings[0].primary_location.file == "unknown"

    def test_explicit_file_used_over_inference(self, parser):
        """When model provides file, use it even with single file."""
        files = {"only_file.py": "x = 1\n"}
        response = '[{"severity": "NIT", "message": "Unused var", "file": "other.py", "line": 1}]'
        findings = parser.parse(response, files)
        assert findings[0].primary_location.file == "other.py"


class TestFieldAliases:
    """Tests for alternative field name handling."""

    def test_description_as_message(self, parser, file_contents):
        response = '[{"description": "Found a problem", "line": 1}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].message == "Found a problem"

    def test_title_as_message(self, parser, file_contents):
        response = '[{"title": "Hardcoded secret", "line": 1}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].message == "Hardcoded secret"

    def test_line_as_start_line(self, parser, file_contents):
        response = '[{"message": "Issue", "line": 3}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].primary_location.start_line == 3
        assert findings[0].primary_location.end_line == 3

    def test_startLine_camelCase(self, parser, file_contents):
        response = '[{"message": "Issue", "startLine": 2, "endLine": 5}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].primary_location.start_line == 2
        assert findings[0].primary_location.end_line == 5

    def test_filePath_camelCase(self, parser, file_contents):
        response = '[{"message": "Issue", "filePath": "foo.py", "line": 1}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].primary_location.file == "foo.py"

    def test_ruleId_camelCase(self, parser, file_contents):
        response = '[{"ruleId": "my-rule", "message": "Issue", "line": 1}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].rule_id == "my-rule"


class TestRuleIdInference:
    """Tests for rule_id inference from message content."""

    @pytest.mark.parametrize("message,expected_rule", [
        ("Command injection via user input", "command-injection"),
        ("SQL injection vulnerability in query builder", "sql-injection"),
        ("XSS vulnerability in template rendering", "xss"),
        ("Hardcoded password in source code", "hardcoded-credential"),
        ("Hardcoded secret key exposed", "hardcoded-credential"),
        ("Password exposed in logs", "credential-exposure"),
        ("Arbitrary code execution possible", "unsafe-code-execution"),
        ("Shell subprocess with unsanitized input", "unsafe-shell-execution"),
        ("Missing error handling for network call", "missing-error-handling"),
        ("Unused import os", "unused-import"),
        ("Race condition in concurrent access", "race-condition"),
        ("Security vulnerability in auth flow", "security-issue"),
        ("Something looks off", "code-issue"),  # no match → default
    ])
    def test_rule_id_inference(self, parser, file_contents, message, expected_rule):
        response = f'[{{"message": "{message}", "line": 1}}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].rule_id == expected_rule


class TestCategoryInference:
    """Tests for category inference from message content."""

    @pytest.mark.parametrize("message,expected_cat", [
        ("SQL injection vulnerability", Category.SECURITY),
        ("Hardcoded password in config", Category.SECURITY),
        ("Attacker can execute arbitrary code", Category.SECURITY),
        ("Untrusted input passed to shell", Category.SECURITY),
        ("Will raise AttributeError at runtime", Category.CORRECTNESS),
        ("TypeError when input is None", Category.CORRECTNESS),
        ("Function does not exist, will crash", Category.CORRECTNESS),
        ("Missing test coverage for edge case", Category.TESTS),
        ("Unit test has weak assertion", Category.TESTS),
        ("High complexity, deeply nested loops", Category.MAINTAINABILITY),
        ("Poor readability due to variable names", Category.MAINTAINABILITY),
        ("Tight coupling between modules", Category.DESIGN),
        ("Violates single responsibility principle", Category.DESIGN),
        ("Variable name too short", Category.STYLE),  # no match → default
    ])
    def test_category_inference(self, parser, file_contents, message, expected_cat):
        # Use invalid category to force inference from message
        response = f'[{{"category": "xxx", "message": "{message}", "line": 1}}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].category == expected_cat


class TestEvidenceFallback:
    """Tests for evidence auto-extraction from file contents."""

    def test_evidence_extracted_when_model_omits_it(self, parser):
        files = {"app.py": "line1\nline2\nline3\n"}
        response = '[{"message": "Issue on line 2", "file": "app.py", "start_line": 2, "end_line": 2}]'
        findings = parser.parse(response, files)
        assert findings[0].evidence == "line2"

    def test_explicit_evidence_preserved(self, parser):
        files = {"app.py": "line1\nline2\nline3\n"}
        response = '[{"message": "Issue", "file": "app.py", "start_line": 2, "end_line": 2, "evidence": "custom evidence"}]'
        findings = parser.parse(response, files)
        assert findings[0].evidence == "custom evidence"

    def test_code_snippet_alias(self, parser, file_contents):
        response = '[{"message": "Issue", "line": 1, "code_snippet": "import os"}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].evidence == "import os"


class TestNonDictItems:
    """Tests that non-dict items in JSON arrays are handled gracefully."""

    def test_string_items_skipped(self, parser, file_contents):
        response = '["not a dict", {"message": "Real finding", "line": 1}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].message == "Real finding"

    def test_number_items_skipped(self, parser, file_contents):
        response = '[42, {"message": "Real finding", "line": 1}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1

    def test_null_items_skipped(self, parser, file_contents):
        response = '[null, {"message": "Real finding", "line": 1}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1


class TestMalformedNumericFields:
    """H-1 regression: malformed line/start_line values must not crash the parser."""

    def test_empty_string_line_degrades_to_default(self, parser, file_contents):
        """line="" should use default (1), not raise ValueError."""
        response = '[{"message": "bad line", "line": ""}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].primary_location.start_line == 1  # default

    def test_non_numeric_line_degrades_to_default(self, parser, file_contents):
        """line="abc" should use default, not crash."""
        response = '[{"message": "bad line", "line": "abc"}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].primary_location.start_line == 1

    def test_empty_end_line_degrades(self, parser, file_contents):
        """end_line="" should fall through to line or start_line."""
        response = '[{"message": "bad end", "line": 3, "end_line": ""}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].primary_location.start_line == 3
        assert findings[0].primary_location.end_line == 3  # falls back to line

    def test_valid_findings_survive_malformed_sibling(self, parser, file_contents):
        """One malformed finding shouldn't prevent others from parsing."""
        response = '[{"message": "bad", "line": "xyz"}, {"message": "good", "line": 2}]'
        findings = parser.parse(response, file_contents)
        assert len(findings) == 2
        assert findings[0].primary_location.start_line == 1  # default
        assert findings[1].primary_location.start_line == 2  # parsed correctly

    def test_float_line_truncated(self, parser, file_contents):
        """line=3.7 should truncate to 3."""
        response = '[{"message": "float line", "line": 3.7}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].primary_location.start_line == 3

    def test_string_integer_line_parsed(self, parser, file_contents):
        """line="5" (string containing int) should parse correctly."""
        response = '[{"message": "string int", "line": "5"}]'
        findings = parser.parse(response, file_contents)
        assert findings[0].primary_location.start_line == 5


class TestRegexPathInference:
    """Tests that the regex fallback path also uses severity mapping and category inference."""

    def test_regex_security_finding_gets_security_category(self, parser, file_contents):
        response = "**BUG** in `foo.py` (line 1): SQL injection vulnerability in query"
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].category == Category.SECURITY  # was hardcoded STYLE before
        assert findings[0].rule_id == "sql-injection"

    def test_regex_correctness_finding(self, parser, file_contents):
        response = "**WARN** in `foo.py` (line 2): Will raise AttributeError at runtime"
        findings = parser.parse(response, file_contents)
        assert len(findings) == 1
        assert findings[0].category == Category.CORRECTNESS


class TestIncidentalBracketFalsePositive:
    """B-1 regression: prose containing incidental [] or {} must NOT be
    misclassified as valid empty-JSON "no findings" responses.
    The fallback chain must reach regex or NIT-wrap for these cases."""

    def test_prose_with_function_call_brackets(self, parser, file_contents):
        """calculate_average([]) in prose must not parse as valid JSON."""
        prose = (
            "Fixed by adding an explicit empty-list guard to "
            "calculate_average([]) before computing the result."
        )
        findings = parser.parse(prose, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"
        assert findings[0].severity == Severity.NIT

    def test_prose_with_dict_literal(self, parser, file_contents):
        """my_dict = {} in prose must not parse as valid JSON."""
        prose = "Initialize with my_dict = {} and then populate it with data."
        findings = parser.parse(prose, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_with_list_index(self, parser, file_contents):
        """items[0] in prose must not be mishandled."""
        prose = "Access the first element with items[0] to get the initial value."
        findings = parser.parse(prose, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_bare_empty_array_still_valid(self, parser, file_contents):
        """A response that is ONLY [] is a legitimate 'no findings' response."""
        findings = parser.parse("[]", file_contents)
        assert findings == []

    def test_bare_empty_array_with_whitespace(self, parser, file_contents):
        """[] with surrounding whitespace is still valid."""
        findings = parser.parse("  []  \n", file_contents)
        assert findings == []

    def test_fenced_empty_array_still_valid(self, parser, file_contents):
        """Code-fenced [] is a legitimate 'no findings' response."""
        findings = parser.parse("```json\n[]\n```", file_contents)
        assert findings == []

    def test_prose_with_multiple_brackets(self, parser, file_contents):
        """Multiple incidental brackets in prose should not parse as JSON."""
        prose = (
            "The function takes a list[] and returns a dict{}. "
            "Call it with process([1,2,3]) to get results."
        )
        findings = parser.parse(prose, file_contents)
        assert len(findings) >= 1
        # Must NOT return empty list (false "no findings")

    def test_intentional_empty_array_at_end_of_prose(self, parser, file_contents):
        """'Here are my findings: []' → NIT-wrap (bare JSON in prose, ambiguous zone)."""
        findings = parser.parse("Here are my findings: []", file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_intentional_empty_array_after_sentence(self, parser, file_contents):
        """'No issues found. []' → NIT-wrap (bare JSON in prose)."""
        findings = parser.parse("No issues found. []", file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_incidental_brackets_in_function_call_only(self, parser, file_contents):
        """Just 'calculate_average([])' — brackets mid-text, not at end."""
        findings = parser.parse("calculate_average([])", file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_short_prose_with_incidental_brackets_fn_call(self, parser, file_contents):
        """Short prose 'Fix fn([]) now.' — json_repair must not extract [] (R8 B-1)."""
        findings = parser.parse("Fix fn([]) now.", file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_short_prose_with_incidental_brackets_mid_text(self, parser, file_contents):
        """Short prose 'prefix [] suffix' — json_repair must not extract [] (R8 B-1)."""
        findings = parser.parse("prefix [] suffix", file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_short_prose_with_brackets_at_start(self, parser, file_contents):
        """'[] trailing note' — [] at start with trailing text → incidental (R8 B-1)."""
        findings = parser.parse("[] trailing note", file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_with_example_json_no_finding_fields(self, parser, file_contents):
        """Prose with example JSON lacking severity+message → NIT-wrap (R9 B-1)."""
        findings = parser.parse('Payload example: [{"foo": 1}]', file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_with_example_json_message_only(self, parser, file_contents):
        """Example JSON with message but no severity → NIT-wrap (R9 B-1)."""
        findings = parser.parse(
            'Use [{"message": "x"}] as a sample payload.', file_contents
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_with_example_json_rule_and_message(self, parser, file_contents):
        """Example JSON with rule_id+message but no severity → NIT-wrap (R9 B-1)."""
        findings = parser.parse(
            'Example JSON: [{"rule_id": "demo", "message": "not a review finding"}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_with_real_finding_json_passes(self, parser, file_contents):
        """Real finding in prose → NIT-wrap (trust model: bare JSON in prose is ambiguous)."""
        findings = parser.parse(
            'Here are my findings: [{"severity": "BUG", "message": "div by zero", "file": "foo.py", "line": 1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_example_response_schema_shaped_json(self, parser, file_contents):
        """Schema-shaped example JSON in 'Example response:' prose → NIT-wrap (R10 B-1)."""
        findings = parser.parse(
            'Example response: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_sample_payload_schema_shaped_json(self, parser, file_contents):
        """Schema-shaped example JSON in 'Sample payload:' prose → NIT-wrap (R10 B-1)."""
        findings = parser.parse(
            'Sample payload: [{"severity":"NIT","description":"not an actual finding"}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_could_emit_schema_shaped_json(self, parser, file_contents):
        """Schema-shaped example in 'you could emit' context → NIT-wrap (R10 B-1)."""
        findings = parser.parse(
            'For example, you could emit [{"severity":"WARN","message":"placeholder"}] but I am not reporting this.',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_findings_introduction_prose_still_nit_wraps(self, parser, file_contents):
        """'I found issues:' + bare JSON → NIT-wrap (trust model: ambiguous zone)."""
        findings = parser.parse(
            'I found the following issues: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_for_example_with_actual_findings(self, parser, file_contents):
        """'For example, I found:' + bare JSON → NIT-wrap (ambiguous zone)."""
        findings = parser.parse(
            'For example, I found the following issues: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_example_of_issue_found(self, parser, file_contents):
        """'Here is an example of one issue I found:' + bare JSON → NIT-wrap."""
        findings = parser.parse(
            'Here is an example of one issue I found: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_for_example_discourse_marker(self, parser, file_contents):
        """'The issue is, for example, a division by zero:' + bare JSON → NIT-wrap."""
        findings = parser.parse(
            'The issue is, for example, a division by zero: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_sample_bug_report_payload(self, parser, file_contents):
        """'Sample bug report payload:' with rescue noun but no verb phrase → NIT-wrap (R12 B-1)."""
        findings = parser.parse(
            'Sample bug report payload: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_example_findings_json(self, parser, file_contents):
        """'Example findings JSON:' with rescue noun but no verb phrase → NIT-wrap (R12 B-1)."""
        findings = parser.parse(
            'Example findings JSON: [{"severity":"WARN","message":"demo"}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_illustration_of_issue_format(self, parser, file_contents):
        """'Illustration of issue format:' with rescue noun but no verb phrase → NIT-wrap (R12 B-1)."""
        findings = parser.parse(
            'Illustration of issue format: [{"severity":"NIT","description":"demo"}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_example_payload_from_issue_tracker(self, parser, file_contents):
        """'Example payload from issue tracker:' with rescue noun but no verb phrase → NIT-wrap (R12 B-1)."""
        findings = parser.parse(
            'Example payload from issue tracker: [{"severity":"BUG","message":"demo"}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # R13 B-1 (now R16 trust model): bare JSON in prose → NIT-wrap
    # Under the trust model, ALL bare JSON embedded in prose is ambiguous
    # and gets NIT-wrapped regardless of content or framing.
    def test_prose_for_example_discourse_no_rescue(self, parser, file_contents):
        """'For example, division by zero can occur here:' + bare JSON → NIT-wrap (trust model)."""
        findings = parser.parse(
            'For example, division by zero can occur here: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_for_example_this_can(self, parser, file_contents):
        """'For example, this can divide by zero:' + bare JSON → NIT-wrap (trust model)."""
        findings = parser.parse(
            'For example, this can divide by zero: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_for_instance_discourse(self, parser, file_contents):
        """'For instance, division by zero can occur here:' + bare JSON → NIT-wrap (trust model)."""
        findings = parser.parse(
            'For instance, division by zero can occur here: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # R13 B-1: false positives — rescue verb refers to the example itself
    def test_prose_noticed_example_format(self, parser, file_contents):
        """'I noticed this example response format:' rescue before indicator → NIT-wrap (R13 B-1 false pos)."""
        findings = parser.parse(
            'I noticed this example response format: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_found_example_format(self, parser, file_contents):
        """'I found this example response format useful:' rescue before indicator → NIT-wrap (R13 B-1 false pos)."""
        findings = parser.parse(
            'I found this example response format useful: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_issue_is_format_for_example(self, parser, file_contents):
        """'The issue is the response format, for example:' rescue before indicator → NIT-wrap (R13 B-1 false pos)."""
        findings = parser.parse(
            'The issue is the response format, for example: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_identified_example_payload(self, parser, file_contents):
        """'I have identified this example payload shape:' rescue before indicator → NIT-wrap (R13 B-1 false pos)."""
        findings = parser.parse(
            'I have identified this example payload shape: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # ── R16: Trust model — bare JSON in prose is ALWAYS ambiguous ──
    #
    # Under the trust model (R16), the parser only trusts JSON in
    # unambiguous containers: code fences, sentinel delimiters, or
    # whole-response JSON.  ALL bare JSON embedded in prose gets
    # NIT-wrapped regardless of framing words or content quality.
    # This eliminates the entire class of false positives where
    # illustrative examples were fabricated as real findings.

    # CLASS: Discourse markers + ANY content in prose → NIT-wrap
    def test_for_example_colon_real(self, parser, file_contents):
        """'For example:' + bare JSON → NIT-wrap (trust model: prose is ambiguous)."""
        findings = parser.parse(
            'For example: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_for_instance_colon_real(self, parser, file_contents):
        """'For instance:' + bare JSON → NIT-wrap (trust model)."""
        findings = parser.parse(
            'For instance: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_eg_colon_real(self, parser, file_contents):
        """'e.g.:' + bare JSON → NIT-wrap (trust model)."""
        findings = parser.parse(
            'e.g.: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_eg_no_comma_real(self, parser, file_contents):
        """'e.g. division by zero can occur here:' + bare JSON → NIT-wrap (trust model)."""
        findings = parser.parse(
            'e.g. division by zero can occur here: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_for_instance_comma_real(self, parser, file_contents):
        """'For instance, this can crash:' + bare JSON → NIT-wrap (trust model)."""
        findings = parser.parse(
            'For instance, this can crash: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # CLASS: Discourse markers + PLACEHOLDER content → reject
    def test_for_example_comma_demo(self, parser, file_contents):
        """'For example, the expected JSON is:' + demo → NIT-wrap (R14 B-1 false pos)."""
        findings = parser.parse(
            'For example, the expected JSON is: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_for_example_format_works_demo(self, parser, file_contents):
        """'For example, this format works:' + demo → NIT-wrap (R14 B-1 false pos)."""
        findings = parser.parse(
            'For example, this format works: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_for_instance_expected_payload_demo(self, parser, file_contents):
        """'For instance, the expected payload is:' + demo → NIT-wrap (R14 B-1 false pos)."""
        findings = parser.parse(
            'For instance, the expected payload is: [{"severity":"WARN","message":"demo"}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_eg_format_demo(self, parser, file_contents):
        """'e.g. this is the format:' + demo → NIT-wrap."""
        findings = parser.parse(
            'e.g. this is the format: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_for_example_colon_demo(self, parser, file_contents):
        """'For example:' + demo → NIT-wrap (placeholder content)."""
        findings = parser.parse(
            'For example: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # CLASS: Format/payload/schema framing + placeholder content → reject
    def test_payload_format_demo(self, parser, file_contents):
        """'Payload format:' + demo → NIT-wrap (R14 B-1 false pos)."""
        findings = parser.parse(
            'Payload format: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_expected_json_demo(self, parser, file_contents):
        """'The expected JSON is:' + demo → NIT-wrap."""
        findings = parser.parse(
            'The expected JSON is: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_response_format_demo(self, parser, file_contents):
        """'Response format:' + demo → NIT-wrap."""
        findings = parser.parse(
            'Response format: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_output_format_demo(self, parser, file_contents):
        """'Output format:' + demo → NIT-wrap."""
        findings = parser.parse(
            'Output format: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # CLASS: Example/sample words + ANY content in prose → NIT-wrap
    def test_here_is_an_example_real(self, parser, file_contents):
        """'Here is an example:' + bare JSON → NIT-wrap (trust model: prose is ambiguous)."""
        findings = parser.parse(
            'Here is an example: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_sample_issue_real(self, parser, file_contents):
        """'Sample issue found:' + bare JSON → NIT-wrap (trust model)."""
        findings = parser.parse(
            'Sample issue found: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # CLASS: Mixed content in prose → NIT-wrap (bare JSON, no trusted container)
    def test_mixed_real_and_placeholder(self, parser, file_contents):
        """Mixed real + placeholder messages in prose → NIT-wrap (trust model)."""
        findings = parser.parse(
            'Issues found: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2},'
            '{"severity":"NIT","message":"demo"}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # CLASS: Code-fenced JSON always trusted (bypasses all prose/content checks)
    def test_fenced_demo_trusted(self, parser, file_contents):
        """Code-fenced JSON with demo message → still trusted."""
        findings = parser.parse(
            'Example:\n```json\n[{"severity":"BUG","message":"demo","file":"foo.py","line":1}]\n```',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG

    # CLASS: Bare JSON in prose with example-adjacent words → NIT-wrap
    def test_real_msg_with_word_example(self, parser, file_contents):
        """'Found:' + bare JSON → NIT-wrap (trust model: prose is ambiguous)."""
        findings = parser.parse(
            'Found: [{"severity":"BUG","message":"Example variable is uninitialized","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_real_msg_with_word_format(self, parser, file_contents):
        """'Issues:' + bare JSON → NIT-wrap (trust model: prose is ambiguous)."""
        findings = parser.parse(
            'Issues: [{"severity":"NIT","message":"format string vulnerability","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"


class TestSentinelDelimitedJSON:
    """Tests for BEGIN_FINDINGS_JSON / END_FINDINGS_JSON sentinel extraction.

    The sentinel delimiter is a machine-readable contract between the prompt
    and the parser.  It is the PREFERRED output path (alongside code fences).
    """

    def test_sentinel_single_finding(self, parser, file_contents):
        """Sentinel-delimited JSON with one finding → parsed."""
        text = (
            "Here are my findings:\n"
            "BEGIN_FINDINGS_JSON\n"
            '[{"severity":"BUG","message":"null deref","file":"foo.py","start_line":2}]\n'
            "END_FINDINGS_JSON"
        )
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG
        assert findings[0].message == "null deref"

    def test_sentinel_empty_array(self, parser, file_contents):
        """Sentinel-delimited empty array → no findings."""
        text = (
            "Code looks clean.\n"
            "BEGIN_FINDINGS_JSON\n"
            "[]\n"
            "END_FINDINGS_JSON"
        )
        findings = parser.parse(text, file_contents)
        assert findings == []

    def test_sentinel_multiple_findings(self, parser, file_contents):
        """Sentinel-delimited JSON with multiple findings → all parsed."""
        text = (
            "BEGIN_FINDINGS_JSON\n"
            '[{"severity":"BUG","message":"null deref","file":"foo.py","start_line":1},'
            '{"severity":"WARN","message":"unchecked return","file":"foo.py","start_line":3}]\n'
            "END_FINDINGS_JSON"
        )
        findings = parser.parse(text, file_contents)
        assert len(findings) == 2
        assert findings[0].severity == Severity.BUG
        assert findings[1].severity == Severity.WARN

    def test_sentinel_with_surrounding_prose(self, parser, file_contents):
        """Sentinel block inside conversational prose → findings extracted."""
        text = (
            "I found several issues in your code.\n\n"
            "The main problem is error handling.\n\n"
            "BEGIN_FINDINGS_JSON\n"
            '[{"severity":"WARN","message":"missing error handling","file":"foo.py","start_line":2}]\n'
            "END_FINDINGS_JSON\n\n"
            "Let me know if you want more details."
        )
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.WARN

    def test_sentinel_preferred_over_prose_json(self, parser, file_contents):
        """Sentinel-delimited JSON is trusted even when bare JSON also in prose."""
        text = (
            'Example response: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]\n\n'
            "BEGIN_FINDINGS_JSON\n"
            '[{"severity":"WARN","message":"real issue","file":"foo.py","start_line":2}]\n'
            "END_FINDINGS_JSON"
        )
        # Sentinel content is inside prose that also has bare JSON —
        # but since there are no code fences, sentinels take priority
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].message == "real issue"

    def test_sentinel_in_format_reinforcement_style(self, parser, file_contents):
        """Sentinel output matching FORMAT_REINFORCEMENT example → parsed."""
        text = "BEGIN_FINDINGS_JSON\n[]\nEND_FINDINGS_JSON"
        findings = parser.parse(text, file_contents)
        assert findings == []


class TestTrustModelDecisionTable:
    """Decision table: framing × content × wrapper.

    The trust model defines three zones:
    - TRUSTED: code-fenced JSON, sentinel-delimited JSON, whole-response JSON
    - AMBIGUOUS: bare JSON embedded in prose → fail closed (NIT-wrap)
    - PLAIN TEXT: no JSON at all → regex extraction → NIT-wrap

    This table crosses:
    - Wrapper: fenced | sentinel | whole-response | bare-in-prose
    - Framing: example | neutral | none
    - Content: placeholder | realistic | mixed
    """

    # ── FENCED JSON: always trusted regardless of framing/content ──

    def test_fenced_example_framing_placeholder(self, parser, file_contents):
        """Fenced + example framing + placeholder → trusted (parsed)."""
        text = 'For example:\n```json\n[{"severity":"BUG","message":"demo","file":"foo.py","line":1}]\n```'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG

    def test_fenced_example_framing_realistic(self, parser, file_contents):
        """Fenced + example framing + realistic → trusted (parsed)."""
        text = 'For example:\n```json\n[{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]\n```'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG

    def test_fenced_neutral_framing_realistic(self, parser, file_contents):
        """Fenced + neutral framing + realistic → trusted (parsed)."""
        text = 'Issues found:\n```json\n[{"severity":"WARN","message":"SQL injection","file":"foo.py","line":3}]\n```'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.WARN

    # ── SENTINEL JSON: always trusted regardless of framing/content ──

    def test_sentinel_example_framing_placeholder(self, parser, file_contents):
        """Sentinel + example framing + placeholder → trusted (parsed)."""
        text = (
            "Example output:\n"
            "BEGIN_FINDINGS_JSON\n"
            '[{"severity":"BUG","message":"demo","file":"foo.py","line":1}]\n'
            "END_FINDINGS_JSON"
        )
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG

    def test_sentinel_example_framing_realistic(self, parser, file_contents):
        """Sentinel + example framing + realistic → trusted (parsed)."""
        text = (
            "Example output:\n"
            "BEGIN_FINDINGS_JSON\n"
            '[{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]\n'
            "END_FINDINGS_JSON"
        )
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG

    def test_sentinel_neutral_framing_mixed(self, parser, file_contents):
        """Sentinel + neutral framing + mixed → trusted (parsed)."""
        text = (
            "Found these:\n"
            "BEGIN_FINDINGS_JSON\n"
            '[{"severity":"BUG","message":"division by zero","file":"foo.py","line":2},'
            '{"severity":"NIT","message":"demo","file":"foo.py","line":1}]\n'
            "END_FINDINGS_JSON"
        )
        findings = parser.parse(text, file_contents)
        assert len(findings) == 2

    # ── WHOLE-RESPONSE JSON: trusted (no framing text at all) ──

    def test_whole_response_realistic(self, parser, file_contents):
        """Whole-response JSON (no prose) → trusted."""
        text = '[{"severity":"BUG","message":"division by zero","file":"foo.py","start_line":2}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG

    def test_whole_response_placeholder(self, parser, file_contents):
        """Whole-response JSON with placeholder → trusted (still parsed)."""
        text = '[{"severity":"BUG","message":"demo","file":"foo.py","start_line":1}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].severity == Severity.BUG

    def test_whole_response_empty_array(self, parser, file_contents):
        """Whole-response empty JSON array → no findings."""
        findings = parser.parse("[]", file_contents)
        assert findings == []

    # ── BARE JSON IN PROSE: ambiguous → NIT-wrap (fail closed) ──

    def test_prose_example_placeholder(self, parser, file_contents):
        """Bare-in-prose + example framing + placeholder → NIT-wrap."""
        text = 'Example response: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_example_realistic(self, parser, file_contents):
        """Bare-in-prose + example framing + realistic → NIT-wrap.

        This is the CRITICAL case: the exact class the judge identified.
        'Example response: [realistic bug text]' MUST NOT fabricate a finding.
        """
        text = 'Example response: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_sample_realistic(self, parser, file_contents):
        """Bare-in-prose + 'Sample payload:' + realistic → NIT-wrap."""
        text = 'Sample payload: [{"severity":"BUG","message":"hardcoded credential","file":"foo.py","line":9}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_expected_json_realistic(self, parser, file_contents):
        """Bare-in-prose + 'Expected JSON:' + realistic → NIT-wrap."""
        text = 'Expected JSON: [{"severity":"BUG","message":"off-by-one error","file":"foo.py","line":3}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_for_example_use_format_realistic(self, parser, file_contents):
        """Bare-in-prose + 'For example, use this output format:' + realistic → NIT-wrap."""
        text = 'For example, use this output format: [{"severity":"WARN","message":"SQL injection in query","file":"foo.py","line":5}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_here_is_an_example_realistic(self, parser, file_contents):
        """Bare-in-prose + 'Here is an example:' + realistic → NIT-wrap."""
        text = 'Here is an example: [{"severity":"BUG","message":"this is just an example","file":"foo.py","line":1}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_neutral_realistic(self, parser, file_contents):
        """Bare-in-prose + neutral framing + realistic → NIT-wrap."""
        text = 'Issues found: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]'
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_prose_neutral_mixed(self, parser, file_contents):
        """Bare-in-prose + neutral framing + mixed content → NIT-wrap."""
        text = (
            'Results: [{"severity":"BUG","message":"use after free","file":"foo.py","line":2},'
            '{"severity":"NIT","message":"demo","file":"foo.py","line":1}]'
        )
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    # ── PLAIN TEXT: no JSON at all → regex → NIT-wrap ──

    def test_plain_text_no_json(self, parser, file_contents):
        """Plain conversational text with no JSON → NIT-wrap."""
        text = "The code looks good overall, but there's a null dereference on line 5 of foo.py."
        findings = parser.parse(text, file_contents)
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"


class TestJudgeR15FalsePositives:
    """Exact repro cases from judge R15 verification.

    These are the SPECIFIC strings the judge tested in the venv.
    ALL must NIT-wrap under the trust model (they are bare JSON in prose).
    """

    def test_example_response_division_by_zero(self, parser, file_contents):
        """Judge R15: 'Example response: [division by zero]' → NIT-wrap."""
        findings = parser.parse(
            'Example response: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_for_example_use_output_format_sql_injection(self, parser, file_contents):
        """Judge R15: 'For example, use this output format: [SQL injection]' → NIT-wrap."""
        findings = parser.parse(
            'For example, use this output format: [{"severity":"WARN","message":"SQL injection in query","file":"foo.py","line":5}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_sample_payload_hardcoded_credential(self, parser, file_contents):
        """Judge R15: 'Sample payload: [hardcoded credential]' → NIT-wrap."""
        findings = parser.parse(
            'Sample payload: [{"severity":"BUG","message":"hardcoded credential","file":"foo.py","line":9}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_expected_json_off_by_one(self, parser, file_contents):
        """Judge R15: 'Expected JSON: [off-by-one error]' → NIT-wrap."""
        findings = parser.parse(
            'Expected JSON: [{"severity":"BUG","message":"off-by-one error","file":"foo.py","line":3}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_here_is_an_example_just_an_example(self, parser, file_contents):
        """Judge R15: 'Here is an example: [this is just an example]' → NIT-wrap."""
        findings = parser.parse(
            'Here is an example: [{"severity":"BUG","message":"this is just an example","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"


class TestJudgeR14FalsePositives:
    """Exact repro cases from judge R14 verification.

    Verifies that the R14 false positive/negative cases behave correctly
    under the trust model.
    """

    def test_for_example_expected_json_demo(self, parser, file_contents):
        """R14: 'For example, the expected JSON is: [demo]' → NIT-wrap."""
        findings = parser.parse(
            'For example, the expected JSON is: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_for_example_format_works_demo(self, parser, file_contents):
        """R14: 'For example, this format works: [demo]' → NIT-wrap."""
        findings = parser.parse(
            'For example, this format works: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_for_instance_expected_payload_demo(self, parser, file_contents):
        """R14: 'For instance, the expected payload is: [demo]' → NIT-wrap."""
        findings = parser.parse(
            'For instance, the expected payload is: [{"severity":"WARN","message":"demo"}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_payload_format_demo(self, parser, file_contents):
        """R14: 'Payload format: [demo]' → NIT-wrap."""
        findings = parser.parse(
            'Payload format: [{"severity":"BUG","message":"demo","file":"foo.py","line":1}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"

    def test_eg_division_by_zero(self, parser, file_contents):
        """R14: 'e.g. division by zero can occur here: [BUG]' → NIT-wrap."""
        findings = parser.parse(
            'e.g. division by zero can occur here: [{"severity":"BUG","message":"division by zero","file":"foo.py","line":2}]',
            file_contents,
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "unparseable-response"
