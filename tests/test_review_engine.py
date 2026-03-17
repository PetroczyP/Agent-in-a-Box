"""Tests for review engine — T017, T018, T024-T026, T028, T032."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from server.denylist import ContentDenylist
from server.models import (
    DiscussRequest,
    ReviewBundle,
    Severity,
    SessionStatus,
)
from server.review_engine import BundleTooLargeError, ContentDeniedError, ReviewEngine
from server.store import SessionStore


@pytest.fixture
def engine(mock_copilot_client) -> ReviewEngine:
    return ReviewEngine(
        copilot=mock_copilot_client,
        store=SessionStore(),
        denylist=ContentDenylist(),
    )


# --- T017: start_review tests ---


class TestStartReviewHappyPath:
    async def test_returns_review_result(self, engine, sample_review_bundle):
        result = await engine.start_review(sample_review_bundle)
        assert result.session_id is not None
        assert result.model == "gpt-4o"
        assert isinstance(result.findings, list)
        assert result.finding_count >= 0

    async def test_creates_session_in_store(self, engine, sample_review_bundle):
        result = await engine.start_review(sample_review_bundle)
        session = engine._store.get(result.session_id)
        assert session is not None
        assert session.branch == "feature/add-os-import"

    async def test_severity_summary(self, engine, sample_review_bundle):
        result = await engine.start_review(sample_review_bundle)
        assert isinstance(result.severity_summary, dict)
        # Should contain at least the severities from the mock response
        for key in result.severity_summary:
            assert key in ("BUG", "WARN", "NIT")

    async def test_stores_file_contents_in_session(self, engine, sample_review_bundle):
        """H-3: Session must retain original file contents for stable fingerprints."""
        result = await engine.start_review(sample_review_bundle)
        session = engine._store.get(result.session_id)
        assert "foo.py" in session.file_contents
        assert session.file_contents["foo.py"] == sample_review_bundle.files["foo.py"]
        # test_files should also be stored
        assert "tests/test_foo.py" in session.file_contents


class TestStartReviewZeroFindings:
    """M-1: Zero findings → session status resolved, not active."""

    async def test_zero_findings_marks_session_resolved(self, mock_copilot_client):
        """Spec edge case: review with no findings → session marked resolved."""
        mock_copilot_client.send_review = AsyncMock(return_value="[]")
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
        )
        bundle = ReviewBundle(
            diff="--- a/f.py\n+++ b/f.py\n",
            files={"f.py": "pass"},
            branch="feature/clean",
        )
        result = await engine.start_review(bundle)
        assert result.finding_count == 0

        # Session must be resolved, not active
        session = engine._store.get(result.session_id)
        assert session.status == SessionStatus.RESOLVED

    async def test_nonzero_findings_keeps_session_active(self, engine, sample_review_bundle):
        """Regression: sessions with findings must remain active."""
        result = await engine.start_review(sample_review_bundle)
        assert result.finding_count > 0

        session = engine._store.get(result.session_id)
        assert session.status == SessionStatus.ACTIVE


class TestStartReviewDenylist:
    async def test_rejects_bundle_with_denied_files(self, engine, sample_bundle_with_denied_files):
        with pytest.raises(ContentDeniedError) as exc_info:
            await engine.start_review(sample_bundle_with_denied_files)
        assert isinstance(exc_info.value.denied_files, list)
        assert ".env" in exc_info.value.denied_files

    async def test_denylist_error_lists_denied_files(self, engine):
        bundle = ReviewBundle(
            diff="diff",
            files={".env": "SECRET=abc", "app.py": "print()"},
        )
        with pytest.raises(ContentDeniedError) as exc_info:
            await engine.start_review(bundle)
        assert isinstance(exc_info.value.denied_files, list)

    async def test_rejects_bundle_with_denied_test_files(self, engine):
        """H-1: Denylist must check test_files, not just files."""
        bundle = ReviewBundle(
            diff="diff content",
            files={"app.py": "print()"},
            test_files={".env": "SECRET=abc"},
        )
        with pytest.raises(ContentDeniedError) as exc_info:
            await engine.start_review(bundle)
        assert ".env" in exc_info.value.denied_files

    async def test_denylist_error_returns_structured_list(self, engine):
        """M-1: denied_files must be an actual list, not a stringified Python repr."""
        bundle = ReviewBundle(
            diff="diff",
            files={".env": "SECRET=abc", "credentials.json": "{}"},
        )
        with pytest.raises(ContentDeniedError) as exc_info:
            await engine.start_review(bundle)
        denied = exc_info.value.denied_files
        assert isinstance(denied, list)
        for item in denied:
            assert isinstance(item, str)


class TestStartReviewEmptyDiff:
    async def test_rejects_empty_diff(self, engine):
        bundle = ReviewBundle(diff="", files={"a.py": "code"})
        with pytest.raises(ValueError, match="empty_diff"):
            await engine.start_review(bundle)


class TestStartReviewBundleSize:
    """H-2: FR-009 — must fail fast on oversized bundles."""

    async def test_rejects_oversized_bundle(self, mock_copilot_client):
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
            max_context_chars=100,  # Very low limit for testing
        )
        bundle = ReviewBundle(
            diff="x" * 200,
            files={"a.py": "code"},
        )
        with pytest.raises(BundleTooLargeError) as exc_info:
            await engine.start_review(bundle)
        assert exc_info.value.bundle_size > 100
        assert exc_info.value.model_limit == 100
        assert exc_info.value.guidance  # Must include reduction guidance

    async def test_accepts_bundle_within_limit(self, mock_copilot_client):
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
            max_context_chars=1_000_000,  # Very high limit
        )
        bundle = ReviewBundle(
            diff="small diff",
            files={"a.py": "code"},
        )
        result = await engine.start_review(bundle)
        assert result.session_id is not None


class TestStartReviewIdempotency:
    async def test_duplicate_token_returns_same_result(self, engine, sample_review_bundle):
        sample_review_bundle.idempotency_token = "tok-123"
        result1 = await engine.start_review(sample_review_bundle)
        result2 = await engine.start_review(sample_review_bundle)
        assert result1.session_id == result2.session_id
        assert result1.finding_count == result2.finding_count

    async def test_idempotency_conflict(self, engine, sample_review_bundle):
        sample_review_bundle.idempotency_token = "tok-conflict"
        result = await engine.start_review(sample_review_bundle)

        # Use same token with discuss on the SAME session — should conflict
        # because the token is already used for start_review
        discuss_req = DiscussRequest(
            session_id=result.session_id,
            message="test",
            idempotency_token="tok-conflict",
        )
        with pytest.raises(ValueError, match="idempotency_conflict"):
            await engine.discuss(discuss_req)


class TestStartReviewCopilotErrors:
    async def test_copilot_timeout_raises_retryable(self, engine, sample_review_bundle):
        from server.copilot_client import CopilotTimeoutError
        engine._copilot.send_review = AsyncMock(side_effect=CopilotTimeoutError("timeout"))
        with pytest.raises(CopilotTimeoutError):
            await engine.start_review(sample_review_bundle)

    async def test_copilot_auth_failure_raises_terminal(self, engine, sample_review_bundle):
        from server.copilot_client import CopilotAuthError
        engine._copilot.send_review = AsyncMock(side_effect=CopilotAuthError("bad token"))
        with pytest.raises(CopilotAuthError):
            await engine.start_review(sample_review_bundle)


# --- T018: Prompt construction tests ---


class TestPromptConstruction:
    async def test_create_session_receives_persona_prompt(self, engine, sample_review_bundle):
        """Verify create_review_session gets the reviewer persona with FR-010/FR-011."""
        await engine.start_review(sample_review_bundle)

        engine._copilot.create_review_session.assert_called_once()
        call_kwargs = engine._copilot.create_review_session.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt") or call_kwargs.args[0]

        # FR-010: Must contain all 6 review dimensions
        for category in ["correctness", "design", "tests", "maintainability", "security", "style"]:
            assert category in system_prompt, f"Missing category: {category}"

        # FR-011: Must require evidence for BUG and WARN
        assert "evidence" in system_prompt.lower()
        assert "BUG" in system_prompt
        assert "WARN" in system_prompt

    async def test_send_review_receives_ordered_context(self, engine, sample_review_bundle):
        """Verify send_review gets context in FR-008 order."""
        await engine.start_review(sample_review_bundle)

        engine._copilot.send_review.assert_called_once()
        call_kwargs = engine._copilot.send_review.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs.args[1]

        # FR-008 order: conventions → anti_patterns → spec → diff → files → test_files → test_results → context
        # Since our sample bundle has conventions, spec, diff, files, test_files, test_results, context
        sections = [
            "Project Rules",        # conventions
            "Spec Artifacts",       # spec
            "Git Diff",             # diff
            "Changed Files",        # files
            "Test Files",           # test_files
            "Test Results",         # test_results
            "Additional Context",   # context
        ]
        positions = []
        for section in sections:
            pos = prompt.find(section)
            if pos >= 0:
                positions.append(pos)

        # Verify ordering: each found section should appear after the previous
        for i in range(len(positions) - 1):
            assert positions[i] < positions[i + 1], (
                f"Section order violated: sections found at positions {positions}"
            )


# --- T024: discuss tests ---


class TestDiscussHappyPath:
    async def test_discuss_returns_result(self, engine, sample_review_bundle):
        review_result = await engine.start_review(sample_review_bundle)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="I disagree with F-001",
        )
        result = await engine.discuss(request)
        assert result.response is not None
        assert isinstance(result.updated_findings, list)
        assert isinstance(result.finding_count_by_status, dict)

    async def test_discuss_session_not_found(self, engine):
        request = DiscussRequest(session_id="nonexistent", message="hello")
        with pytest.raises(ValueError, match="session_not_found"):
            await engine.discuss(request)

    async def test_discuss_session_not_active(self, engine, sample_review_bundle):
        review_result = await engine.start_review(sample_review_bundle)
        session = engine._store.get(review_result.session_id)
        session.status = SessionStatus.RESOLVED
        engine._store.save(session)

        request = DiscussRequest(session_id=review_result.session_id, message="hello")
        with pytest.raises(ValueError, match="session_not_active"):
            await engine.discuss(request)

    async def test_discuss_denylist_on_additional_files(self, engine, sample_review_bundle):
        review_result = await engine.start_review(sample_review_bundle)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="Here are more files",
            additional_files={".env": "SECRET=abc"},
        )
        with pytest.raises(ContentDeniedError):
            await engine.discuss(request)


class TestDiscussIdempotency:
    async def test_duplicate_discuss_token_returns_cached(self, engine, sample_review_bundle):
        review_result = await engine.start_review(sample_review_bundle)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="I disagree with F-001",
            idempotency_token="disc-tok-1",
        )
        result1 = await engine.discuss(request)
        result2 = await engine.discuss(request)
        assert result1.response == result2.response

    async def test_discuss_idempotency_conflict(self, engine, sample_review_bundle):
        sample_review_bundle.idempotency_token = "shared-tok"
        await engine.start_review(sample_review_bundle)

        # The token "shared-tok" is now used for start_review
        review_result2 = await engine.start_review(
            ReviewBundle(diff="diff2", files={"b.py": "code"})
        )
        request = DiscussRequest(
            session_id=review_result2.session_id,
            message="test",
            idempotency_token="shared-tok",
        )
        with pytest.raises(ValueError, match="idempotency_conflict"):
            await engine.discuss(request)


# --- T025: Finding stability across discuss rounds ---


class TestFindingStability:
    async def test_finding_ids_preserved_across_discuss(self, engine, sample_review_bundle):
        """AC-7: findings maintain stable finding_id and fingerprint across rounds."""
        review_result = await engine.start_review(sample_review_bundle)
        original_findings = review_result.findings
        original_ids = {f.finding_id for f in original_findings}
        original_fingerprints = {f.finding_id: f.fingerprint for f in original_findings}

        request = DiscussRequest(
            session_id=review_result.session_id,
            message="I disagree with the first finding",
        )
        await engine.discuss(request)

        # Original finding IDs should still exist in the session
        session = engine._store.get(review_result.session_id)
        session_ids = {f.finding_id for f in session.findings}
        for fid in original_ids:
            assert fid in session_ids, f"Finding {fid} lost after discuss"

        # Fingerprints should be preserved for matched findings
        for finding in session.findings:
            if finding.finding_id in original_fingerprints:
                assert finding.fingerprint == original_fingerprints[finding.finding_id]

    async def test_discuss_merges_duplicate_findings(self, engine, sample_review_bundle):
        """H-3: discuss must use original file contents for fingerprints to merge duplicates."""
        review_result = await engine.start_review(sample_review_bundle)

        # Discuss returns the same finding (same rule_id, file, lines)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="I disagree with F-001",
        )
        await engine.discuss(request)

        session = engine._store.get(review_result.session_id)
        # Should NOT have duplicate findings — the same finding should be reconciled
        findings_at_location = [
            f for f in session.findings
            if f.rule_id == "missing-error-handling"
            and f.primary_location.file == "foo.py"
            and f.primary_location.start_line == 2
        ]
        assert len(findings_at_location) == 1, (
            f"Expected 1 finding at foo.py:2 but found {len(findings_at_location)}: "
            f"fingerprint matching likely failed due to missing file contents"
        )


class TestTestFileFingerprintStability:
    """H-2: Findings on test_files must use same file contents for fingerprints in both
    start_review and discuss, preventing duplicates."""

    async def test_test_file_finding_no_duplicate_after_discuss(self, mock_copilot_client):
        """A finding on tests/test_foo.py should not duplicate across discuss rounds."""
        # Mock returns a finding against a test file
        mock_copilot_client.send_review = AsyncMock(
            return_value='[{"rule_id": "missing-assertion", "severity": "WARN", '
            '"category": "tests", "message": "Test has no real assertion", '
            '"file": "tests/test_foo.py", "start_line": 1, "end_line": 2, '
            '"confidence": "high", "evidence": "def test_main():\\n    assert True"}]'
        )
        mock_copilot_client.send_followup = AsyncMock(
            return_value='[{"rule_id": "missing-assertion", "severity": "WARN", '
            '"category": "tests", "message": "Test has no real assertion", '
            '"file": "tests/test_foo.py", "start_line": 1, "end_line": 2, '
            '"confidence": "high", "evidence": "def test_main():\\n    assert True"}]'
        )

        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
        )
        bundle = ReviewBundle(
            diff="diff content",
            files={"app.py": "print()"},
            test_files={"tests/test_foo.py": "def test_main():\n    assert True\n"},
            branch="feature/test",
        )
        result = await engine.start_review(bundle)

        # Discuss with the same finding
        request = DiscussRequest(
            session_id=result.session_id,
            message="I disagree with the finding",
        )
        await engine.discuss(request)

        session = engine._store.get(result.session_id)
        test_findings = [
            f for f in session.findings
            if f.primary_location.file == "tests/test_foo.py"
        ]
        assert len(test_findings) == 1, (
            f"Expected 1 finding on tests/test_foo.py but found {len(test_findings)}: "
            f"initial parse likely used bundle.files only, not combined files+test_files"
        )


class TestModelOverride:
    """M-1: ReviewResult.model must reflect per-review model override."""

    async def test_model_override_reflected_in_result(self, mock_copilot_client):
        mock_copilot_client.selected_model = None  # No default model selected
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
        )
        bundle = ReviewBundle(
            diff="diff content",
            files={"a.py": "code"},
            model="custom-model-v2",
        )
        result = await engine.start_review(bundle)
        assert result.model == "custom-model-v2"

    async def test_model_falls_back_to_selected_model(self, mock_copilot_client):
        mock_copilot_client.selected_model = "gpt-4o"
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
        )
        bundle = ReviewBundle(
            diff="diff content",
            files={"a.py": "code"},
        )
        result = await engine.start_review(bundle)
        assert result.model == "gpt-4o"


# --- T026: get_review_summary tests ---


class TestGetReviewSummary:
    async def test_summary_counts(self, engine, sample_review_bundle):
        review_result = await engine.start_review(sample_review_bundle)
        summary = await engine.get_summary(review_result.session_id)
        assert summary.session_id == review_result.session_id
        assert summary.finding_count == review_result.finding_count
        assert isinstance(summary.by_severity, dict)
        assert isinstance(summary.by_category, dict)
        assert isinstance(summary.by_status, dict)

    async def test_summary_session_not_found(self, engine):
        with pytest.raises(ValueError, match="session_not_found"):
            await engine.get_summary("nonexistent")


# --- T032: list_sessions tests ---


class TestListSessions:
    async def test_list_multiple_sessions(self, engine, sample_review_bundle):
        await engine.start_review(sample_review_bundle)
        bundle2 = ReviewBundle(diff="diff2", files={"b.py": "code"}, branch="feature/other")
        await engine.start_review(bundle2)

        result = await engine.list_sessions()
        assert len(result.sessions) == 2
        branches = {s.branch for s in result.sessions}
        assert "feature/add-os-import" in branches
        assert "feature/other" in branches

    async def test_list_empty(self, engine):
        result = await engine.list_sessions()
        assert len(result.sessions) == 0

    async def test_list_includes_severity_counts(self, engine, sample_review_bundle):
        await engine.start_review(sample_review_bundle)
        result = await engine.list_sessions()
        info = result.sessions[0]
        assert isinstance(info.by_severity, dict)
        assert isinstance(info.by_category, dict)
        assert info.finding_count >= 0


# --- T019-T020: US3 Discuss reinforcement tests ---


class TestDiscussReinforcement:
    """T019: discuss() prompt includes DISCUSS_REINFORCEMENT appended after user message."""

    async def test_discuss_prompt_includes_reinforcement(self, engine, sample_review_bundle):
        """T019: The prompt sent to Copilot via send_followup includes DISCUSS_REINFORCEMENT."""
        from server.prompts import DISCUSS_REINFORCEMENT

        review_result = await engine.start_review(sample_review_bundle)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="I disagree with F-001",
        )
        await engine.discuss(request)

        engine._copilot.send_followup.assert_called_once()
        call_kwargs = engine._copilot.send_followup.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs.args[1]
        assert DISCUSS_REINFORCEMENT in prompt

    async def test_reinforcement_after_user_message(self, engine, sample_review_bundle):
        """T019: Reinforcement comes after user message and additional files."""
        from server.prompts import DISCUSS_REINFORCEMENT

        review_result = await engine.start_review(sample_review_bundle)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="I disagree with F-001",
            additional_files={"extra.py": "print('extra')"},
        )
        await engine.discuss(request)

        call_kwargs = engine._copilot.send_followup.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs.args[1]
        msg_pos = prompt.find("I disagree with F-001")
        extra_pos = prompt.find("extra.py")
        reinforce_pos = prompt.find(DISCUSS_REINFORCEMENT)
        assert msg_pos < reinforce_pos, "Reinforcement must come after user message"
        assert extra_pos < reinforce_pos, "Reinforcement must come after additional files"


class TestDualFormatDiscussParsing:
    """T020: Parser extracts findings from dual-format response (text + JSON fence)."""

    async def test_dual_format_response_parsed(self, mock_copilot_client):
        """Conversational text + JSON code fence at end → parser extracts findings."""
        dual_response = """I looked at the code and I agree with your concern. The exception handling is indeed too broad.

