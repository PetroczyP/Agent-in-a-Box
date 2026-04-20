# Spec 014: Eval Harness Statistical Hardening

**Status**: Backlog
**Depends on**: 007 (Eval Harness)
**Priority**: Medium

## Overview

Statistical hardening of the eval harness beyond the Option B improvements delivered in spec 007. These items were identified during spec 007 research (Round 11) and deferred to keep the release scope manageable.

## Backlog Items

### Regression Gating (compare_runs)
- **SH-001**: Replace naive delta comparison in `compare_runs` (reporter.py) with paired bootstrap test + sign-flip permutation test (arXiv:2511.19794). Current implementation declares regression on `current.mean < baseline.mean` with no statistical test.
- **SH-002**: Add Benjamini-Hochberg FDR correction for multi-metric gating. When checking 7 metrics simultaneously, uncorrected p-values inflate false alarm rate.

### Trial Clustering
- **SH-003**: Implement clustered standard errors by `case_id`. Currently, per-trial values from the same golden case are treated as independent, but trials within a case share the same diff/expected findings and are not truly independent. The Inspect AI eval framework (Anthropic/UK AISI) uses a similar clustering approach.

### Grader Reliability
- **SH-004**: Implement position-swap double-pass for the Tier 2 LLM grader. Research shows 60-75% of LLM judges exhibit position bias. Running each grading call twice with swapped context ordering and requiring agreement improves reliability.

### Reproducibility
- **SH-005**: Add dataset fingerprint (SHA-256 of sorted golden case content hashes) to eval run metadata. Enables detecting when results are compared across different fixture sets.
- **SH-006**: Record grader prompt content hash (not just version) in eval run metadata for exact reproducibility.

### Human Calibration
- **SH-007**: Add a human calibration slice -- a small set of golden cases where human expert severity/category labels are collected alongside model predictions. Enables computing human-model ICC (intraclass correlation coefficient) as ground truth for grader quality.
- **SH-008**: Add contamination probe -- a canary case with known-unique content that detects if the evaluated model has memorized golden case content from training data.

## References

- Brown, Cai & DasGupta (2001). "Interval Estimation for a Binomial Proportion." Statistical Science.
- Efron & Tibshirani (1993). "An Introduction to the Bootstrap." Chapman & Hall/CRC.
- Warrens (2012). "Equivalences of Weighted Kappas for Multiple Raters."
- Agresti (2013). "Categorical Data Analysis."
- DeepCRCEval (2024). Human-human ICC for code review quality = 0.89-0.95; LLM-human = 0.62-0.83.
- SWR-Bench (ICSE 2025). Severity scoring treated as supplementary.
- Quantum Software Engineering studies. Cohen's kappa for severity = 0.162.
- arXiv:2511.19794. Paired bootstrap and sign-flip permutation for LLM eval regression detection.
