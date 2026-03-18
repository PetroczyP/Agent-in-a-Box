# Research — 008-prompt-tuning

**Date**: 2026-03-16

## Decision 1: Few-Shot Example Strategy

**Decision**: Two-layer approach. Layer 1 (baked-in): 2 generalized format examples in `REVIEWER_PERSONA` — one BUG finding, one clean empty array. Layer 2 (optional): Users provide project-specific tuning via existing `conventions`/`context` MCP parameters.

**Rationale**: AgentinaBox is project-agnostic (Constitution Principle I). The baked-in examples teach Copilot *output format*, not project-specific review patterns. Users who want to customize review behavior already have `ReviewBundle.conventions` and `ReviewBundle.context` for that — no new API surface needed.

**Alternatives Rejected**:
- 3 examples (BUG+WARN+NIT): Consumes too much prompt budget for marginal format compliance gain. The schema definition + 2 examples is sufficient.
- 0 baked-in examples (user-provided only): Breaks "works out of the box" guarantee. New users would get conversational text.
- New MCP parameter for few-shot examples: Violates YAGNI (Principle VI). Existing params cover this.

**Source**: Real Copilot review findings from [PetroczyP/explainIT-Home-Page PR #137](https://github.com/PetroczyP/explainIT-Home-Page/pull/137) used to derive generalized example patterns.

## Decision 2: Lenient JSON Parser Library

**Decision**: Use `json-repair` (PyPI: [json-repair](https://pypi.org/project/json-repair/)) for FR-007 (truncated JSON repair). No version pin — use `json-repair>=0.50.0` to allow patch updates.

**Rationale**: `json-repair` is purpose-built for repairing LLM-generated JSON. It handles: unclosed brackets/braces, trailing commas, single quotes, unquoted keys, truncated strings. Pure Python, zero dependencies, actively maintained. This is the most targeted solution for the problem.

**Alternatives Considered**:
- `partialjson` (1M+ downloads): Focuses on streaming partial JSON parsing. Good for real-time streams, but our use case is post-hoc repair of complete (but truncated) responses. `json-repair` is a better fit.
- `json5` / `pyjson5`: Handles JSON5 superset (comments, trailing commas) but not truncated JSON. Different problem.
- `demjson3`: Full-featured but heavyweight. Last updated less frequently. Overkill for our use case.
- Simple bracket closing (no library): Too fragile — doesn't handle truncated strings, trailing commas, or partial objects. Fails for real-world truncation patterns.

**Constitution Check**: Adding `json-repair` is a new dependency. Principle VI (YAGNI) applies — but FR-007 explicitly requires JSON repair, and rolling our own would be more code and less reliable than a focused library. Justified.

## Decision 3: GitHub PAT for Copilot SDK

**Decision**: Fine-grained PAT with `Copilot Requests` permission (Account permissions section). The permission is called "Copilot Requests" and is found under Account permissions when creating a fine-grained token at github.com/settings/personal-access-tokens/new.

**Rationale**: Web research confirmed:
- Fine-grained PATs (prefix `github_pat_`) support `Copilot Requests` as an Account permission
- Classic PATs (`ghp_`) do NOT have this permission scope
- Known issue: The permission does not appear for organization-owned tokens (only personal account)
- The permission enables making Copilot requests charged against the user's premium request allowance

**For testing**: Peter has a `GITHUB_TOKEN` in `.env`. This needs to be verified as a fine-grained PAT with `Copilot Requests` permission. If it's a classic PAT, it won't work with the Copilot SDK.

**Sources**: [GitHub Docs - Managing PATs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens), [Copilot CLI Auth Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli), [copilot-cli#223](https://github.com/github/copilot-cli/issues/223)

## Decision 4: Discuss Reinforcement Format

**Decision**: Structured separator approach. Follow-up prompt includes a suffix asking Copilot to: respond conversationally first, then include any new/updated findings as a JSON array in a ```json code fence at the end.

**Rationale**: The parser already extracts JSON from code fences (finding_parser.py:62-64). A structured separator ("respond conversationally, then JSON at the end") leverages existing parsing capabilities while giving Copilot clear format guidance.

**Alternatives Rejected**:
- Natural suffix only ("include findings as JSON"): Too vague — Copilot might inline JSON in the middle of prose.
- JSON-only follow-ups: Breaks `DiscussResult.response` contract from spec 001 (must be conversational text).

## Decision 5: Prompt Iteration Strategy

**Decision**: Design includes explicit iteration loops. Build phase tasks will include:
1. Baseline measurement (current prompt, live Copilot)
2. Apply changes incrementally (few-shot → reinforcement → parser)
3. Measure after each change
4. Iterate on prompt wording based on live results

**Rationale**: Prompt engineering is empirical. A single design-then-implement pass will not achieve SC-001 (80% JSON parse) or SC-006 (70% classification accuracy). The build phase must be structured as hypothesis → test → revise cycles.

## Decision 6: Format Reinforcement Placement

**Decision**: `build_review_context()` appends a `FORMAT_REINFORCEMENT` constant as the final section, after all review context. This is a separate constant from `REVIEWER_PERSONA` (system prompt).

**Rationale**: Placing format reinforcement at the end of the user message (after all context) is a proven technique — it's the last thing the model reads before generating, maximizing compliance. Keeping it as a separate constant from the system prompt allows independent tuning.

**Integration point**: `build_review_context()` in `server/prompts.py` — add optional `reinforce_format: bool = True` parameter that appends the suffix.
