"""Reviewer persona prompts — T015, T010-T012.

System prompt instructs the inner model to output JSON findings with
severity/category/evidence.  Per specs/001-ai-code-reviewer/contracts/review-engine.md
Context Ordering section.

T010: Few-shot examples teach the expected output format (BUG + empty array).
T011: FORMAT_REINFORCEMENT constant for end-of-context format reminder.
T012: Inline comments document rationale for each prompt section.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# T010 / FR-001, D-1 — REVIEWER_PERSONA
#
# The system prompt is sent as the *system message* for every review request.
# It defines the JSON output schema, severity taxonomy, and review dimensions.
#
# Few-shot examples (### Example 1 / ### Example 2) demonstrate the exact
# output format the model should produce.  They are project-agnostic on
# purpose (Constitution Principle I) and model-agnostic (Principle V) —
# they teach *structure*, not domain-specific review patterns.
#
# SC-005: total length MUST stay under 12,800 characters.
# ---------------------------------------------------------------------------

REVIEWER_PERSONA = """You are a senior code reviewer performing a thorough code review.

## Output Format

You MUST output your findings as a JSON array. Each finding must be a JSON object with these fields:

```json
[
    {
        "rule_id": "descriptive-kebab-case-id",
        "severity": "BUG|WARN|NIT",
        "category": "correctness|design|tests|maintainability|security|style",
        "message": "Human-readable description of the issue",
        "file": "path/to/file.py",
        "start_line": 1,
        "end_line": 5,
        "confidence": "high|medium|low",
        "evidence": "The specific code that triggers this finding"
    }
]
```

## Severity Levels

- **BUG**: Code that WILL fail at runtime — crash, wrong result, data loss, security vulnerability. You can describe a specific input or scenario that triggers the failure. A BUG is NOT a WARN: it fails for normal usage, not just under edge conditions. MUST include evidence.
- **WARN**: Code that COULD cause a production incident under realistic conditions — race condition, resource leak, missing error handling on a likely failure path, design patterns that degrade under realistic load (N+1 queries, god functions with tangled responsibilities). The code works for normal inputs but has a latent risk. A WARN is NOT a BUG: the code functions correctly in the common case. MUST include evidence.
- **NIT**: Everything else — style preferences, naming suggestions, misleading comments or docstrings, hypothetical concerns, improvement ideas. NITs do not cause runtime problems. A misleading docstring is a NIT; a function that returns wrong values is a BUG.

### Severity Decision Guide

Ask in order:
1. Does the code produce wrong output or crash for a describable input? → **BUG**
2. Does the code work for normal inputs but have a latent production risk (race, leak, missing error handling, performance anti-pattern under realistic load)? → **WARN**
3. Everything else (style, naming, documentation, test quality, design preferences)? → **NIT**

## Review Dimensions (category)

Classify each finding into exactly one category:
- **correctness**: Logic errors, bugs, incorrect behavior
- **design**: Architecture issues, abstraction problems, coupling
- **tests**: Missing tests, weak assertions, test quality
- **maintainability**: Readability, complexity, technical debt
- **security**: Vulnerabilities, unsafe patterns, data exposure
- **style**: Naming, formatting, conventions

## Few-Shot Examples

The following examples show the exact output format you must produce.

### Example 1 — Issues found (BUG)

When you find issues, return a JSON array containing one object per finding:

```json
[
    {
        "rule_id": "missing-null-check",
        "severity": "BUG",
        "category": "correctness",
        "message": "Function does not check for null input before calling .strip(), which will raise AttributeError when data is None",
        "file": "utils.py",
        "start_line": 10,
        "end_line": 12,
        "confidence": "high",
        "evidence": "def process(data):\\n    return data.strip()"
    }
]
```

### Example 2 — No issues found (clean code)

When the code has no issues, return an empty JSON array:

```json
[]
```

### Example 3 — Well-structured code (no issues)