Here are my updated findings:

```json
[{"rule_id": "broad-except", "severity": "WARN", "category": "correctness", "message": "Bare except catches KeyboardInterrupt", "file": "foo.py", "start_line": 2, "end_line": 3, "confidence": "high", "evidence": "except:\\n    pass"}]
```"""
        mock_copilot_client.send_followup = AsyncMock(return_value=dual_response)
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
        )

        bundle = ReviewBundle(
            diff="--- a/foo.py\n+++ b/foo.py",
            files={"foo.py": "try:\n    x = 1\nexcept:\n    pass\n"},
            branch="test",
        )
        review_result = await engine.start_review(bundle)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="What about the exception handling?",
        )
        result = await engine.discuss(request)

        # FR-010: DiscussResult.response contains full text (conversational + JSON)
        assert "I looked at the code" in result.response
        assert "broad-except" in result.response or "```json" in result.response

    async def test_dual_format_preserves_full_response(self, mock_copilot_client):
        """FR-010: DiscussResult.response stores the FULL text, not just JSON."""
        dual_response = "Great question! Let me reconsider.\n\n```json\n[]\n```"
        mock_copilot_client.send_followup = AsyncMock(return_value=dual_response)
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
        )
        bundle = ReviewBundle(diff="diff", files={"a.py": "pass"}, branch="test")
        review_result = await engine.start_review(bundle)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="Reconsider?",
        )
        result = await engine.discuss(request)
        assert result.response == dual_response


class TestDiscussReconciliation:
    """M-1: Verify discuss() drives updated_findings via reconciliation,
    not just preserving raw response text."""

    async def test_discuss_new_finding_appears_in_updated_findings(
        self, mock_copilot_client
    ):
        """When discuss response contains a NEW finding, it should appear
        in DiscussResult.updated_findings alongside originals."""
        # Initial review returns one finding
        review_response = (
            '```json\n'
            '[{"severity": "BUG", "category": "correctness", '
            '"rule_id": "div-by-zero", "message": "Division by zero", '
            '"file": "math.py", "start_line": 5}]\n'
            '```'
        )
        # Discuss adds a second finding
        discuss_response = (
            "Good point, I also noticed another issue.\n\n"
            '```json\n'
            '[{"severity": "WARN", "category": "correctness", '
            '"rule_id": "broad-except", "message": "Bare except catches all", '
            '"file": "math.py", "start_line": 10}]\n'
            '```'
        )
        mock_copilot_client.send_review = AsyncMock(return_value=review_response)
        mock_copilot_client.send_followup = AsyncMock(return_value=discuss_response)
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
        )
        bundle = ReviewBundle(
            diff="--- a/math.py\n+++ b/math.py",
            files={"math.py": "x = 1 / n\ntry:\n    pass\nexcept:\n    pass\n"},
            branch="test",
        )
        review_result = await engine.start_review(bundle)
        assert len(review_result.findings) == 1

        request = DiscussRequest(
            session_id=review_result.session_id,
            message="Any other issues?",
        )
        result = await engine.discuss(request)

        # Reconciliation: original + new finding
        assert len(result.updated_findings) == 2
        rule_ids = {f.rule_id for f in result.updated_findings}
        assert "div-by-zero" in rule_ids
        assert "broad-except" in rule_ids

    async def test_discuss_empty_findings_preserves_originals(
        self, mock_copilot_client
    ):
        """When discuss response has no new findings, originals are preserved."""
        review_response = (
            '```json\n'
            '[{"severity": "BUG", "message": "bug", '
            '"file": "a.py", "start_line": 1}]\n'
            '```'
        )
        discuss_response = "I agree with the finding.\n\n```json\n[]\n```"
        mock_copilot_client.send_review = AsyncMock(return_value=review_response)
        mock_copilot_client.send_followup = AsyncMock(return_value=discuss_response)
        engine = ReviewEngine(
            copilot=mock_copilot_client,
            store=SessionStore(),
            denylist=ContentDenylist(),
        )
        bundle = ReviewBundle(
            diff="diff", files={"a.py": "x=1\n"}, branch="test"
        )
        review_result = await engine.start_review(bundle)
        request = DiscussRequest(
            session_id=review_result.session_id,
            message="Thoughts?",
        )
        result = await engine.discuss(request)

        # Original findings preserved
        assert len(result.updated_findings) == 1
        assert result.updated_findings[0].severity == Severity.BUG
