# Feature Specification: Prompt Tuning for Structured Copilot Output

**Feature Branch**: `008-prompt-tuning`
**Created**: 2026-03-16
**Status**: Draft
**Origin**: Spec 001 deferred task T040

## User Scenarios & Testing

### User Story 1 - Structured Review Findings (Priority: P1)

Claude Code sends a review bundle (diff + files) to the review server via MCP `start_review`. The review server forwards the bundle to Copilot with a system prompt that produces structured JSON findings. Claude Code receives findings with accurate severity (BUG/WARN/NIT), category, file locations, and evidence — not a single NIT-wrapped blob of conversational text.

**Why this priority**: This is the entire purpose of T040. Without structured output, the review server's Finding model, fingerprinting, reconciliation, and severity summary are all meaningless — every finding is `rule_id: unparseable-response, severity: NIT, confidence: low`.

**Independent Test**: Send a review bundle containing a known bug (e.g., division by zero, unclosed file handle) via `start_review`. Verify the response parses as JSON and the finding correctly identifies the bug with `severity: BUG` and `category: correctness`.

**Acceptance Scenarios**:

1. **Given** a diff with a clear bug (e.g., `except: pass` swallowing exceptions), **When** `start_review` is called, **Then** the response parses via `FindingParser._try_json` and contains at least one finding with `severity: BUG` and `category: correctness`.
2. **Given** a diff with only style issues (naming, formatting), **When** `start_review` is called, **Then** the response parses as JSON and findings have `severity: NIT` and `category: style`.
3. **Given** a diff with no issues, **When** `start_review` is called, **Then** the response is a valid JSON empty array `[]`.

---

### User Story 2 - Robust Parsing of Mixed Output (Priority: P2)

Even with improved prompts, Copilot may sometimes wrap JSON in explanatory text (e.g., "Here are my findings:\n```json\n[...]\n```\nLet me know if you need clarification."). The parser must extract the JSON from such mixed output without falling to NIT-wrap.

**Why this priority**: LLMs are non-deterministic. Even a well-tuned prompt won't achieve 100% pure JSON output. The parser needs to handle the realistic middle ground between "pure JSON" and "pure conversational text."

**Independent Test**: Feed the parser a string containing prose before and after a valid JSON array in a code fence. Verify it extracts and parses the JSON correctly.

**Acceptance Scenarios**:

