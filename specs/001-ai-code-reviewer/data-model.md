# Data Model: Core Review Server (001)

**Date**: 2026-03-13
**Source**: spec.md Key Entities + research.md decisions

## Entity Relationship

```
ReviewSession 1──* Message
ReviewSession 1──* Finding
Finding *──1 Location (primary)
Finding *──* Location (related)
```

## Entities

### ReviewSession

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `str` | UUID4, unique identifier |
| `branch` | `str` | Branch name from review bundle |
| `status` | `SessionStatus` | `active` or `resolved` (MVP) |
| `model` | `str` | Model ID used for this review |
| `copilot_session_key` | `str` | Internal key mapping to the live Copilot SDK session object |
| `created_at` | `datetime` | Session creation time (UTC) |
| `updated_at` | `datetime` | Last activity time (UTC) |
| `messages` | `list[Message]` | Ordered conversation history |
| `findings` | `list[Finding]` | All findings, keyed by `finding_id` |
| `idempotency_token` | `str | None` | Client-provided dedup token for `start_review` |
| `file_contents` | `dict[str, str]` | Original file + test_file contents for stable fingerprints across discuss rounds |
| `token_usage` | `TokenUsage` | Cumulative token accounting |

**Status enum (MVP)**:
- `active` — review in progress
- `resolved` — all findings addressed or session explicitly closed

### Message

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | `str` | UUID4 |
| `sender` | `MessageSender` | `system`, `claude`, `copilot` |
| `content` | `str` | Message text |
| `timestamp` | `datetime` | UTC |
| `attached_files` | `dict[str, str] | None` | `{path: content}` for files attached in `discuss` |
| `idempotency_token` | `str | None` | Client-provided dedup token |

### Finding

| Field | Type | Description |
|-------|------|-------------|
| `finding_id` | `str` | Sequential within session: `F-001`, `F-002`, etc. |
| `rule_id` | `str` | Issue class: `race-condition`, `missing-error-handling`, etc. |
| `severity` | `Severity` | `BUG`, `WARN`, `NIT` |
| `category` | `Category` | `correctness`, `design`, `tests`, `maintainability`, `security`, `style` |
| `message` | `str` | Human-readable description |
| `primary_location` | `Location` | Where the issue occurs |
| `related_locations` | `list[Location]` | Additional relevant locations |
| `fingerprint` | `str` | SHA-256 truncated hash of `rule_id` + normalized code |
| `confidence` | `Confidence` | `high`, `medium`, `low` |
| `evidence` | `str` | Code quote or explanation grounding the finding |
| `status` | `FindingStatus` | `open`, `accepted`, `dismissed`, `fixed` |

### Location

| Field | Type | Description |
|-------|------|-------------|
| `file` | `str` | File path relative to repo root |
| `start_line` | `int` | 1-based start line |
| `end_line` | `int` | 1-based end line |

### TokenUsage

| Field | Type | Description |
|-------|------|-------------|
| `prompt_tokens` | `int` | Total prompt tokens used |
| `completion_tokens` | `int` | Total completion tokens used |
| `total_tokens` | `int` | Sum |

## Enums

```python
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
```

### IdempotencyRecord

Stores an immutable snapshot of the original response for a given idempotency key. The key is a composite of `(tool, session_id, token)` to prevent cross-tool and cross-session replay. Ensures duplicate calls return the exact same result regardless of how the session has evolved since.

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Composite key: `"{tool}:{session_id or ''}:{token}"` |
| `tool` | `str` | Which tool: `start_review` or `discuss` |
| `session_id` | `str | None` | `None` for `start_review` (session doesn't exist yet), session ID for `discuss` |
| `token` | `str` | Client-provided idempotency token |
| `result_snapshot` | `str` | JSON-serialized original response (`ReviewResult` or `DiscussResult`) |
| `created_at` | `datetime` | When the original request was processed |

**Scoping rules:**
- `start_review`: key = `"start_review::{token}"` — token alone is sufficient since no session exists yet
- `discuss`: key = `"discuss:{session_id}:{token}"` — scoped to session to prevent replaying one session's result in another
- If a token is reused with a different tool or session, return an `idempotency_conflict` error (not a replay)

## Storage

MVP uses **in-memory dicts** within the MCP server process. MCP stdio is a long-lived connection — all tool calls for one Claude Code session flow through the same process, so in-memory state persists across `start_review` → `discuss` → `get_review_summary` calls. Sessions are ephemeral — lost when the MCP process ends or the container restarts, per FR-015.

```python
class SessionStore:
    """In-memory session storage for MVP."""
    _sessions: dict[str, ReviewSession]                    # session_id → session
    _copilot_sessions: dict[str, CopilotSession]           # copilot_session_key → live SDK session object
    _idempotency_records: dict[str, IdempotencyRecord]     # composite key → immutable result snapshot
```

Persistent storage (SQLite) is deferred to spec 003 when the web dashboard needs cross-process session access.
