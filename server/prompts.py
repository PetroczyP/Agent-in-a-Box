"""Reviewer persona prompts — T015.

System prompt instructs Copilot to output JSON findings with severity/category/evidence.
Per contracts/review-engine.md Context Ordering section.
"""

from __future__ import annotations

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

- **BUG**: Likely defect that will cause incorrect behavior. MUST include evidence (code quote).
- **WARN**: Potential issue that could cause problems. MUST include evidence (code quote).
- **NIT**: Suggestion or style improvement. Evidence is optional.

## Review Dimensions (category)

Classify each finding into exactly one category:
- **correctness**: Logic errors, bugs, incorrect behavior
- **design**: Architecture issues, abstraction problems, coupling
- **tests**: Missing tests, weak assertions, test quality
- **maintainability**: Readability, complexity, technical debt
- **security**: Vulnerabilities, unsafe patterns, data exposure
- **style**: Naming, formatting, conventions

## Rules

1. Be specific — reference exact file paths and line numbers
2. Use stable rule_id values (e.g., "missing-error-handling", "unused-import")
3. Ground BUG and WARN findings in evidence — quote the specific code
4. If you find no issues, return an empty array: []
5. Do not include meta-commentary outside the JSON array
"""


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
) -> str:
    """Assemble review context in FR-008 deterministic order.

    Order: conventions → anti_patterns → spec → diff → files → test_files → test_results → context
    """
    sections = []

    if conventions:
        sections.append(f"## Project Rules\n\n{conventions}")

    if anti_patterns:
        sections.append(f"## Anti-Patterns\n\n{anti_patterns}")

    if spec:
        sections.append(f"## Spec Artifacts\n\n{spec}")

    sections.append(f"## Git Diff\n\n```diff\n{diff}\n```")

    if files:
        file_section = "## Changed Files\n"
        for path, content in sorted(files.items()):
            file_section += f"\n### {path}\n```\n{content}\n```\n"
        sections.append(file_section)

    if test_files:
        test_section = "## Test Files\n"
        for path, content in sorted(test_files.items()):
            test_section += f"\n### {path}\n```\n{content}\n```\n"
        sections.append(test_section)

    if test_results:
        sections.append(f"## Test Results\n\n```\n{test_results}\n```")

    if context:
        sections.append(f"## Additional Context\n\n{context}")

    return "\n\n".join(sections)
