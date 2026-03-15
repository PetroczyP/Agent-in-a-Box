"""Review engine — T021, T028-T030, T033.

Orchestrates the review lifecycle: bundle validation, context ordering,
Copilot interaction, finding parsing, session management.
Per contracts/review-engine.md.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone

from server.copilot_client import CopilotReviewClient
from server.denylist import ContentDenylist
from server.finding_parser import FindingParser
from server.models import (
    Category,
    DiscussRequest,
    DiscussResult,
    Finding,
    FindingStatus,
    IdempotencyRecord,
    Message,
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
from server.prompts import REVIEWER_PERSONA, build_review_context
from server.store import SessionStore


class ContentDeniedError(ValueError):
    """Raised when bundle contains files matching the content denylist."""

    def __init__(self, denied_files: list[str]):
        self.denied_files = denied_files
        super().__init__("content_denied")


class BundleTooLargeError(ValueError):
    """Raised when assembled review context exceeds the model's context limit."""

    def __init__(self, bundle_size: int, model_limit: int):
        self.bundle_size = bundle_size
        self.model_limit = model_limit
        self.guidance = (
            "Reduce bundle by omitting test_results or limiting files to the most changed"
        )
        super().__init__("bundle_too_large")


class ReviewEngine:
    """Core review orchestration. Stateless — delegates persistence to SessionStore."""

    def __init__(
        self,
        copilot: CopilotReviewClient,
        store: SessionStore,
        denylist: ContentDenylist,
        max_context_chars: int = 128_000,
    ) -> None:
        self._copilot = copilot
        self._store = store
        self._denylist = denylist
        self._parser = FindingParser()
        self._max_context_chars = max_context_chars

    async def start_review(self, bundle: ReviewBundle) -> ReviewResult:
        """Per contracts/review-engine.md steps 1-11."""

        # Step 1: Idempotency check
        if bundle.idempotency_token:
            key = f"start_review::{bundle.idempotency_token}"
            existing = self._store.get_idempotency_record(key)
            if existing:
                return ReviewResult.model_validate_json(existing.result_snapshot)
            if self._store.token_exists_elsewhere(bundle.idempotency_token, key):
                raise ValueError("idempotency_conflict: Token already used for a different request")

        # Step 2: Validate bundle against denylist (FR-006)
        all_paths = list(bundle.files.keys())
        if bundle.test_files:
            all_paths.extend(bundle.test_files.keys())
        denied = self._denylist.check(all_paths)
        if denied:
            raise ContentDeniedError(denied)

        # Step 3: Validate non-empty diff
        if not bundle.diff or not bundle.diff.strip():
            raise ValueError("empty_diff: No changes to review")

        # Step 4: Order review context deterministically (FR-008)
        review_context = build_review_context(
            conventions=bundle.conventions,
            anti_patterns=bundle.anti_patterns,
            spec=bundle.spec,
            diff=bundle.diff,
            files=bundle.files,
            test_files=bundle.test_files,
            test_results=bundle.test_results,
            context=bundle.context,
        )

        # Step 5: Check bundle size against model limit (FR-009)
        context_size = len(review_context)
        if context_size > self._max_context_chars:
            raise BundleTooLargeError(
                bundle_size=context_size,
                model_limit=self._max_context_chars,
            )

        # Step 6: Create Copilot session (after validation — no resource leak)
        session_key = await self._copilot.create_review_session(
            system_prompt=REVIEWER_PERSONA,
            model=bundle.model,
        )

        # Step 7: Send ordered context to Copilot
        response_text = await self._copilot.send_review(
            session_key=session_key,
            prompt=review_context,
            timeout=60.0,
        )

        # Step 8: Parse response into structured findings
        # Use combined file contents (files + test_files) for stable fingerprints (H-2)
        all_file_contents = dict(bundle.files)
        if bundle.test_files:
            all_file_contents.update(bundle.test_files)
        findings = self._parser.parse(response_text, all_file_contents)

        # Step 9: Create session, store it
        session_id = str(uuid.uuid4())
        model = bundle.model or self._copilot.selected_model or "unknown"

        # Zero findings = resolved session (spec edge case, AC-4)
        status = SessionStatus.RESOLVED if len(findings) == 0 else SessionStatus.ACTIVE

        session = ReviewSession(
            session_id=session_id,
            branch=bundle.branch,
            status=status,
            model=model,
            copilot_session_key=session_key,
            file_contents=all_file_contents,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            messages=[
                Message(
                    message_id=str(uuid.uuid4()),
                    sender=MessageSender.SYSTEM,
                    content=review_context,
                ),
                Message(
                    message_id=str(uuid.uuid4()),
                    sender=MessageSender.COPILOT,
                    content=response_text,
                ),
            ],
            findings=findings,
            idempotency_token=bundle.idempotency_token,
            token_usage=TokenUsage(),
        )
        self._store.save(session)
        self._store.set_copilot_session(session_key, session_key)

        # Build result
        severity_summary = self._count_by_severity(findings)
        result = ReviewResult(
            session_id=session_id,
            model=model,
            findings=findings,
            finding_count=len(findings),
            severity_summary=severity_summary,
        )

        # Step 10: Store idempotency record
        if bundle.idempotency_token:
            key = f"start_review::{bundle.idempotency_token}"
            record = IdempotencyRecord(
                key=key,
                tool="start_review",
                session_id=None,
                token=bundle.idempotency_token,
                result_snapshot=result.model_dump_json(),
            )
            self._store.save_idempotency_record(record)

        return result

    async def discuss(self, request: DiscussRequest) -> DiscussResult:
        """Per contracts/review-engine.md steps 1-9."""

        # Step 1: Look up session
        session = self._store.get(request.session_id)
        if session is None:
            raise ValueError("session_not_found")

        # Step 2: Idempotency check (before status guard so cached results work for resolved sessions)
        if request.idempotency_token:
            key = f"discuss:{request.session_id}:{request.idempotency_token}"
            existing = self._store.get_idempotency_record(key)
            if existing:
                return DiscussResult.model_validate_json(existing.result_snapshot)
            if self._store.token_exists_elsewhere(request.idempotency_token, key):
                raise ValueError("idempotency_conflict: Token already used for a different request")

        if session.status != SessionStatus.ACTIVE:
            raise ValueError("session_not_active")

        # Step 3: Validate additional files against denylist (FR-007)
        if request.additional_files:
            denied = self._denylist.check(list(request.additional_files.keys()))
            if denied:
                raise ContentDeniedError(denied)

        # Step 4: Format follow-up prompt
        prompt_parts = [request.message]
        if request.additional_files:
            for path, content in sorted(request.additional_files.items()):
                prompt_parts.append(f"\n### {path}\n```\n{content}\n```")
        prompt = "\n".join(prompt_parts)

        # Step 5: Send to Copilot
        response_text = await self._copilot.send_followup(
            session_key=session.copilot_session_key,
            prompt=prompt,
            timeout=30.0,
        )

        # Step 6: Parse response and reconcile findings (T028)
        # Start with original file contents from the review bundle (H-3)
        file_contents = dict(session.file_contents)
        for msg in session.messages:
            if msg.attached_files:
                file_contents.update(msg.attached_files)
        if request.additional_files:
            file_contents.update(request.additional_files)
        new_findings = self._parser.parse(response_text, file_contents)
        reconciled = self._reconcile_findings(session.findings, new_findings)

        # Step 7: Update session
        session.messages.append(
            Message(
                message_id=str(uuid.uuid4()),
                sender=MessageSender.CLAUDE,
                content=request.message,
                attached_files=request.additional_files,
                idempotency_token=request.idempotency_token,
            )
        )
        session.messages.append(
            Message(
                message_id=str(uuid.uuid4()),
                sender=MessageSender.COPILOT,
                content=response_text,
            )
        )
        session.findings = reconciled
        if all(f.status != FindingStatus.OPEN for f in reconciled):
            session.status = SessionStatus.RESOLVED
        session.updated_at = datetime.now(timezone.utc)
        self._store.save(session)

        # Build result
        status_counts = self._count_by_status(reconciled)
        result = DiscussResult(
            response=response_text,
            updated_findings=reconciled,
            finding_count_by_status=status_counts,
        )

        # Step 8: Store idempotency record
        if request.idempotency_token:
            key = f"discuss:{request.session_id}:{request.idempotency_token}"
            record = IdempotencyRecord(
                key=key,
                tool="discuss",
                session_id=request.session_id,
                token=request.idempotency_token,
                result_snapshot=result.model_dump_json(),
            )
            self._store.save_idempotency_record(record)

        return result

    async def get_summary(self, session_id: str) -> ReviewSummary:
        """Load session, compute summary statistics. T030."""
        session = self._store.get(session_id)
        if session is None:
            raise ValueError("session_not_found")

        # Count discuss rounds (pairs of claude + copilot messages after initial)
        round_count = sum(1 for m in session.messages if m.sender == MessageSender.CLAUDE)

        return ReviewSummary(
            session_id=session.session_id,
            status=session.status.value,
            model=session.model,
            round_count=round_count,
            findings=session.findings,
            finding_count=len(session.findings),
            by_severity=self._count_by_severity(session.findings),
            by_category=self._count_by_category(session.findings),
            by_status=self._count_by_status(session.findings),
        )

    async def list_sessions(self) -> SessionList:
        """List all sessions with metadata. T033."""
        sessions = self._store.list_all()
        infos = []
        for s in sessions:
            round_count = sum(1 for m in s.messages if m.sender == MessageSender.CLAUDE)
            infos.append(
                SessionInfo(
                    session_id=s.session_id,
                    branch=s.branch,
                    status=s.status.value,
                    model=s.model,
                    round_count=round_count,
                    finding_count=len(s.findings),
                    by_severity=self._count_by_severity(s.findings),
                    by_category=self._count_by_category(s.findings),
                    created_at=s.created_at.isoformat(),
                    updated_at=s.updated_at.isoformat(),
                )
            )
        return SessionList(sessions=infos)

    def _reconcile_findings(
        self,
        existing: list[Finding],
        new_findings: list[Finding],
    ) -> list[Finding]:
        """Reconcile new findings with existing ones by fingerprint. T028.

        - Matched by fingerprint: preserve existing finding_id, update status if changed
        - Unmatched new: assign next sequential ID
        - Existing with no match in new: keep as-is (may be dismissed/fixed)
        """
        existing_by_fp = {f.fingerprint: f for f in existing}
        existing_ids = {f.finding_id for f in existing}
        next_id = max(
            (int(f.finding_id.split("-")[1]) for f in existing),
            default=0,
        ) + 1

        reconciled = list(existing)  # Start with all existing
        seen_fps = {f.fingerprint for f in existing}

        for new_f in new_findings:
            if new_f.fingerprint in existing_by_fp:
                # Match found — update status if the new finding has a different status
                matched = existing_by_fp[new_f.fingerprint]
                if new_f.status != FindingStatus.OPEN:
                    # Find and update in reconciled list
                    for i, f in enumerate(reconciled):
                        if f.finding_id == matched.finding_id:
                            reconciled[i] = f.model_copy(update={"status": new_f.status})
                            break
            elif new_f.fingerprint not in seen_fps:
                # New finding — assign next sequential ID
                new_f_copy = new_f.model_copy(
                    update={"finding_id": f"F-{next_id:03d}"}
                )
                reconciled.append(new_f_copy)
                seen_fps.add(new_f.fingerprint)
                next_id += 1

        return reconciled

    @staticmethod
    def _count_by_severity(findings: list[Finding]) -> dict[str, int]:
        counts: dict[str, int] = {"BUG": 0, "WARN": 0, "NIT": 0}
        for f in findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        return counts

    @staticmethod
    def _count_by_category(findings: list[Finding]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.category.value] = counts.get(f.category.value, 0) + 1
        return counts

    @staticmethod
    def _count_by_status(findings: list[Finding]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.status.value] = counts.get(f.status.value, 0) + 1
        return counts
