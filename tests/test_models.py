"""Tests for Pydantic models — T007."""

from __future__ import annotations

import json

import pytest

from server.models import (
    Category,
    Confidence,
    DiscussRequest,
    DiscussResult,
    Finding,
    FindingStatus,
    Location,
    MessageSender,
    ReviewBundle,
    ReviewResult,
    ReviewSession,
    ReviewSummary,
    SessionInfo,
    SessionList,
    SessionStatus,
    Severity,
    TokenUsage,
)


class TestEnums:
    def test_session_status_values(self):
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.RESOLVED == "resolved"

    def test_message_sender_values(self):
        assert MessageSender.SYSTEM == "system"
        assert MessageSender.CLAUDE == "claude"
        assert MessageSender.COPILOT == "copilot"

    def test_severity_values(self):
        assert Severity.BUG == "BUG"
        assert Severity.WARN == "WARN"
        assert Severity.NIT == "NIT"

    def test_category_values(self):
        assert Category.CORRECTNESS == "correctness"
        assert Category.DESIGN == "design"
        assert Category.TESTS == "tests"
        assert Category.MAINTAINABILITY == "maintainability"
        assert Category.SECURITY == "security"
        assert Category.STYLE == "style"

    def test_confidence_values(self):
        assert Confidence.HIGH == "high"
        assert Confidence.MEDIUM == "medium"
        assert Confidence.LOW == "low"

    def test_finding_status_values(self):
        assert FindingStatus.OPEN == "open"
        assert FindingStatus.ACCEPTED == "accepted"
        assert FindingStatus.DISMISSED == "dismissed"
        assert FindingStatus.FIXED == "fixed"


class TestLocation:
    def test_valid_location(self):
        loc = Location(file="foo.py", start_line=1, end_line=5)
        assert loc.file == "foo.py"
        assert loc.start_line == 1
        assert loc.end_line == 5

    def test_location_serialization_roundtrip(self):
        loc = Location(file="bar.py", start_line=10, end_line=20)
        data = json.loads(loc.model_dump_json())
        loc2 = Location.model_validate(data)
        assert loc == loc2


class TestFinding:
    def test_valid_finding(self, sample_findings):
        f = sample_findings[0]
        assert f.finding_id == "F-001"
        assert f.severity == Severity.BUG
        assert f.category == Category.CORRECTNESS
        assert f.status == FindingStatus.OPEN

    def test_finding_serialization_roundtrip(self, sample_findings):
        f = sample_findings[0]
        data = json.loads(f.model_dump_json())
        f2 = Finding.model_validate(data)
        assert f.finding_id == f2.finding_id
        assert f.fingerprint == f2.fingerprint
        assert f.severity == f2.severity

    def test_finding_related_locations(self):
        f = Finding(
            finding_id="F-010",
            rule_id="race-condition",
            severity=Severity.BUG,
            category=Category.CORRECTNESS,
            message="Race condition between reader and writer",
            primary_location=Location(file="a.py", start_line=1, end_line=5),
            related_locations=[
                Location(file="b.py", start_line=10, end_line=15),
            ],
            fingerprint="abcdef",
            confidence=Confidence.HIGH,
            evidence="shared_state = {}",
            status=FindingStatus.OPEN,
        )
        assert len(f.related_locations) == 1
        assert f.related_locations[0].file == "b.py"


class TestTokenUsage:
    def test_valid_token_usage(self):
        t = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert t.total_tokens == 150

    def test_token_usage_defaults(self):
        t = TokenUsage()
        assert t.prompt_tokens == 0
        assert t.completion_tokens == 0
        assert t.total_tokens == 0


class TestReviewBundle:
    def test_minimal_bundle(self):
        bundle = ReviewBundle(
            diff="some diff",
            files={"a.py": "content"},
        )
        assert bundle.diff == "some diff"
        assert bundle.test_files is None
        assert bundle.branch is None
        assert bundle.idempotency_token is None

    def test_full_bundle(self, sample_review_bundle):
        assert sample_review_bundle.diff is not None
        assert sample_review_bundle.branch == "feature/add-os-import"


class TestReviewResult:
    def test_valid_result(self, sample_findings):
        result = ReviewResult(
            session_id="sess-1",
            model="gpt-4o",
            findings=sample_findings,
            finding_count=3,
            severity_summary={"BUG": 1, "WARN": 1, "NIT": 1},
        )
        assert result.finding_count == 3
        assert result.severity_summary["BUG"] == 1

    def test_result_serialization_roundtrip(self, sample_findings):
        result = ReviewResult(
            session_id="sess-1",
            model="gpt-4o",
            findings=sample_findings,
            finding_count=3,
            severity_summary={"BUG": 1, "WARN": 1, "NIT": 1},
        )
        data = json.loads(result.model_dump_json())
        result2 = ReviewResult.model_validate(data)
        assert result.session_id == result2.session_id
        assert len(result2.findings) == 3


class TestDiscussModels:
    def test_discuss_request(self):
        req = DiscussRequest(
            session_id="sess-1",
            message="I disagree with F-001",
            additional_files={"extra.py": "code"},
            idempotency_token="tok-1",
        )
        assert req.session_id == "sess-1"
        assert req.additional_files is not None

    def test_discuss_result(self, sample_findings):
        result = DiscussResult(
            response="The finding is valid because...",
            updated_findings=sample_findings,
            finding_count_by_status={"open": 2, "dismissed": 1},
        )
        assert len(result.updated_findings) == 3


class TestSummaryModels:
    def test_review_summary(self, sample_findings):
        summary = ReviewSummary(
            session_id="sess-1",
            status="active",
            model="gpt-4o",
            round_count=2,
            findings=sample_findings,
            finding_count=3,
            by_severity={"BUG": 1, "WARN": 1, "NIT": 1},
            by_category={"correctness": 1, "style": 1, "maintainability": 1},
            by_status={"open": 3},
        )
        assert summary.round_count == 2

    def test_session_info(self):
        info = SessionInfo(
            session_id="sess-1",
            branch="main",
            status="active",
            model="gpt-4o",
            round_count=1,
            finding_count=3,
            by_severity={"BUG": 1, "WARN": 1, "NIT": 1},
            by_category={"correctness": 1},
            created_at="2026-03-14T00:00:00Z",
            updated_at="2026-03-14T00:00:00Z",
        )
        assert info.branch == "main"

    def test_session_list(self):
        sl = SessionList(sessions=[])
        assert len(sl.sessions) == 0