1. **Given** a response with valid JSON inside a ```json code fence surrounded by prose, **When** parsed, **Then** `_try_json` succeeds and returns structured findings.
2. **Given** a response with valid JSON in a sentinel-delimited block (`BEGIN_FINDINGS_JSON` / `END_FINDINGS_JSON`) surrounded by prose, **When** parsed, **Then** `_try_json` succeeds and returns structured findings.
3. **Given** a response with bare JSON embedded in prose (no code fence, no sentinel delimiters), **When** parsed, **Then** the parser does NOT extract it. The response falls through to regex → NIT-wrap (fail closed, degraded output). No findings are fabricated from the ambiguous content.
4. **Given** a response with multiple JSON blocks (e.g., findings split across code fences), **When** parsed, **Then** findings from all blocks are merged.

---

### User Story 3 - Format Reinforcement in Follow-up (Priority: P2)

During `discuss` rounds, Copilot tends to drift away from JSON format even if the initial response was structured. The follow-up prompt must reinforce the expected output format so updated/new findings remain parseable — while preserving the conversational reply that `DiscussResult.response` promises (spec 001 contract).

**Why this priority**: Multi-turn review sessions are a core feature (US2 in spec 001). If only the first response is structured, the reconciliation logic in `discuss` breaks down.

**Dual-format contract**: The `discuss` prompt asks Copilot to respond conversationally AND include a JSON findings section (e.g., in a code fence at the end). `DiscussResult.response` retains the full text (conversational + JSON). The parser extracts findings from the JSON section. This preserves spec 001's MCP contract (`DiscussResult.response: str` = Copilot's response text) while enabling structured finding reconciliation.

**Independent Test**: After `start_review` returns structured findings, call `discuss` with a question about a specific finding. Verify the follow-up response contains both conversational text and parseable JSON for any new or updated findings.

**Acceptance Scenarios**:

1. **Given** an active session from a structured `start_review`, **When** `discuss` is called asking Copilot to reconsider a finding, **Then** `DiscussResult.response` contains conversational text AND the parser extracts updated findings as JSON.
2. **Given** an active session, **When** `discuss` provides additional files for review, **Then** new findings in the response are structured JSON matching the Finding schema, and `DiscussResult.response` includes both the conversational explanation and the JSON section.
3. **Given** an active session, **When** Copilot's follow-up contains only conversational text (no JSON), **Then** the existing fallback chain (regex → NIT-wrap) handles it gracefully — no crash, no regression from spec 001 behavior.

---

### User Story 4 - Prompt Tuning Documentation (Priority: P3)

Prompt changes are documented with rationale, so future maintainers understand why specific phrasing was chosen and can iterate further when Copilot models change.

**Why this priority**: Prompt engineering is empirical — what works today may not work with a future Copilot model update. Without documentation, the next developer will restart from scratch.

**Independent Test**: A developer can read the prompt file and understand the purpose of each section without referring to external docs.

**Acceptance Scenarios**:

1. **Given** the updated `server/prompts.py`, **When** a developer reads it, **Then** each prompt section has inline comments explaining its purpose and why it's phrased that way.

---

### Edge Cases

- What happens when Copilot returns a JSON object (not array) wrapping findings?
  - Parser should unwrap: if response is `{"findings": [...]}`, extract the array.
- What happens when Copilot returns truncated JSON (token limit hit mid-response)?
  - Parser should attempt repair (close open brackets) or fall to regex fallback.
- What happens when Copilot returns findings in a different schema (missing fields, extra fields)?
  - Parser already handles missing fields with defaults (`_dict_to_finding`). Extra fields are ignored.
- What happens when the system prompt grows large due to few-shot examples?
  - Monitor total system prompt size in characters. The existing context budget system uses characters (128K default in `ReviewEngine.__init__`), so prompt size should be measured consistently in characters, not tokens.
- What happens when the existing fallback chain is disrupted by parser changes?
  - The three-tier fallback (JSON → regex → NIT-wrap) MUST be preserved. Parser changes add capabilities to `_try_json`; they MUST NOT remove or weaken the regex or NIT-wrap tiers. Regression tests must cover all three tiers.
- What happens when a different Copilot model is selected that responds differently?
  - Prompt should be model-agnostic. The constitution requires `list_models()` at runtime — prompt must not assume a specific model's behavior.
- What happens when the model stops honoring trusted containers (format drift)?
  - Responses that do not use code fences, sentinel delimiters, or whole-response JSON fall through to NIT-wrap. This is a **visible degraded-state signal**, not a quiet failure. The `rule_id: unparseable-response` tag on NIT-wrapped findings is the contract-violation indicator. Operators SHOULD monitor the rate of `unparseable-response` findings; a sustained increase indicates the prompt contract is no longer being honored and requires prompt re-tuning or model investigation. **Recall is contingent on format compliance** — if the model stops using trusted containers, real findings will be missed (NIT-wrapped instead of structured). This is the correct fail-closed behavior: missing a finding is strictly better than fabricating one.
- What happens before a model or provider change?
  - Canary tests against real backend outputs SHOULD be run before switching models or updating providers. The live validation script (`tests/live_validation.py`) serves as the canary suite. If the unparseable-response rate rises above the SC-002 threshold (<10%), the model change should be investigated before deployment.

## Requirements

### Functional Requirements

- **FR-001**: System MUST include few-shot examples in the system prompt showing the expected JSON output format for a code review finding
- **FR-002**: System MUST add a format reinforcement suffix after the review context in `build_review_context()` reminding the model to output only a JSON array
- **FR-003**: `FindingParser._try_json` MUST extract JSON only from **trusted containers**: (a) code fences (` ```json ... ``` `), (b) sentinel-delimited blocks (`BEGIN_FINDINGS_JSON` / `END_FINDINGS_JSON`), (c) whole-response JSON. Bare JSON embedded in prose MUST NOT be extracted — it falls through to regex → NIT-wrap (fail closed). **Failure preference**: ambiguous mixed prose must surface as degraded output (NIT-wrap preserving full text), not as inferred findings that could fabricate phantom issues
- **FR-004**: `FindingParser._try_json` MUST handle a JSON object wrapper (e.g., `{"findings": [...]}`) by extracting the inner array
- **FR-005**: System MUST add format reinforcement to `discuss` follow-up prompts in `review_engine.py`. The reinforcement MUST request a dual-format response: conversational text followed by a JSON findings section, preserving the `DiscussResult.response` contract from spec 001
- **FR-006**: System SHOULD keep the system prompt (REVIEWER_PERSONA) as short as practical. Size is measured in characters, consistent with the existing context budget system (128K chars in `ReviewEngine`). No hard token limit — the constraint is that REVIEWER_PERSONA + review context must fit within the model's context budget
- **FR-007**: Parser MUST attempt JSON repair for truncated responses (unclosed brackets/braces) before falling to regex
- **FR-008**: All prompt changes MUST include inline documentation explaining the rationale for each section
- **FR-009**: The existing fallback chain (JSON → regex → NIT-wrap) in `FindingParser.parse()` MUST be preserved. Parser changes MUST NOT remove or weaken any fallback tier. Regression tests MUST cover all three parse paths
- **FR-010**: For `discuss` follow-ups, the parser extracts findings from the JSON section of the response. The full response text (conversational + JSON) is stored in `DiscussResult.response` unchanged

### Key Entities

- **REVIEWER_PERSONA** (existing): System prompt constant in `server/prompts.py`. Will be enhanced with few-shot examples and stronger format instructions.
- **FORMAT_REINFORCEMENT** (new): Suffix appended after review context, reinforcing JSON-only output.
- **FindingParser** (existing): Parser class in `server/finding_parser.py`. `_try_json` will be hardened for mixed output.

## Success Criteria

### Measurable Outcomes

- **SC-001**: `FindingParser._try_json` succeeds (returns non-None) for >= 80% of live Copilot responses
- **SC-002**: `FindingParser._wrap_as_nit` (last-resort fallback) fires for < 10% of live Copilot responses
- **SC-003**: Live findings include at least 2 distinct severity levels (not all NIT) when reviewing code with known bugs
- **SC-004**: Existing test suite (154+ tests) passes with zero regressions
- **SC-005**: System prompt (REVIEWER_PERSONA) character count does not exceed 10% of the model context budget (i.e., stays under ~12,800 chars given the 128K default)
- **SC-006**: For a curated validation set of 3+ code samples with known issues (at least one BUG, one WARN, one NIT), at least 70% of live findings match both the expected severity level AND expected category (e.g., a division-by-zero is `BUG`+`correctness`, not `WARN`+`style`). This validates classification accuracy for both dimensions, not just label variety
- **SC-007**: All three parser fallback tiers (JSON, regex, NIT-wrap) have dedicated regression tests that pass
