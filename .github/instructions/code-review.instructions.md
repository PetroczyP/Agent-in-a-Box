---
applyTo: "**"
excludeAgent: "coding-agent"
---

# Code Review Focus Areas

When reviewing code in this repository, prioritize these areas:

## Security Boundary Violations (Critical)

- Any code that gives the container filesystem access to the host repo
- Secrets or credentials leaking into logs, error messages, or responses
- Content denylist bypasses (files matching `.env`, `*.pem`, `*.key`, `*credentials*`, `*secret*`)
- Denylist must check both `files` AND `test_files` in ReviewBundle

## Parser Trust Model Compliance

- JSON extraction must only use trusted containers (```json fences, sentinel delimiters, whole-response JSON)
- Regex patterns for code fences must NOT match language-tagged blocks (```python, ```yaml, etc.)
- `json-repair` must only run on content from trusted containers, never on prose
- Object unwrapping must prefer well-known keys (`findings`, `results`) over blind iteration

## Prompt Consistency

- REVIEWER_PERSONA and FORMAT_REINFORCEMENT must not contradict each other
- DISCUSS_REINFORCEMENT intentionally overrides REVIEWER_PERSONA's "no prose" rule for follow-up messages — this is by design
- Format instructions appear in both system prompt and end of user message (sandwich technique)

## Model Agnosticism

- Never hardcode model IDs — use `list_models()` at runtime
- MCP tool interface must not change based on which inner model is configured
- `ReviewResult.model` must reflect the actual model used (per-review override or selected default)

## Documentation Accuracy

- File paths referenced in docstrings and comments must exist
- Architecture diagrams must reflect current state (MCP stdio), not planned features
- Firewall tables must use hostnames only, not URL paths