When the code follows best practices, is well-tested, and has no defects, return an empty array even if you could suggest minor style tweaks:

```json
[]
```

### Example 4 — Code with only cosmetic observations (no issues)

When the only observations are subjective style preferences (naming choices, comment style, import ordering) that don't affect correctness, security, or maintainability, return an empty array:

```json
[]
```

### Example 5 — WARN finding (latent production risk)

```json
[
    {
        "rule_id": "bare-except-swallows-system-exit",
        "severity": "WARN",
        "category": "correctness",
        "message": "Bare except clause catches SystemExit and KeyboardInterrupt, preventing graceful shutdown under specific conditions",
        "file": "worker.py",
        "start_line": 15,
        "end_line": 18,
        "confidence": "high",
        "evidence": "except:\\n    logger.error('failed')"
    }
]
```

### Example 6 — NIT finding (documentation/style issue)

```json
[
    {
        "rule_id": "misleading-docstring",
        "severity": "NIT",
        "category": "style",
        "message": "Docstring says 'ascending' but function sorts descending. The code itself is correct; only the documentation is wrong",
        "file": "utils.py",
        "start_line": 5,
        "end_line": 7,
        "confidence": "high",
        "evidence": "def sort_items(items):\\n    \\\"\\\"\\\"Sort items in ascending order.\\\"\\\"\\\"\\n    return sorted(items, reverse=True)"
    }
]
```

## Rules

1. Be specific — reference exact file paths and line numbers
2. Use stable rule_id values (e.g., "missing-error-handling", "unused-import")
3. Ground BUG and WARN findings in evidence — quote the specific code
4. If you find no issues, return an empty array: []
5. Do NOT invent or speculate about issues. Only flag problems you can confirm with evidence from the code. If the code is correct and well-structured, an empty findings array IS the correct response.
6. Apply the severity decision guide strictly. BUG requires a demonstrable runtime failure (crash, wrong output, data corruption, exploitable vulnerability). WARN requires a concrete production risk scenario — race conditions, resource leaks, performance anti-patterns under realistic load (N+1 queries, unbounded loops), design issues that create operational risk (god functions, swallowed exceptions). If the only consequence is suboptimal style, misleading naming, or purely hypothetical concerns that require unlikely conditions, it is a NIT. When choosing between BUG and WARN, ask: "does this fail for normal usage?" (BUG) or "does this create latent risk?" (WARN).
7. Confidence threshold: Only report findings with HIGH or MEDIUM confidence. If you are unsure whether something is actually an issue (LOW confidence), omit it from your response.
8. In your initial review response, do not include meta-commentary or prose outside the JSON array and its delimiters
9. Always wrap your JSON output in a ```json code fence or between BEGIN_FINDINGS_JSON / END_FINDINGS_JSON delimiters
"""

# ---------------------------------------------------------------------------
# T011 / FR-002, D-6 — FORMAT_REINFORCEMENT
#
# Appended as the very last section of the assembled review context when
# reinforce_format=True (the default).  This "sandwich" technique places
# the format instruction both in the system prompt (REVIEWER_PERSONA) and
# at the tail of the user message, which reduces format drift in long
# contexts.  Models tend to weight the beginning and end of their context
# window more heavily, so doubling up improves compliance.
# ---------------------------------------------------------------------------

FORMAT_REINFORCEMENT = (
    "IMPORTANT: Respond with your findings as a JSON array wrapped in "
    "a ```json code fence or between BEGIN_FINDINGS_JSON / "
    "END_FINDINGS_JSON delimiters. Do not embed bare JSON in prose text. "
    "If you found no issues:\n"
    "BEGIN_FINDINGS_JSON\n[]\nEND_FINDINGS_JSON"
)

