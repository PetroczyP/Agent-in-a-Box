"""Live validation script for spec 008 — Phase 8 tasks (T002b, T030-T035).

Runs INSIDE Docker container against live Copilot.
Usage: docker exec agent-in-a-box python tests/live_validation.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time


async def run_validation():
    """Run all Phase 8 validation tasks."""
    # Ensure we can import server modules
    sys.path.insert(0, "/app")

    from server.copilot_client import CopilotAuthError, CopilotReviewClient
    from server.finding_parser import FindingParser
    from server.prompts import REVIEWER_PERSONA, build_review_context

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("FAIL: GITHUB_TOKEN not set")
        return False

    # ── T002b: PAT Verification Gate ──────────────────────────────────
    print("=" * 60)
    print("T002b: PAT Verification Gate")
    print("=" * 60)

    is_fine_grained = token.startswith("github_pat_")
    token_type = "fine-grained PAT" if is_fine_grained else "not fine-grained"
    print(f"  Token type: {token_type}")

    if not is_fine_grained:
        print("  FAIL: T002b requires a fine-grained PAT (github_pat_ prefix)")
        print("  Check: Create a fine-grained PAT with 'Copilot Requests' Account permission")
        return False

    client = CopilotReviewClient()
    try:
        await client.start(github_token=token)
        if not client.is_connected:
            print("  FAIL: Client not connected after start()")
            return False
        print(f"  Connected: True")
        print(f"  Selected model: {client.selected_model}")
        models = await client.get_available_models()
        print(f"  Available models: {[m['id'] for m in models]}")
        print(f"  T002b: PASS")
    except CopilotAuthError as e:
        print(f"  FAIL: Auth error — {e}")
        print("  Check: Is the PAT fine-grained with 'Copilot Requests' Account permission?")
        return False
    except Exception as e:
        print(f"  FAIL: {type(e).__name__} — {e}")
        return False

    # Load validation samples
    samples_path = "tests/fixtures/validation_samples/expected.json"
    with open(samples_path) as f:
        samples_data = json.load(f)

    samples = samples_data["samples"]
    parser = FindingParser()

    # ── T030/T031: Send validation samples to live Copilot ────────────
    print()
    print("=" * 60)
    print("T030/T031: Live Review — Validation Samples")
    print("=" * 60)

    results = []
    for sample in samples:
        file_name = sample["file"]
        diff = sample["diff"]
        sample_path = f"tests/fixtures/validation_samples/{file_name}"
        with open(sample_path) as f:
            file_content = f.read()

        print(f"\n  Reviewing: {file_name}")

        # Build review context
        files = {file_name: file_content}
        context = build_review_context(diff=diff, files=files)

        # Create session and send review
        try:
            session_key = await client.create_review_session(
                system_prompt=REVIEWER_PERSONA,
                model=None,
            )
            t0 = time.time()
            response = await client.send_review(
                session_key=session_key,
                prompt=context,
                timeout=60.0,
            )
            elapsed = time.time() - t0
        except Exception as e:
            print(f"    ERROR: {type(e).__name__} — {e}")
            results.append({
                "file": file_name,
                "error": str(e),
                "parse_method": None,
                "findings": [],
                "expected": sample["expected_findings"],
            })
            continue

        print(f"    Response time: {elapsed:.1f}s")
        print(f"    Response length: {len(response)} chars")
        print(f"    Response preview: {response[:200]}...")

        # Determine which parse path succeeded
        json_findings = parser._try_json(response, files, 1)
        repair_findings = None
        regex_findings = None
        parse_method = "unknown"

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
        print(f"    Findings count: {len(findings)}")
        for finding in findings:
            print(f"      - [{finding.severity.value}] [{finding.category.value}] {finding.rule_id}: {finding.message[:80]}")

        results.append({
            "file": file_name,
            "parse_method": parse_method,
            "findings": findings,
            "expected": sample["expected_findings"],
            "response_preview": response[:500],
        })

    # ── SC Scoring ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("SC Scoring")
    print("=" * 60)

    total = len(results)
    errors = sum(1 for r in results if r.get("error"))
    valid = total - errors

    # SC-001: >=80% JSON parse rate (_try_json succeeds)
    json_success = sum(1 for r in results if r["parse_method"] == "_try_json")
    json_rate = json_success / valid * 100 if valid > 0 else 0
    sc001_pass = json_rate >= 80
    print(f"  SC-001 (>=80% JSON parse): {json_success}/{valid} = {json_rate:.0f}% — {'PASS' if sc001_pass else 'FAIL'}")

    # SC-002: <10% NIT-wrap rate
    nit_wrap = sum(1 for r in results if r["parse_method"] == "_wrap_as_nit")
    nit_rate = nit_wrap / valid * 100 if valid > 0 else 0
    sc002_pass = nit_rate < 10
    print(f"  SC-002 (<10% NIT-wrap): {nit_wrap}/{valid} = {nit_rate:.0f}% — {'PASS' if sc002_pass else 'FAIL'}")

    # SC-003: 2+ distinct severity levels
    all_severities = set()
    for r in results:
        if not r.get("error"):
            for f in r["findings"]:
                all_severities.add(f.severity.value)
    sc003_pass = len(all_severities) >= 2
    print(f"  SC-003 (2+ severity levels): {all_severities} = {len(all_severities)} — {'PASS' if sc003_pass else 'FAIL'}")

    # SC-006: >=70% classification accuracy (severity AND category match)
    print()
    print("  SC-006 Classification Accuracy:")
    total_expected = 0
    total_matched = 0
    for r in results:
        if r.get("error"):
            continue
        for expected in r["expected"]:
            total_expected += 1
            exp_sev = expected["severity"].upper()
            exp_cat = expected["category"].lower()
            # Check if any finding matches both severity and category
            matched = False
            for finding in r["findings"]:
                if finding.severity.value == exp_sev and finding.category.value == exp_cat:
                    matched = True
                    break
            status = "MATCH" if matched else "MISS"
            print(f"    {r['file']}: expected {exp_sev}/{exp_cat} — {status}")
            if matched:
                total_matched += 1

    accuracy = total_matched / total_expected * 100 if total_expected > 0 else 0
    sc006_pass = accuracy >= 70
    print(f"  SC-006 (>=70% classification): {total_matched}/{total_expected} = {accuracy:.0f}% — {'PASS' if sc006_pass else 'FAIL'}")

    # ── T034: Discuss live validation ─────────────────────────────────
    print()
    print("=" * 60)
    print("T034: Discuss Live Validation")
    print("=" * 60)

    # Use the first successful session for discuss test
    discuss_result_ok = False
    for r in results:
        if r.get("error") or r["parse_method"] == "_wrap_as_nit":
            continue
        # Find the session key for this sample
        file_name = r["file"]
        sample = next(s for s in samples if s["file"] == file_name)
        sample_path = f"tests/fixtures/validation_samples/{file_name}"
        with open(sample_path) as f2:
            file_content = f2.read()

        files = {file_name: file_content}
        context = build_review_context(diff=sample["diff"], files=files)

        # Create a new session for discuss test
        try:
            session_key = await client.create_review_session(
                system_prompt=REVIEWER_PERSONA, model=None
            )
            await client.send_review(session_key=session_key, prompt=context, timeout=60.0)

            # Now send a discuss follow-up
            from server.prompts import DISCUSS_REINFORCEMENT
            follow_up = f"Can you explain the severity of the first finding in more detail?{DISCUSS_REINFORCEMENT}"

            t0 = time.time()
            discuss_response = await client.send_followup(
                session_key=session_key,
                prompt=follow_up,
                timeout=30.0,
            )
            elapsed = time.time() - t0

            print(f"  File: {file_name}")
            print(f"  Response time: {elapsed:.1f}s")
            print(f"  Response length: {len(discuss_response)} chars")
            print(f"  Has conversational text: {len(discuss_response) > 50}")

            # Check if parser can extract findings from discuss response
            discuss_findings = parser.parse(discuss_response, files)
            discuss_json = parser._try_json(discuss_response, files, 1)
            print(f"  Parser found findings: {len(discuss_findings)}")
            print(f"  JSON extractable: {discuss_json is not None}")
            print(f"  Response preview: {discuss_response[:300]}...")
            discuss_result_ok = True
            print("  T034: PASS")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__} — {e}")

        break

    if not discuss_result_ok:
        print("  T034: SKIP (no successful review session to discuss)")

    # ── Summary ───────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  T002b PAT Verification:  PASS (fine-grained PAT)")
    print(f"  SC-001 JSON parse rate:  {json_rate:.0f}% ({'PASS' if sc001_pass else 'FAIL'})")
    print(f"  SC-002 NIT-wrap rate:    {nit_rate:.0f}% ({'PASS' if sc002_pass else 'FAIL'})")
    print(f"  SC-003 Severity levels:  {len(all_severities)} ({'PASS' if sc003_pass else 'FAIL'})")
    print(f"  SC-006 Classification:   {accuracy:.0f}% ({'PASS' if sc006_pass else 'FAIL'})")
    print(f"  T034 Discuss:            {'PASS' if discuss_result_ok else 'SKIP'}")

    all_pass = sc001_pass and sc002_pass and sc003_pass and sc006_pass
    print(f"\n  Overall: {'ALL SC PASS' if all_pass else 'SOME SC FAIL — may need prompt iteration (T033)'}")

    # Clean up
    await client.stop()
    return all_pass


if __name__ == "__main__":
    success = asyncio.run(run_validation())
    sys.exit(0 if success else 1)
