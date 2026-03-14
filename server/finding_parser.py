"""Finding parser — T014.

Parses Copilot's text response into structured Finding objects.
Strategy: JSON parse → regex fallback → NIT wrap fallback.
Fingerprint: SHA-256 of rule_id + normalized code (research.md Decision 7).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from server.models import (
    Category,
    Confidence,
    Finding,
    FindingStatus,
    Location,
    Severity,
)


def compute_fingerprint(rule_id: str, code_snippet: str) -> str:
    """SHA-256 of rule_id + normalized code, truncated to 16 hex chars."""
    normalized = " ".join(code_snippet.split())
    return hashlib.sha256(f"{rule_id}:{normalized}".encode()).hexdigest()[:16]


class FindingParser:
    """Parses Copilot's text response into structured Finding objects."""

    def parse(
        self,
        response_text: str,
        file_contents: dict[str, str],
        start_id: int = 1,
    ) -> list[Finding]:
        """Parse response into findings. start_id controls F-NNN numbering."""
        # Try JSON first (returns None on parse failure, [] on valid empty array)
        findings = self._try_json(response_text, file_contents, start_id)
        if findings is not None:
            return findings

        # Try regex fallback
        findings = self._try_regex(response_text, file_contents, start_id)
        if findings is not None:
            return findings

        # Last resort: wrap entire response as single NIT
        return self._wrap_as_nit(response_text, start_id)

    def _try_json(
        self,
        text: str,
        file_contents: dict[str, str],
        start_id: int,
    ) -> list[Finding] | None:
        """Try to parse JSON findings from response."""
        # Extract JSON from code fences if present
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        json_str = json_match.group(1).strip() if json_match else text.strip()

        try:
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(data, list):
            return None

        # Empty JSON array = valid "no findings" response
        if len(data) == 0:
            return []

        findings = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            finding = self._dict_to_finding(item, file_contents, start_id + i)
            if finding:
                findings.append(finding)

        return findings if findings else None

    def _dict_to_finding(
        self,
        d: dict[str, Any],
        file_contents: dict[str, str],
        finding_num: int,
    ) -> Finding | None:
        """Convert a dict to a Finding, computing fingerprint."""
        try:
            rule_id = d.get("rule_id", "unknown")
            file_path = d.get("file", "unknown")
            start_line = int(d.get("start_line", 1))
            end_line = int(d.get("end_line", start_line))
            evidence = d.get("evidence", "")

            # Get code at location for fingerprint
            code_at_location = self._get_code_at_location(
                file_contents, file_path, start_line, end_line
            )
            fingerprint = compute_fingerprint(rule_id, code_at_location)

            severity_str = d.get("severity", "NIT").upper()
            severity = Severity(severity_str) if severity_str in Severity.__members__ else Severity.NIT

            category_str = d.get("category", "style").lower()
            try:
                category = Category(category_str)
            except ValueError:
                category = Category.STYLE

            confidence_str = d.get("confidence", "medium").lower()
            try:
                confidence = Confidence(confidence_str)
            except ValueError:
                confidence = Confidence.MEDIUM

            status_str = d.get("status", "open").lower()
            try:
                status = FindingStatus(status_str)
            except ValueError:
                status = FindingStatus.OPEN

            return Finding(
                finding_id=f"F-{finding_num:03d}",
                rule_id=rule_id,
                severity=severity,
                category=category,
                message=d.get("message", ""),
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
        except (KeyError, ValueError, TypeError):
            return None

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

            severity_str = severity_str.upper()
            severity = Severity(severity_str) if severity_str in Severity.__members__ else Severity.NIT

            rule_id = self._infer_rule_id(message)
            code_at_location = self._get_code_at_location(
                file_contents, file_path, start_line, end_line
            )
            fingerprint = compute_fingerprint(rule_id, code_at_location)

            findings.append(
                Finding(
                    finding_id=f"F-{start_id + i:03d}",
                    rule_id=rule_id,
                    severity=severity,
                    category=Category.STYLE,
                    message=message.strip(),
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
        fingerprint = compute_fingerprint("unparseable-response", text)
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
        if "error" in msg_lower or "exception" in msg_lower:
            return "missing-error-handling"
        if "unused" in msg_lower or "import" in msg_lower:
            return "unused-import"
        if "naming" in msg_lower or "convention" in msg_lower:
            return "naming-convention"
        if "race" in msg_lower or "concurren" in msg_lower:
            return "race-condition"
        if "security" in msg_lower or "inject" in msg_lower:
            return "security-issue"
        return "code-issue"