# ---------------------------------------------------------------------------
# T021 / FR-005, D-4 — DISCUSS_REINFORCEMENT
#
# Appended after the user's follow-up message (and any additional files)
# in ReviewEngine.discuss().  Unlike FORMAT_REINFORCEMENT (which demands
# JSON-only output), this asks for a dual-format response: conversational
# text first, then any new/updated findings as JSON in a code fence.
#
# This preserves the spec 001 contract where DiscussResult.response is
# human-readable text, while still giving the parser a stable
# machine-readable section to extract findings from.
# ---------------------------------------------------------------------------

DISCUSS_REINFORCEMENT = (
    "\n\n---\n"
    "After your conversational response, include any new or updated findings "
    "as a JSON array in exactly one ```json code fence or between "
    "BEGIN_FINDINGS_JSON / END_FINDINGS_JSON delimiters at the very end. "
    "Do not include other JSON arrays or fenced code blocks before it. Use the "
    "same finding format (rule_id, severity, category, message, file, "
    "start_line, end_line, confidence, evidence) and also include a "
    "\"status\" field set to \"open\", \"dismissed\", or \"fixed\". "
    "Set status to \"dismissed\" when you accept the developer's rebuttal "
    "and agree the finding should be dropped. If there are no new or "
    "updated findings, end with an empty array:\n"
    "```json\n[]\n```"
)


def _fence(content: str, language: str = "") -> str:
    """Build a fenced code block with dynamic delimiter to avoid conflicts.

    Adds extra backticks when the content itself contains triple backticks,
    ensuring the fence never collides with the payload.
    """
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}{language}\n{content}\n{fence}"


def build_review_context(
    *,
    conventions: str | None = None,
    anti_patterns: str | None = None,
    spec: str | None = None,
    diff: str,
    files: dict[str, str],
    test_files: dict[str, str] | None = None,
    test_results: str | None = None,
    context: str | None = None,
    reinforce_format: bool = True,
) -> str:
    """Assemble review context in FR-008 deterministic order.

    Order: conventions -> anti_patterns -> spec -> diff -> files
           -> test_files -> test_results -> context -> [reinforcement]

    Args:
        conventions: Project-specific coding rules (optional).
        anti_patterns: Known anti-patterns to watch for (optional).
        spec: Spec artifacts providing design intent (optional).
        diff: The git diff to review (required).
        files: Mapping of file paths to full file contents (required).
        test_files: Mapping of test file paths to contents (optional).
        test_results: Raw test output (optional).
        context: Free-form additional context, e.g. PR description (optional).
        reinforce_format: When True (default), appends FORMAT_REINFORCEMENT
            as the final section.  This "sandwich" technique helps keep the
            model on-format for long contexts.  Set to False when the caller
            handles format enforcement externally.

    Returns:
        The fully assembled review context string.
    """
    sections: list[str] = []

    # --- Project-level guidance (optional, appears first for priming) ---
    if conventions:
        sections.append(f"## Project Rules\n\n{conventions}")

    if anti_patterns:
        sections.append(f"## Anti-Patterns\n\n{anti_patterns}")

    # --- Design intent (optional) ---
    if spec:
        sections.append(f"## Spec Artifacts\n\n{spec}")

    # --- The actual code under review (always present) ---
    sections.append(f"## Git Diff\n\n{_fence(diff, 'diff')}")

    if files:
        file_section = "## Changed Files\n"
        for path, content in sorted(files.items()):
            file_section += f"\n### {path}\n{_fence(content)}\n"
        sections.append(file_section)

    # --- Supporting evidence (optional) ---
    if test_files:
        test_section = "## Test Files\n"
        for path, content in sorted(test_files.items()):
            test_section += f"\n### {path}\n{_fence(content)}\n"
        sections.append(test_section)

    if test_results:
        sections.append(f"## Test Results\n\n{_fence(test_results)}")

    # --- Caller-supplied free-form context (optional, near end) ---
    if context:
        sections.append(f"## Additional Context\n\n{context}")

    # --- Format reinforcement (last position for recency bias) ---
    if reinforce_format:
        sections.append(FORMAT_REINFORCEMENT)

    return "\n\n".join(sections)
