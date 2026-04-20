"""Finding parser — T014.

Parses Copilot's text response into structured Finding objects.
Strategy: JSON parse → json-repair → regex fallback → NIT wrap fallback.
Fingerprint: SHA-256 of rule_id + normalized code (research.md Decision 7).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from json_repair import repair_json

from server.models import (
    Category,
    Confidence,
    Finding,
    FindingStatus,
    Location,
    Severity,
)


def compute_fingerprint(rule_id: str, file_path: str, code_snippet: str) -> str:
    """SHA-256 of (rule_id, file_path, normalized code), truncated to 16 hex chars.

    The file path is part of the identity because the same rule_id and
    snippet can legitimately appear in multiple files (e.g., a shared
    anti-pattern) and must not be merged by reconciliation. Line
    numbers are deliberately excluded — a fix that shifts lines should
    still match its prior fingerprint.
    """
    normalized = " ".join(code_snippet.split())
    return hashlib.sha256(
        f"{rule_id}:{file_path}:{normalized}".encode()
    ).hexdigest()[:16]


class FindingParser:
    """Parses Copilot's text response into structured Finding objects."""

    def parse(
        self,
        response_text: str,
        file_contents: dict[str, str],
        start_id: int = 1,
        filter_low_confidence: bool = True,
        allow_nit_fallback: bool = True,
    ) -> list[Finding]:
        """Parse response into findings. start_id controls F-NNN numbering.

        When filter_low_confidence is False, low-confidence findings are
        preserved so the caller can make its own decision (e.g., discuss
        reconciliation needs them to propagate status updates).

        When allow_nit_fallback is False, unparseable responses return []
        instead of the synthetic NIT wrap. Used by discuss() where plain
        conversational text must not fabricate phantom findings.
        """
        def _maybe_filter(fs: list[Finding]) -> list[Finding]:
            return self._filter_low_confidence(fs) if filter_low_confidence else fs

        # Try JSON first (returns None on parse failure, [] on valid empty array)
        findings = self._try_json(response_text, file_contents, start_id)
        if findings is not None:
            return _maybe_filter(findings)

        # Try json-repair for truncated / malformed JSON
        findings = self._try_json_repair(response_text, file_contents, start_id)
        if findings is not None:
            return _maybe_filter(findings)

        # Try regex fallback
        findings = self._try_regex(response_text, file_contents, start_id)
        if findings is not None:
            return _maybe_filter(findings)

        if not allow_nit_fallback:
            return []

        # NIT wrap: don't filter — unparseable responses need human review
        return self._wrap_as_nit(response_text, start_id)

    def _filter_low_confidence(self, findings: list[Finding]) -> list[Finding]:
        """Remove findings with low confidence per confidence threshold rule."""
        return [f for f in findings if f.confidence != Confidence.LOW]

    # ── Trust model (output-contract approach) ───────────────────────
    #
    # Parsing invariant:
    #
    #   The parser trusts ONLY unambiguous shapes:
    #
    #   1. Code-fenced JSON (```json ... ```)  — explicit container
    #   2. Sentinel-delimited JSON (BEGIN_FINDINGS_JSON ... END_FINDINGS_JSON)
    #   3. Whole-response JSON (the entire text is a valid JSON array/object)
    #
    #   Bare JSON embedded in prose text is the AMBIGUOUS ZONE.  The
    #   parser does NOT attempt to extract it.  Prose-embedded JSON
    #   falls through to regex → NIT-wrap.
    #
    # Why fail closed in the ambiguous zone:
    #
    #   Rounds 10-15 proved that no heuristic (phrase lists, positional
    #   rescue, comma context, content validation) can reliably
    #   distinguish illustrative example JSON from actual findings in
    #   prose.  The same prose patterns ("For example, ...", "Sample
    #   payload: ...") can frame both real findings and format examples.
    #
    #   Error preference: false positives FABRICATE findings (phantom
    #   bugs, phantom security issues).  False negatives merely
    #   NIT-wrap the response, preserving the full text for human
    #   review.  Fabricated findings are strictly worse.
    #
    #   The tuned prompt (REVIEWER_PERSONA + FORMAT_REINFORCEMENT)
    #   produces code-fenced JSON 100% of the time in live validation.
    #   The sentinel contract provides an additional unambiguous path.
    #   Together they eliminate the need to infer intent from prose.
    # ─────────────────────────────────────────────────────────────────

    # Sentinel delimiters for machine-readable finding extraction.
    # Added to FORMAT_REINFORCEMENT and DISCUSS_REINFORCEMENT so the
    # prompt and parser share a contract.
    _SENTINEL_BEGIN = "BEGIN_FINDINGS_JSON"
    _SENTINEL_END = "END_FINDINGS_JSON"

    def _try_json(
        self,
        text: str,
        file_contents: dict[str, str],
        start_id: int,
    ) -> list[Finding] | None:
        """Try to parse JSON findings from trusted containers.

        Trusts: code-fenced JSON, sentinel-delimited JSON, whole-response
        JSON.  Does NOT extract bare JSON from prose (ambiguous zone).
        """
        json_strings = self._extract_json_strings(text)

        all_items: list[dict] = []
        any_parsed = False
        for json_str in json_strings:
            items = self._parse_json_to_items(json_str)
            if items is not None:
                any_parsed = True
                all_items.extend(items)

        if not any_parsed:
            return None

        # Empty JSON array = valid "no findings" response
        if len(all_items) == 0:
            return []

        findings = []
        for i, item in enumerate(all_items):
            finding = self._dict_to_finding(item, file_contents, start_id + i)
            if finding:
                findings.append(finding)

        return findings if findings else None

    def _extract_json_strings(self, text: str) -> list[str]:
        """Extract JSON strings from trusted containers only.

        Collects candidates from all trusted containers:
        1. Code-fenced blocks (```json ... ```)
        2. Sentinel-delimited blocks (BEGIN/END_FINDINGS_JSON)
        Both are checked independently — code fences do not suppress
        sentinel extraction.  Identical content emitted in both containers
        (belt-and-suspenders prompt compliance) is deduplicated so each
        underlying finding gets a single F-NNN id.  Falls back to whole
        stripped text only when neither container is found.

        Bare JSON embedded in prose (e.g., "Example: [{...}]") is NOT
        extracted.  This is the ambiguous zone where illustrative and
        real JSON cannot be distinguished.  Such responses fall through
        to regex → NIT-wrap, which preserves the content without
        fabricating findings.
        """
        results: list[str] = []

        # 1. Code-fenced blocks — support 3+ backtick fences with matching close
        matches = re.findall(r"(`{3,})json\s*\n?(.*?)\n?\1", text, re.DOTALL)
        if matches:
            results.extend(m[1].strip() for m in matches)
        else:
            matches = re.findall(r"(`{3,})\s*\n?(.*?)\n?\1", text, re.DOTALL)
            if matches:
                results.extend(m[1].strip() for m in matches)

        # 2. Sentinel-delimited blocks (always checked, even if code fences found)
        sentinel_pattern = re.compile(
            rf"{re.escape(self._SENTINEL_BEGIN)}\s*\n?(.*?)\n?\s*{re.escape(self._SENTINEL_END)}",
            re.DOTALL,
        )
        sentinel = sentinel_pattern.findall(text)
        if sentinel:
            results.extend(s.strip() for s in sentinel)

        results = self._dedupe_by_content(results)
        if results:
            return results

        # 3. Whole text as JSON (no container found)
        stripped = text.strip()
        if stripped:
            return [stripped]

        return []

    @staticmethod
    def _dedupe_by_content(candidates: list[str]) -> list[str]:
        """Deduplicate JSON candidate strings by whitespace-normalized content.

        Models occasionally emit the same findings in multiple trusted
        containers (e.g., both a code fence and sentinel block).  Without
        dedup the same finding would be assigned two F-NNN ids and inflate
        downstream metrics.  Normalization collapses whitespace so
        semantically identical JSON with differing indentation still
        dedupes.  Order is preserved (first occurrence wins).
        """
        seen: set[str] = set()
        unique: list[str] = []
        for candidate in candidates:
            key = "".join(candidate.split())
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    def _parse_json_to_items(self, json_str: str) -> list[dict] | None:
        """Parse a JSON string into a list of finding dicts.

        Handles arrays directly and unwraps objects that contain a list value.
        Returns None on parse failure, [] for valid empty arrays.
        """
        try:
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return None

        return self._unwrap_to_list(data)

    _WRAPPER_KEYS = ("findings", "results", "items", "issues", "data")

    def _unwrap_to_list(self, data: Any) -> list[dict] | None:
        """Convert parsed JSON data to a list of finding dicts.

        - list → return directly
        - dict → check well-known wrapper keys first, then fall back
          to the sole list value if exactly one exists
        - anything else → None
        """
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Prefer well-known wrapper keys
            for key in self._WRAPPER_KEYS:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Fall back to sole list value (reject ambiguous multi-list objects)
            lists = [v for v in data.values() if isinstance(v, list)]
            if len(lists) == 1:
                return lists[0]

        return None

    def _try_json_repair(
        self,
        text: str,
        file_contents: dict[str, str],
        start_id: int,
    ) -> list[Finding] | None:
        """Try to repair malformed JSON from trusted containers.

        Same trust model as _try_json: only attempts repair on content
        from code fences, sentinels, or whole-text that starts with
        JSON syntax.  Does NOT repair prose-embedded text (that would
        extract bare JSON from the ambiguous zone).
        """
        candidates = self._extract_repair_candidates(text)

        all_items: list[dict] = []
        any_repaired = False
        for json_str in candidates:
            if "[" not in json_str and "{" not in json_str:
                continue
            try:
                repaired = repair_json(json_str, return_objects=True)
            except Exception:
                continue

            items = self._unwrap_to_list(repaired)
            if items is not None:
                if len(items) == 0:
                    continue
                any_repaired = True
                all_items.extend(items)

        if not any_repaired:
            return None

        findings = []
        for i, item in enumerate(all_items):
            if not isinstance(item, dict):
                continue
            finding = self._dict_to_finding(item, file_contents, start_id + i)
            if finding:
                findings.append(finding)

        return findings if findings else None

    def _extract_repair_candidates(self, text: str) -> list[str]:
        """Extract candidates for JSON repair from trusted containers.

        Collects candidates from code fences and sentinel blocks
        independently — code fences do not suppress sentinel
        extraction.  Identical content from both containers is
        deduplicated (see ``_dedupe_by_content``).  Stricter on the
        whole-text fallback: only tries whole text if it starts with
        JSON syntax ([ or {).  Prose starting with words is NOT
        repaired — that would extract bare JSON from the ambiguous zone.
        """
        results: list[str] = []

        # 1. Code-fenced blocks — support 3+ backtick fences with matching close
        matches = re.findall(r"(`{3,})json\s*\n?(.*?)\n?\1", text, re.DOTALL)
        if matches:
            results.extend(m[1].strip() for m in matches)
        else:
            matches = re.findall(r"(`{3,})\s*\n?(.*?)\n?\1", text, re.DOTALL)
            if matches:
                results.extend(m[1].strip() for m in matches)

        # 2. Sentinel-delimited blocks (always checked, even if code fences found)
        sentinel_pattern = re.compile(
            rf"{re.escape(self._SENTINEL_BEGIN)}\s*\n?(.*?)\n?\s*{re.escape(self._SENTINEL_END)}",
            re.DOTALL,
        )
        sentinel = sentinel_pattern.findall(text)
        if sentinel:
            results.extend(s.strip() for s in sentinel)

        results = self._dedupe_by_content(results)
        if results:
            return results

        # 3. Whole text only if it starts with JSON syntax
        stripped = text.strip()
        if stripped and stripped[0] in ("[", "{"):
            return [stripped]

        return []

    # Map model severity strings to our BUG/WARN/NIT taxonomy
    _SEVERITY_MAP: dict[str, Severity] = {
        "BUG": Severity.BUG,
        "WARN": Severity.WARN,
        "NIT": Severity.NIT,
        # Common model variations
        "CRITICAL": Severity.BUG,
        "ERROR": Severity.BUG,
        "HIGH": Severity.BUG,
        "MAJOR": Severity.BUG,
        "WARNING": Severity.WARN,
        "MEDIUM": Severity.WARN,
        "MODERATE": Severity.WARN,
        "LOW": Severity.NIT,
        "MINOR": Severity.NIT,
        "INFO": Severity.NIT,
        "SUGGESTION": Severity.NIT,
        "TRIVIAL": Severity.NIT,
    }

    # Map model category strings to our Category enum
    _CATEGORY_MAP: dict[str, Category] = {
        # Direct matches
        "correctness": Category.CORRECTNESS,
        "design": Category.DESIGN,
        "tests": Category.TESTS,
        "maintainability": Category.MAINTAINABILITY,
        "security": Category.SECURITY,
        "style": Category.STYLE,
        # Common model variations
        "bug": Category.CORRECTNESS,
        "logic": Category.CORRECTNESS,
        "error": Category.CORRECTNESS,
        "vulnerability": Category.SECURITY,
        "injection": Category.SECURITY,
        "credential": Category.SECURITY,
        "credentials": Category.SECURITY,
        "secret": Category.SECURITY,
        "auth": Category.SECURITY,
        "authentication": Category.SECURITY,
        "performance": Category.MAINTAINABILITY,
        "complexity": Category.MAINTAINABILITY,
        "readability": Category.MAINTAINABILITY,
        "naming": Category.STYLE,
        "formatting": Category.STYLE,
        "convention": Category.STYLE,
        "test": Category.TESTS,
        "testing": Category.TESTS,
        "coverage": Category.TESTS,
    }

    @staticmethod
    def _first_str(d: dict[str, Any], keys: tuple[str, ...], default: str = "") -> str:
        """Return the first non-empty string value found across keys."""
        for key in keys:
            val = d.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
        return default

    @staticmethod
    def _first_int(d: dict[str, Any], keys: tuple[str, ...], default: int = 1) -> int:
        """Return the first valid integer value found across keys.

        Skips non-numeric values (empty strings, words, None) rather than
        crashing — model JSON is not schema-validated.
        """
        for key in keys:
            val = d.get(key)
            if val is None:
                continue
            try:
                return int(val)
            except (ValueError, TypeError):
                continue
        return default

    def _dict_to_finding(
        self,
        d: Any,
        file_contents: dict[str, str],
        finding_num: int,
    ) -> Finding | None:
        """Convert a dict to a Finding, computing fingerprint.

        Returns None for non-dict input (e.g. a string or number from malformed JSON).
        """
        if not isinstance(d, dict):
            return None

        message = self._first_str(d, (
            "message", "description", "text", "issue", "title",
            "detail", "details", "finding", "problem",
        ))
        file_path = self._first_str(d, (
            "file", "path", "filename", "filePath", "file_path",
            "fileName", "file_name",
        ))
        # Infer file when model omits it and there's only one file
        if not file_path and len(file_contents) == 1:
            file_path = next(iter(file_contents))
        file_path = file_path or "unknown"

        start_line = self._first_int(d, (
            "start_line", "startLine", "start_line_number",
            "line", "line_number", "lineNumber",
        ), default=1)
        end_line = self._first_int(d, (
            "end_line", "endLine", "end_line_number",
        ), default=0)
        # Fall back to "line" field, then start_line
        if end_line == 0:
            end_line = self._first_int(d, ("line",), default=start_line)

        evidence = self._first_str(d, (
            "evidence", "code", "snippet", "code_snippet", "codeSnippet",
        ))

        rule_id = self._first_str(d, ("rule_id", "ruleId", "rule"))
        if not rule_id:
            rule_id = self._infer_rule_id(message)

        # Get code at location for fingerprint and evidence fallback
        code_at_location = self._get_code_at_location(
            file_contents, file_path, start_line, end_line
        )
        if not evidence and code_at_location:
            evidence = code_at_location
        fingerprint = compute_fingerprint(rule_id, file_path, code_at_location)

        severity_str = str(d.get("severity", "NIT")).upper()
        severity = self._SEVERITY_MAP.get(severity_str, Severity.NIT)

        category_str = self._first_str(d, ("category", "type")).lower()
        category = self._CATEGORY_MAP.get(category_str)
        if category is None:
            category = self._infer_category(message)

        # Category-severity consistency: style findings cannot be runtime bugs.
        if category == Category.STYLE and severity == Severity.BUG:
            severity = Severity.NIT

        confidence_str = str(d.get("confidence", "medium")).lower()
        try:
            confidence = Confidence(confidence_str)
        except ValueError:
            confidence = Confidence.MEDIUM

        status_str = str(d.get("status", "open")).lower()
        try:
            status = FindingStatus(status_str)
        except ValueError:
            status = FindingStatus.OPEN

        return Finding(
            finding_id=f"F-{finding_num:03d}",
            rule_id=rule_id,
            severity=severity,
            category=category,
            message=message,
            primary_location=Location(
                file=file_path,
                start_line=start_line,
                end_line=end_line,
            ),
            related_locations=[],
            fingerprint=fingerprint,
            confidence=confidence,
            evidence=evidence,
            status=status,
        )

    def _try_regex(
        self,
        text: str,
        file_contents: dict[str, str],
        start_id: int,
    ) -> list[Finding] | None:
        """Try regex-based extraction for semi-structured responses."""
        # Match patterns like: **BUG** in `file.py` (line N-M): message
        pattern = r"\*\*(\w+)\*\*\s+in\s+`([^`]+)`\s*\(lines?\s*(\d+)(?:-(\d+))?\):\s*(.+)"
        matches = re.findall(pattern, text)

        if not matches:
            return None

        findings = []
        for i, match in enumerate(matches):
            severity_str, file_path, start_str, end_str, message = match
            start_line = int(start_str)
            end_line = int(end_str) if end_str else start_line
            message = message.strip()

            severity = self._SEVERITY_MAP.get(severity_str.upper(), Severity.NIT)

            rule_id = self._infer_rule_id(message)
            category = self._infer_category(message)
            code_at_location = self._get_code_at_location(
                file_contents, file_path, start_line, end_line
            )
            fingerprint = compute_fingerprint(rule_id, file_path, code_at_location)

            findings.append(
                Finding(
                    finding_id=f"F-{start_id + i:03d}",
                    rule_id=rule_id,
                    severity=severity,
                    category=category,
                    message=message,
                    primary_location=Location(
                        file=file_path,
                        start_line=start_line,
                        end_line=end_line,
                    ),
                    related_locations=[],
                    fingerprint=fingerprint,
                    confidence=Confidence.MEDIUM,
                    evidence=code_at_location,
                    status=FindingStatus.OPEN,
                )
            )

        return findings if findings else None

    def _wrap_as_nit(self, text: str, start_id: int) -> list[Finding]:
        """Wrap unparseable response as a single NIT finding."""
        fingerprint = compute_fingerprint("unparseable-response", "unknown", text)
        return [
            Finding(
                finding_id=f"F-{start_id:03d}",
                rule_id="unparseable-response",
                severity=Severity.NIT,
                category=Category.STYLE,
                message=text,
                primary_location=Location(file="unknown", start_line=1, end_line=1),
                related_locations=[],
                fingerprint=fingerprint,
                confidence=Confidence.LOW,
                evidence="",
                status=FindingStatus.OPEN,
            )
        ]

    def _get_code_at_location(
        self,
        file_contents: dict[str, str],
        file_path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        """Extract code lines from file contents."""
        content = file_contents.get(file_path, "")
        if not content:
            return ""
        lines = content.splitlines()
        # Convert to 0-indexed
        start = max(0, start_line - 1)
        end = min(len(lines), end_line)
        return "\n".join(lines[start:end])

    def _infer_rule_id(self, message: str) -> str:
        """Infer a rule_id from a free-text message."""
        msg_lower = message.lower()
        if "command injection" in msg_lower or ("inject" in msg_lower and "shell" in msg_lower):
            return "command-injection"
        if "sql" in msg_lower and "inject" in msg_lower:
            return "sql-injection"
        if "xss" in msg_lower or "cross-site" in msg_lower:
            return "xss"
        if "hardcod" in msg_lower and ("password" in msg_lower or "secret" in msg_lower or "credential" in msg_lower):
            return "hardcoded-credential"
        if "password" in msg_lower or "credential" in msg_lower or "secret" in msg_lower:
            return "credential-exposure"
        if "arbitrary" in msg_lower and ("code" in msg_lower or "execution" in msg_lower):
            return "unsafe-code-execution"
        if "shell" in msg_lower and "subprocess" in msg_lower:
            return "unsafe-shell-execution"
        if "error" in msg_lower or "exception" in msg_lower:
            return "missing-error-handling"
        if "unused" in msg_lower and "import" in msg_lower:
            return "unused-import"
        if "null" in msg_lower or "none" in msg_lower or "undefined" in msg_lower:
            return "missing-null-check"
        if "naming" in msg_lower or "convention" in msg_lower:
            return "naming-convention"
        if "race" in msg_lower or "concurren" in msg_lower:
            return "race-condition"
        if "security" in msg_lower or "vulnerab" in msg_lower:
            return "security-issue"
        return "code-issue"

    def _infer_category(self, message: str) -> Category:
        """Infer a category from a free-text message.

        Uses multi-word phrases where possible to reduce false positives
        from common words like 'error', 'test', 'none'.
        """
        msg_lower = message.lower()
        # Security: high-signal terms first
        security_terms = [
            "inject", "vulnerab", "security", "credential", "password",
            "secret", "xss", "csrf", "permission", "hardcod",
            "plaintext", "exposure", "exploit", "shell=true",
            "attacker", "malicious", "untrusted", "arbitrary code",
            "remote code", "code execution", "deserialization",
            "command execution",
        ]
        if any(term in msg_lower for term in security_terms):
            return Category.SECURITY
        # Correctness: use specific error types and multi-word phrases
        correctness_terms = [
            "attributeerror", "typeerror", "keyerror", "indexerror",
            "valueerror", "runtimeerror", "zerodivisionerror",
            "raise ", "raises ", "will crash", "will fail",
            "does not exist", "incorrect behavior", "incorrect result",
            "logic error", "off-by-one", "infinite loop",
            "null pointer", "null reference", "nullpointer",
        ]
        if any(term in msg_lower for term in correctness_terms):
            return Category.CORRECTNESS
        # Tests
        test_terms = [
            "test coverage", "missing test", "test case", "unit test",
            "assertion", "test quality", "mock", "test fixture",
        ]
        if any(term in msg_lower for term in test_terms):
            return Category.TESTS
        # Maintainability
        maint_terms = [
            "complexity", "readability", "maintainab", "technical debt",
            "code smell", "duplication", "deeply nested",
        ]
        if any(term in msg_lower for term in maint_terms):
            return Category.MAINTAINABILITY
        # Design
        design_terms = [
            "design", "architect", "coupling", "cohesion",
            "abstraction", "single responsibility", "separation of concern",
        ]
        if any(term in msg_lower for term in design_terms):
            return Category.DESIGN
        return Category.STYLE
