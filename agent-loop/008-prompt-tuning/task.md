# Task: Prompt Tuning for Structured Copilot Output

**Task ID**: 008-prompt-tuning
**Origin**: Spec 001, deferred task T040
**Phase**: specify
**Created**: 2026-03-15

## Goal

Tune the reviewer persona prompt (`server/prompts.py`) so that GitHub Copilot returns structured JSON findings instead of conversational text. The current `REVIEWER_PERSONA` requests JSON output, but live smoke testing (2026-03-14) showed Copilot ignores the format instructions and returns free-form text. The parser's NIT-wrap fallback keeps the pipeline functional but findings lack meaningful severity/category classification.

## Scope

- Prompt engineering in `server/prompts.py` (REVIEWER_PERSONA and possibly build_review_context)
- Parser improvements in `server/finding_parser.py` if prompt changes require new extraction strategies
- Test updates to validate structured output parsing
- Iterative validation against live Copilot responses

**Out of Scope** (belongs to other specs):
- Changing the Finding model or SARIF structure (spec 001, stable)
- Adding new MCP tools (spec 001, stable)
- Credential management (spec 002)
- Web dashboard (spec 003)
- Fallback backends (spec 006)

## Constraints (from constitution)

1. **Project-Agnostic**: Prompt must remain generic — no hardcoded repo knowledge
2. **Model-Agnostic Interface**: MCP contract unchanged regardless of prompt changes
3. **Test-First**: TDD for any parser changes; live validation for prompt changes
4. **YAGNI**: No premature abstractions — tune the prompt, don't build a prompt framework
5. **Security Boundary**: No secrets in prompts; content denylist unchanged

## Acceptance Criteria

- **AC-1**: Live Copilot returns JSON-parseable findings (FindingParser._try_json succeeds) for at least 80% of review requests
- **AC-2**: Findings include correct severity (BUG/WARN/NIT) and category classification matching the actual code issues
- **AC-3**: FindingParser._wrap_as_nit (last-resort fallback) triggers less than 10% of the time with live Copilot
- **AC-4**: Existing 154+ tests continue to pass (no regressions)
- **AC-5**: Prompt changes are backward-compatible — if Copilot returns text without a trusted container (code fence, sentinel delimiters, or whole-response JSON), the fallback chain handles it gracefully via NIT-wrap WITHOUT fabricating findings. "Backward-compatible" means graceful fallback to degraded output, not "we still parse every mixed-format response." Bare JSON in prose is intentionally not extracted (coordinator resolution: Option B, 2026-03-18)
- **AC-6**: Prompt tuning documented with rationale for each change

## Open Decisions

1. Should we add few-shot examples to the system prompt, or keep it instruction-only?
2. Should we add a "reminder" suffix at the end of the user message (after context) reinforcing JSON format?
3. Does the Copilot SDK support any response_format parameter (like OpenAI's JSON mode)?
4. Should we adjust the parser to handle partial JSON (e.g., JSON mixed with commentary)?

## Spec Path

`specs/008-prompt-tuning/spec.md`
