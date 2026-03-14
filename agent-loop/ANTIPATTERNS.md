# Anti-Patterns Catalog

**Version**: 1.0.0
**Created**: 2026-03-13

Both agents MUST check this catalog before finalizing each round.
The judge SHOULD cite AP-IDs when a finding matches a known anti-pattern.
Either agent SHOULD propose new anti-patterns when a recurring mistake is identified.

## How to Use This File

- **Builder**: Scan before marking `ready_for_judge`. If your output matches any symptoms, fix it first.
- **Judge**: When writing findings, check if the issue matches a cataloged anti-pattern. If so, cite the AP-ID alongside the finding ID (e.g., "H-1 (AP-003): ...").
- **After each round**: Both agents should check whether the round's findings reveal a new anti-pattern worth cataloging.
- **New entries**: Append to the bottom. Use the next available AP-ID. Follow the template below.

## Entry Template

```
## AP-NNN: Short Name

**Applies to**: builder | judge | both
**Phase**: specify, design, plan, build, test, release
**Severity**: blocker | high | medium

**Symptoms**:
- How to detect this in an artifact

**Problem**: Why this is harmful.

**Root cause**: Why agents fall into this trap.

**Correct pattern**: What to do instead.

**First observed**: task-id, round N
```

---

## AP-001: Unverified Verification

**Applies to**: builder
**Phase**: design, build
**Severity**: high

**Symptoms**:
- Verification section cites a source (README, docs, API reference) but the claim doesn't match what the source actually says
- "Confirmed via X" without having actually checked X
- Verification claims that are copy-pasted assumptions, not checked facts

**Problem**: False verification is worse than no verification — it gives the judge (and Peter) false confidence that a design decision is grounded. When the judge independently checks the source and finds a mismatch, trust erodes and rounds are wasted.

**Root cause**: The builder wants to appear thorough and fills in the Verification section with plausible-sounding claims rather than actually visiting the source. Pressure to complete the round quickly overrides intellectual honesty.

**Correct pattern**: Only claim verification for sources you actually checked in this round. If you haven't verified something, say "Assumed based on [secondary source] — needs build-phase validation" instead of "Confirmed via [primary source]." Honest uncertainty is always better than false certainty.

**First observed**: 001-ai-code-reviewer, design round 3

---

## AP-002: Cross-Document Contradiction

**Applies to**: builder
**Phase**: design, plan
**Severity**: high

**Symptoms**:
- Two design documents make incompatible statements about the same topic
- A fix applied to one document (e.g., contracts/) isn't propagated to related documents (e.g., research.md)
- "Decision X" in research.md says one thing; the contract that implements Decision X says another

**Problem**: The judge must review multiple documents for consistency. Contradictions waste a full round — the builder fixes the specific finding, but the underlying contradiction persists or shifts to a different pair of documents.

**Root cause**: The builder fixes the document the judge cited but doesn't scan related documents for the same assumption. Each round addresses the symptom, not the root inconsistency.

**Correct pattern**: After addressing any judge finding, grep for related terms across all design documents. Ask: "Did I say something different about this topic elsewhere?" Update all references, not just the one the judge found. Before marking `ready_for_judge`, do a cross-document consistency scan.

**First observed**: 001-ai-code-reviewer, design round 4

---

## AP-003: Scope Creep Silence

**Applies to**: builder
**Phase**: design, plan, build
**Severity**: high

**Symptoms**:
- Design introduces components, dependencies, or storage that belong to a later spec
- Task's "Out of Scope" section is ignored in practice
- Builder doesn't flag when a design decision pulls in future work

**Problem**: Scope bleed delays the current task (more to review, more to build, more surface for bugs) and pre-commits decisions that should be made in the future spec's context.

**Root cause**: The builder thinks ahead and tries to "set up" for future specs. This feels efficient but violates YAGNI and the spec boundary. The builder doesn't re-read the "Out of Scope" section before designing.

**Correct pattern**: Before finalizing design, re-read the task's "Out of Scope" section. For every dependency, storage choice, or module, ask: "Is this required by THIS spec's requirements, or am I anticipating a future spec?" If the latter, defer it explicitly.

**First observed**: 001-ai-code-reviewer, design round 1 (SQLite for spec 003, cryptography for spec 002)

---

## AP-004: Assumption Without Spike

**Applies to**: builder
**Phase**: design
**Severity**: medium

**Symptoms**:
- Design treats an external SDK/API's behavior as certain without having run any code
- "The SDK does X" stated as fact when the SDK is pre-release, poorly documented, or has conflicting sources
- No fallback plan documented for the assumption

**Problem**: Designs built on unverified assumptions collapse during build phase, requiring expensive redesigns under time pressure.

**Root cause**: The builder reads documentation (or secondary sources) and treats them as ground truth. Pre-release SDKs frequently have docs that don't match the actual API.

**Correct pattern**: For any pre-release or poorly-documented dependency, document the assumption explicitly and provide a fallback path. Mark it for build-phase validation with a concrete checklist (import test, method existence check, parameter name verification). The design should work regardless of which path is taken.

**First observed**: 001-ai-code-reviewer, design rounds 3-4 (Copilot SDK `send_and_wait` assumption)

---

## AP-005: Incremental Fix, New Inconsistency

**Applies to**: builder
**Phase**: all
**Severity**: medium

**Symptoms**:
- Each round fixes the specific finding but introduces a new issue
- Round count keeps climbing without converging
- The judge keeps finding new problems in previously-clean areas

**Problem**: The task approaches max_rounds without acceptance. Each round feels productive but the total quality isn't converging. Eventually triggers escalation not because of a real disagreement but because of accumulated sloppiness.

**Root cause**: The builder focuses narrowly on the judge's findings without stepping back to assess the overall state of the artifacts. Tunnel vision on "fix what was cited" rather than "make the whole design consistent."

**Correct pattern**: After addressing all judge findings, do a full re-read of the affected artifacts as if you were the judge. Look for: (1) contradictions with unchanged documents, (2) new gaps created by the fix, (3) whether the fix aligns with the task's scope and constraints. One careful round is better than three fast ones.

**First observed**: 001-ai-code-reviewer, design rounds 1-4

---

## AP-006: Generic Finding

**Applies to**: judge
**Phase**: all
**Severity**: medium

**Symptoms**:
- Finding says "this is underspecified" without saying what specific information is missing
- Finding says "this could cause problems" without describing the concrete failure scenario
- Finding references a principle without explaining how the artifact violates it

**Problem**: Generic findings are hard to act on. The builder guesses what the judge wants, often guessing wrong, which wastes a round.

**Root cause**: The judge identifies a vague discomfort with an artifact but doesn't invest the effort to articulate the specific failure mode.

**Correct pattern**: Every finding must answer: (1) What specific artifact/line is wrong? (2) What concrete failure would this cause? (3) What would "fixed" look like? Use the format: "[artifact:line] does X, but [spec/requirement] requires Y, which would cause [specific failure]."

**First observed**: n/a (preventive, based on protocol norms)
