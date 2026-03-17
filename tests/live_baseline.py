"""Baseline validation — T030.

Runs the ORIGINAL (pre-spec-008) prompt against live Copilot to establish
the "before" state for comparison with post-change metrics.

Usage: docker exec $(docker compose ps -q review-server) python tests/live_baseline.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time


# Original REVIEWER_PERSONA from main branch (before spec 008 changes).
# No few-shot examples, no FORMAT_REINFORCEMENT.
ORIGINAL_REVIEWER_PERSONA = """You are a senior code reviewer performing a thorough code review.

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


# Original build_review_context without reinforce_format parameter
def original_build_review_context(*, diff: str, files: dict[str, str]) -> str:
    """Original context builder from main — no FORMAT_REINFORCEMENT."""
    sections = []
    fence = "```"
    sections.append(f"## Git Diff\n\n{fence}diff\n{diff}\n{fence}")
    if files:
        file_section = "## Changed Files\n"
        for path, content in sorted(files.items()):
            file_section += f"\n### {path}\n{fence}\n{content}\n{fence}\n"
        sections.append(file_section)
    return "\n\n".join(sections)


async def run_baseline():
    """Run T030 baseline with original prompt."""
    sys.path.insert(0, "/app")

    from server.copilot_client import CopilotReviewClient
    from server.finding_parser import FindingParser

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("FAIL: GITHUB_TOKEN not set")
        return False

    client = CopilotReviewClient()
    await client.start(github_token=token)
    if not client.is_connected:
        print("FAIL: Not connected")
        return False

    print(f"Model: {client.selected_model}")

    # Load validation samples
    with open("tests/fixtures/validation_samples/expected.json") as f:
        samples_data = json.load(f)

    parser = FindingParser()

    print("=" * 60)
    print("T030: BASELINE — Original prompt (pre-spec-008)")
    print("=" * 60)

    results = []
    for sample in samples_data["samples"]:
        file_name = sample["file"]
        diff = sample["diff"]
        with open(f"tests/fixtures/validation_samples/{file_name}") as f:
            file_content = f.read()

        files = {file_name: file_content}
        context = original_build_review_context(diff=diff, files=files)

        print(f"\n  Reviewing: {file_name}")
        try:
            session_key = await client.create_review_session(
                system_prompt=ORIGINAL_REVIEWER_PERSONA, model=None
            )
            t0 = time.time()
            response = await client.send_review(
                session_key=session_key, prompt=context, timeout=60.0
            )
            elapsed = time.time() - t0
        except Exception as e:
            print(f"    ERROR: {type(e).__name__} — {e}")
            results.append({"file": file_name, "error": str(e), "parse_method": None})
            continue

        print(f"    Response time: {elapsed:.1f}s")
        print(f"    Response preview: {response[:300]}...")

        json_findings = parser._try_json(response, files, 1)
        if json_findings is not None:
            parse_method = "_try_json"
            findings = json_findings
        else:
            repair_findings = parser._try_json_repair(response, files, 1)
            if repair_findings is not None:
                parse_method = "_try_json_repair"
                findings = repair_findings
            else:
                regex_findings = parser._try_regex(response, files, 1)
                if regex_findings is not None:
                    parse_method = "_try_regex"
                    findings = regex_findings
                else:
                    parse_method = "_wrap_as_nit"
                    findings = parser._wrap_as_nit(response, 1)

        print(f"    Parse method: {parse_method}")
        print(f"    Findings: {len(findings)}")
        for finding in findings:
            print(f"      [{finding.severity.value}] [{finding.category.value}] {finding.rule_id}: {finding.message[:80]}")

        results.append({
            "file": file_name,
            "parse_method": parse_method,
            "findings": findings,
            "expected": sample["expected_findings"],
        })

    # Score
    valid = sum(1 for r in results if not r.get("error"))
    json_success = sum(1 for r in results if r.get("parse_method") == "_try_json")
    nit_wrap = sum(1 for r in results if r.get("parse_method") == "_wrap_as_nit")
    severities = set()
    total_expected = 0
    total_matched = 0
    for r in results:
        if r.get("error"):
            continue
        for f in r.get("findings", []):
            severities.add(f.severity.value)
        remaining = list(r.get("findings", []))
        for expected in r.get("expected", []):
            total_expected += 1
            for i, f in enumerate(remaining):
                if f.severity.value == expected["severity"].upper() and f.category.value == expected["category"].lower():
                    total_matched += 1
                    remaining.pop(i)
                    break

    print()
    print("=" * 60)
    print("BASELINE SCORES (original prompt)")
    print("=" * 60)
    print(f"  JSON parse rate:  {json_success}/{valid} = {json_success/valid*100:.0f}%" if valid else "  N/A")
    print(f"  NIT-wrap rate:    {nit_wrap}/{valid} = {nit_wrap/valid*100:.0f}%" if valid else "  N/A")
    print(f"  Severity levels:  {severities} = {len(severities)}")
    print(f"  Classification:   {total_matched}/{total_expected} = {total_matched/total_expected*100:.0f}%" if total_expected else "  N/A")

    await client.stop()
    return True


if __name__ == "__main__":
    success = asyncio.run(run_baseline())
    sys.exit(0 if success else 1)
