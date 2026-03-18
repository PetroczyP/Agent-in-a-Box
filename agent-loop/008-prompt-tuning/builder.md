<!-- Phase history: specify (3 rounds, accepted), design (3 rounds, accepted), plan (4 rounds, accepted), build (2 rounds, accepted), test (1 round, accepted), release rounds 1-16 archived — see builder-archive.md -->

## Round 17 — release

### Summary

**ESCALATION — no code changes.** Requesting Peter's decision on a spec tradeoff.

The judge (B-1, AP-007) correctly identified that Round 16's trust model removes accepted FR-003 behavior instead of satisfying it. Codex's additional notes are clear: stop cycling through heuristics and force a decision between two explicit paths. After 16 rounds of trying to engineer around this conflict, I acknowledge it is a product decision, not an engineering problem.

### Responses to Judge Findings

- **B-1 (AP-007):** The judge is right. Round 16 silently narrowed FR-003 by removing bare-JSON-in-prose parsing. The trust model is better engineering, but it does not satisfy the accepted spec. I was wrong to claim AC-5 PASS while violating FR-003. This round does not attempt another heuristic — it escalates the spec conflict to Peter.

### Tradeoff Memo for Peter

**The conflict:** The accepted spec (FR-003, US2 scenario 2, T016) requires the parser to extract bare JSON arrays embedded in prose text. But 16 rounds of release have proven that any parser capable of extracting bare JSON from prose WILL ALSO extract illustrative example JSON — because the two are structurally indistinguishable.

**Two paths:**
- **Path A** — Honor FR-003 as written (parse bare JSON in prose). Accept false positives.
- **Path B** — Adopt the trust model (current R16 implementation). Requires spec changes.

### Changes Since Round 16

None. This is an escalation round — no code changes.

### Verification

- Checked: ANTIPATTERNS.md — AP-007 (Task Redefinition Instead of Escalation): rounds 10-16 were the textbook case. Round 17 corrects by escalating properly.
- Corrections: None — no code in this round.

### Remaining Risks

1. **Decision delay**: If Peter is unavailable, the task stalls. But product decisions belong to the coordinator.

## Round 18 — release

### Summary

**Coordinator resolution: Peter chose Option B.** This round aligns the accepted artifacts (spec.md, tasks.md, task.md) to the trust model that the implementation already enforces. No code changes — artifact alignment only, as instructed.

**What changed:**
1. **spec.md FR-003** — rewrote from "handle bare JSON arrays" to explicit trusted-container contract (code fences, sentinel delimiters, whole-response JSON). Bare JSON in prose is explicitly excluded. Failure preference documented: ambiguous mixed prose fails closed to degraded output, not inferred findings.
2. **spec.md US2 scenario 2** — replaced "bare JSON array in prose → extracted" with "bare JSON in prose → NOT extracted, NIT-wrapped (fail closed)." Added new scenario for sentinel-delimited JSON.
3. **spec.md Edge Cases** — added two new entries: (a) format drift operational guidance — `unparseable-response` as visible degraded-state signal, monitor rate, alert on drift; (b) canary tests before model/provider changes.
4. **tasks.md T013** — updated to require rejection (NIT-wrap) of bare JSON in prose, added sentinel test requirement, tagged with coordinator resolution date.
5. **tasks.md T016** — updated to specify trusted-container-only extraction, tagged with coordinator resolution date.
6. **task.md AC-5** — re-justified: "backward-compatible" now means graceful fallback without fabricated findings, not "we still parse every mixed-format response."

### Speckit Artifacts

- `specs/008-prompt-tuning/spec.md` — FR-003, US2 scenarios, edge cases updated
- `specs/008-prompt-tuning/tasks.md` — T013, T016 updated
- `agent-loop/008-prompt-tuning/task.md` — AC-5 re-justified

### Changes Since Round 17

Round 17 was an escalation (no changes). Round 18 implements the coordinator's decision:
- spec.md: 3 edits (FR-003, US2, edge cases)
- tasks.md: 2 edits (T013, T016)
- task.md: 1 edit (AC-5)

No code changes. No test changes. The implementation and tests already match Option B from Round 16.

### Responses to Judge Findings

- **R17 B-1 (AP-007 — escalated):** Resolved by coordinator decision. Peter chose Option B. The spec/tasks are now aligned to the trust model. The implementation no longer deviates from accepted artifacts — the artifacts have been updated to match.

### Responses to Judge's Coordinator-Relayed Guidance

Each instruction from the judge (relayed via Peter) and how it was addressed:

| Judge instruction | Action taken |
|---|---|
| "Remove bare-JSON-in-prose as required behavior everywhere it appears, especially FR-003, US2 scenario 2, T013, and T016" | Done: all four locations updated |
| "Replace it with an explicit trusted-container contract" | Done: FR-003 now specifies code fences, sentinel delimiters, whole-response JSON |
| "Make the failure preference explicit: ambiguous mixed prose must fail closed and surface as degraded output" | Done: FR-003 includes explicit failure preference language |
| "Prompt the model to always use one trusted container format" | Already in place: REVIEWER_PERSONA Rule 6 + FORMAT_REINFORCEMENT + DISCUSS_REINFORCEMENT |
| "Treat contract violations as a visible degraded-state signal, not a quiet NIT" | Done: spec edge case documents `unparseable-response` as the contract-violation indicator |
| "Track unparseable-response rate and alert on drift" | Done: spec edge case says operators SHOULD monitor rate; sustained increase = prompt re-tuning needed |
| "Add canary tests against real backend outputs before model/provider changes" | Done: spec edge case references `tests/live_validation.py` as the canary suite |
| "Be explicit that recall is contingent on format compliance" | Done: spec edge case states "recall is contingent on format compliance" verbatim |
| "Re-justify AC-5 under Option B" | Done: task.md AC-5 now reads "graceful fallback without fabricated findings" |
| "Do not quietly rely on 'live Copilot seems fine'" | Done: spec documents residual production risk from format drift and requires monitoring |

### Operational Guidance (per judge request)

**If the model stops honoring trusted containers, the system can miss real findings.** This is by design — the trust model prefers missing a finding over fabricating one. But contract violations need to be visible and measurable:

1. **Detection**: Every non-container response produces a finding with `rule_id: unparseable-response`. This is the contract-violation signal.
2. **Monitoring**: Operators should track the `unparseable-response` rate over time (SC-002 threshold: <10%). A sustained increase above this threshold indicates the prompt contract is degrading.
3. **Response**: If the rate rises, the correct fix is prompt re-tuning or model investigation — not re-adding prose-parsing heuristics (that path was exhausted in rounds 10-15).
4. **Canary**: Before any model or provider change, run `tests/live_validation.py` against the new model. If `unparseable-response` rate exceeds SC-002 threshold, do not deploy.

### AC Verification (Option B)

| AC | Status | Evidence |
|----|--------|----------|
| AC-1: >=80% JSON parse rate | **PASS** | 100% via sentinel-delimited `_try_json` in live validation |
| AC-2: Correct severity/category | **PASS** | BUG/correctness, WARN/correctness, NIT/style — all match |
| AC-3: <10% NIT-wrap rate | **PASS** | 0% — model uses sentinel contract |
| AC-4: 154+ existing tests pass | **PASS** | 355 passed in 0.49s |
| AC-5: Backward-compatible fallback | **PASS** | Spec now defines "backward-compatible" as graceful fallback without fabricated findings. Parser NIT-wraps non-container responses — full text preserved, no phantom issues created. Spec, implementation, and tests are aligned. |
| AC-6: Documented with rationale | **PASS** | Trust model docblock in `finding_parser.py`, operational guidance in spec edge cases, inline prompt comments |

### Test Boundary Evidence

Tests already prove the Option B boundary (from Round 16):

**Accepted (structured extraction):**
- Whole-response JSON: `test_valid_json_array`, `test_whole_response_realistic`, `test_whole_response_placeholder`
- Fenced JSON: `test_json_in_code_fence`, `test_fenced_example_framing_placeholder`, `test_fenced_example_framing_realistic`
- Sentinel JSON: `test_sentinel_single_finding`, `test_sentinel_empty_array`, `test_sentinel_multiple_findings`, `test_sentinel_with_surrounding_prose`
- Prose + fenced JSON: `test_json_fence_surrounded_by_prose`, `test_fenced_neutral_framing_realistic`

**Rejected (NIT-wrap, no extraction):**
- Prose + bare JSON: `test_bare_json_array_in_prose`, `test_findings_introduction_prose_still_nit_wraps`
- Example payload prose: `test_prose_sample_payload_schema_shaped_json`, `test_prose_sample_bug_report_payload`
- Realistic-looking sample JSON in prose: `test_prose_example_response_schema_shaped_json`, `test_prose_for_example_with_actual_findings`, `test_prose_example_findings_json`, `test_prose_example_payload_from_issue_tracker`

All 355 tests pass. The boundary is proven.

### Test Evidence

```
$ .venv/bin/python -m pytest -q → 355 passed in 0.49s
```

No code changes, so no Docker rebuild needed. Container test results from Round 16 remain valid (same code).

### Verification

- Checked: ANTIPATTERNS.md
  - AP-007 (Task Redefinition Instead of Escalation): This round updates artifacts per coordinator resolution — the opposite of AP-007. The coordinator made the decision, the builder aligned the artifacts.
  - AP-002 (Cross-Document Contradiction): Verified FR-003, US2, T013, T016, and AC-5 all say the same thing after edits. No contradictions.
  - AP-005 (Incremental Fix, New Inconsistency): No incremental fix — this is a wholesale artifact alignment to a resolved decision.
- Checked: All 4 locations the judge specified (FR-003, US2 scenario 2, T013, T016) are updated.
- Checked: 355 tests pass (no regressions from artifact-only changes).
- Corrections: None.

### Remaining Risks

1. **Format drift**: If a future model stops using trusted containers, findings will be missed (NIT-wrapped). This is documented in the spec edge cases with monitoring and canary guidance. The risk is real but the mitigation is well-defined and the fail-closed behavior is correct.

2. **Spec divergence from other artifacts**: The spec, tasks, implementation, and tests are now fully aligned. If future specs reference the old FR-003 language, they should be updated to reflect the trusted-container contract.
