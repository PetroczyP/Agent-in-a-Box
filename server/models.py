"""Pydantic models for AgentinaBox — T011.

All entities and enums from data-model.md, plus MCP I/O models from contracts/mcp-tools.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---


class SessionStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"


class MessageSender(str, Enum):
    SYSTEM = "system"
    CLAUDE = "claude"
    COPILOT = "copilot"


class Severity(str, Enum):
    BUG = "BUG"
    WARN = "WARN"
    NIT = "NIT"


class Category(str, Enum):
    CORRECTNESS = "correctness"
    DESIGN = "design"
    TESTS = "tests"
    MAINTAINABILITY = "maintainability"
    SECURITY = "security"
    STYLE = "style"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    FIXED = "fixed"


# --- Core Entities ---


class Location(BaseModel):
    file: str
    start_line: int
    end_line: int


class Finding(BaseModel):
    finding_id: str
    rule_id: str
    severity: Severity
    category: Category
    message: str
    primary_location: Location
    related_locations: list[Location] = Field(default_factory=list)
    fingerprint: str
    confidence: Confidence
    evidence: str
    status: FindingStatus = FindingStatus.OPEN


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Message(BaseModel):
    message_id: str
    sender: MessageSender
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attached_files: dict[str, str] | None = None
    idempotency_token: str | None = None


class ReviewSession(BaseModel):
    session_id: str
    branch: str | None = None
    status: SessionStatus = SessionStatus.ACTIVE
    model: str = ""
    copilot_session_key: str = ""
    file_contents: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[Message] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    idempotency_token: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)


class IdempotencyRecord(BaseModel):
    key: str
    tool: str
    session_id: str | None = None
    token: str
    result_snapshot: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- MCP I/O Models ---


class ReviewBundle(BaseModel):
    diff: str
    files: dict[str, str]
    test_files: dict[str, str] | None = None
    spec: str | None = None
    conventions: str | None = None
    anti_patterns: str | None = None
    test_results: str | None = None
    context: str | None = None
    branch: str | None = None
    model: str | None = None
    idempotency_token: str | None = None


class ReviewResult(BaseModel):
    session_id: str
    model: str
    findings: list[Finding]
    finding_count: int
    severity_summary: dict[str, int]


class DiscussRequest(BaseModel):
    session_id: str
    message: str
    additional_files: dict[str, str] | None = None
    idempotency_token: str | None = None


class DiscussResult(BaseModel):
    response: str
    updated_findings: list[Finding]
    finding_count_by_status: dict[str, int]


class SummaryRequest(BaseModel):
    session_id: str


class ReviewSummary(BaseModel):
    session_id: str
    status: str
    model: str
    round_count: int
    findings: list[Finding]
    finding_count: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    by_status: dict[str, int]


class SessionInfo(BaseModel):
    session_id: str
    branch: str | None = None
    status: str
    model: str
    round_count: int
    finding_count: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    created_at: str
    updated_at: str


class SessionList(BaseModel):
    sessions: list[SessionInfo]
