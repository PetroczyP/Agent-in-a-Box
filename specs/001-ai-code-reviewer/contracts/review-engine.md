# Review Engine Contract: Core Review Server (001)

## Module: `server/review_engine.py`

Orchestrates the review lifecycle: bundle validation, context ordering, Copilot interaction, finding parsing, session management.

## Interface

```python
class ReviewEngine:
    """Core review orchestration. Stateless — delegates persistence to SessionStore."""

    def __init__(
        self,
        copilot: CopilotReviewClient,
        store: SessionStore,
        denylist: ContentDenylist,
    ) -> None: ...

    async def start_review(self, bundle: ReviewBundle) -> ReviewResult:
        """
        1. If idempotency token provided:
           a. Build key: "start_review::{token}"
           b. Check store.get_idempotency_record(key)
           c. If found → deserialize and return cached ReviewResult
           d. If token exists under different key → return idempotency_conflict error
        2. Validate bundle against denylist (FR-006) — checks both files and test_files
        3. Validate non-empty diff
        4. Build reviewer persona prompt (FR-010, FR-011)
        5. Order review context deterministically (FR-008)
        6. Check bundle size against model limit (FR-009) — fail fast before resource allocation
        7. Create Copilot session via create_review_session(system_prompt=persona, model=...)
        8. Send ordered context to Copilot via send_review(session_key, prompt=context)
        9. Parse response into structured findings (using combined files + test_files for fingerprints)
        10. Create session, store it (including file_contents for stable fingerprints across rounds)
        11. Store IdempotencyRecord(key, "start_review", None, token, result_json)
        12. Return ReviewResult
        """

    async def discuss(self, request: DiscussRequest) -> DiscussResult:
        """
        1. Look up session by ID → error if not found or not active
        2. If idempotency token provided:
           a. Build key: "discuss:{session_id}:{token}"
           b. Check store.get_idempotency_record(key)
           c. If found → deserialize and return cached DiscussResult
           d. If token exists under different key → return idempotency_conflict error
        3. Validate additional_files against denylist (FR-007)
        4. Format follow-up prompt with rebuttal + any new files
        5. Send to Copilot via send_followup()
        6. Parse response, update finding statuses
        7. Store updated session
        8. Store IdempotencyRecord(key, "discuss", session_id, token, result_json)
        9. Return DiscussResult
        """

    async def get_summary(self, session_id: str) -> ReviewSummary:
        """Load session, compute summary statistics."""

    async def list_sessions(self) -> SessionList:
        """List all sessions with metadata."""


class ContentDenylist:
    """Validates file paths against configurable glob patterns."""

    DEFAULT_PATTERNS: list[str] = [
        ".env", "*.pem", "*.key", "*credentials*",
        "*secret*", "*.p12", "*.pfx",
    ]

    def __init__(self, patterns: list[str] | None = None) -> None: ...

    def check(self, file_paths: list[str]) -> list[str]:
        """Returns list of denied file paths. Empty = all clear."""


class SessionStore:
    """In-memory session storage for MVP. All state lost on process exit."""

    def __init__(self) -> None: ...

    def save(self, session: ReviewSession) -> None: ...
    def get(self, session_id: str) -> ReviewSession | None: ...
    def list_all(self) -> list[ReviewSession]: ...
    def set_copilot_session(self, key: str, copilot_session: Any) -> None: ...
    def get_copilot_session(self, key: str) -> Any | None: ...
    def save_idempotency_record(self, record: IdempotencyRecord) -> None: ...
    def get_idempotency_record(self, key: str) -> IdempotencyRecord | None: ...
    def token_exists_elsewhere(self, token: str, expected_key: str) -> bool:
        """Check if token is already used under a different composite key (conflict detection)."""
        ...


class FindingParser:
    """Parses Copilot's text response into structured Finding objects."""

    def parse(self, response_text: str, file_contents: dict[str, str]) -> list[Finding]:
        """
        1. Try JSON parsing (if Copilot followed structured output instructions)
        2. Fall back to regex-based extraction
        3. Last resort: wrap entire response as single NIT finding (severity=NIT, category=style)
        Computes fingerprints for each finding.
        """
```

## Prompt Assembly

Prompt assembly is split across two Copilot client calls per `copilot-client.md`:

### Reviewer Persona → `create_review_session(system_prompt=...)`

The system prompt is passed once at session creation. It instructs Copilot to:
- Act as a senior code reviewer
- Classify findings by severity (`BUG`, `WARN`, `NIT`) and category
- Output findings as JSON array for structured parsing
- Include evidence (code quotes) for `BUG` and `WARN` findings
- Use stable `rule_id` values for issue classification
- Reference specific file paths and line numbers

### Review Context → `send_review(prompt=...)`  (FR-008)

The review bundle is assembled into a single ordered context prompt:

1. Project rules and anti-patterns (`conventions`, `anti_patterns`)
2. Spec artifacts (`spec`)
3. Git diff (`diff`)
4. Changed file contents (`files`)
5. Test files (`test_files`)
6. Test results (`test_results`)
7. Free-form context (`context`)
