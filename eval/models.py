"""Pydantic models for the eval harness.

All entities and enums from specs/007-eval-harness/data-model.md.
Reuses Severity, Category, FindingStatus, Location, Finding, ReviewBundle
from server.models.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class GoldenCaseSource(str, Enum):
    HAND_CURATED = "hand_curated"
    BUG_FIX_PR = "bug_fix_pr"
    VULNERABILITY_DATASET = "vulnerability_dataset"
    SYNTHETIC = "synthetic"


class GraderVerdict(str, Enum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    NOVEL_VALID = "novel_valid"
    NO_MATCH = "no_match"
    GRADING_ERROR = "grading_error"


class GraderConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CIMethod(str, Enum):
    """How a metric's confidence interval was computed.

    ``wilson_insufficient_n`` marks an INCONCLUSIVE state: the Wilson CI
    is valid but the sample is too small to pass or fail the threshold
    with statistical confidence.

    ``undefined`` marks an INCONCLUSIVE state where the metric has no
    observations (e.g., severity/category accuracy when no finding was
    ever matched). Emitting a vacuous 1.0 here would force-PASS the
    threshold on zero data; UNDEFINED surfaces the gap to the operator
    and fails strict-mode CI.
    """

    NORMAL = "normal"
    WILSON = "wilson"
    BCA = "bca"
    VACUOUS = "vacuous"
    WILSON_INSUFFICIENT_N = "wilson_insufficient_n"
    UNDEFINED = "undefined"


class MetricStatus(str, Enum):
    """Derived outcome for a MetricWithSEM against its threshold."""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


from server.models import (  # noqa: E402
    Category,
    Finding,
    FindingStatus,
    Location,
    ReviewBundle,
    Severity,
)

__all__ = [
    # Enums
    "GoldenCaseSource",
    "GraderVerdict",
    "GraderConfidence",
    "CIMethod",
    "MetricStatus",
    # Re-exported from server.models
    "Severity",
    "Category",
    "FindingStatus",
    "Location",
    "Finding",
    "ReviewBundle",
    # Entities
    "ExpectedFinding",
    "TurnScript",
    "DualMetricConfig",
    "GoldenCase",
    "GraderResult",
    "TrialMetrics",
    "TrialResult",
    "CaseResult",
    "RebuttalResult",
    "DualMetricResult",
    "EvalRun",
    "AggregateMetrics",
    "MetricWithSEM",
    "Scorecard",
    "CaseSummary",
    "ComparisonResult",
    "MetricDelta",
]


class ExpectedFinding(BaseModel):
    expected_id: str
    rule_id: str
    severity: Severity
    category: Category
    file: str
    approximate_line: int
    description: str

    @field_validator("approximate_line")
    @classmethod
    def line_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("approximate_line must be non-negative")
        return v


class TurnScript(BaseModel):
    turn_number: int
    rebuttal_message_template: str
    target_expected_id: str
    expected_status_after: FindingStatus
    is_valid_rebuttal: bool

    @field_validator("turn_number")
    @classmethod
    def turn_number_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("turn_number must be >= 1")
        return v


class DualMetricConfig(BaseModel):
    vulnerable_dir: str
    fixed_dir: str
    fixed_bundle: ReviewBundle | None = None


class GoldenCase(BaseModel):
    case_id: str
    description: str
    source: GoldenCaseSource
    tags: list[str]
    bundle: ReviewBundle
    expected_findings: list[ExpectedFinding]
    expected_non_findings: list[str] = Field(default_factory=list)
    multi_turn_script: list[TurnScript] | None = None
    dual_metric: DualMetricConfig | None = None


class GraderResult(BaseModel):
    tier: int
    verdict: GraderVerdict
    confidence: GraderConfidence
    reasoning: str | None = None
    matched_expected_id: str | None = None
    actual_finding_id: str

    @field_validator("tier")
    @classmethod
    def tier_must_be_valid(cls, v: int) -> int:
        if v not in (1, 2):
            raise ValueError("tier must be 1 or 2")
        return v

    @model_validator(mode="after")
    def matched_id_consistent_with_verdict(self) -> GraderResult:
        needs_match = {GraderVerdict.MATCH, GraderVerdict.PARTIAL_MATCH}
        must_be_none = {
            GraderVerdict.NOVEL_VALID,
            GraderVerdict.NO_MATCH,
            GraderVerdict.GRADING_ERROR,
        }
        if self.verdict in needs_match and self.matched_expected_id is None:
            raise ValueError(
                f"verdict={self.verdict.value} requires matched_expected_id"
            )
        if self.verdict in must_be_none and self.matched_expected_id is not None:
            raise ValueError(
                f"verdict={self.verdict.value} forbids matched_expected_id"
            )
        return self


class TrialMetrics(BaseModel):
    precision: float
    recall: float
    severity_accuracy: float
    category_accuracy: float
    snr: float
    novel_count: int
    grading_error_count: int
    finding_count: int
    severity_pairs: list[list[str]] = Field(default_factory=list)

    @field_validator("novel_count", "grading_error_count", "finding_count")
    @classmethod
    def counts_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("count must be non-negative")
        return v


class TrialResult(BaseModel):
    trial_number: int
    findings: list[Finding]
    graded: list[GraderResult]
    metrics: TrialMetrics
    error: str | None = None

    @field_validator("trial_number")
    @classmethod
    def trial_number_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("trial_number must be >= 1")
        return v


class RebuttalResult(BaseModel):
    turn_number: int
    target_expected_id: str
    actual_finding_id: str | None
    expected_status: FindingStatus
    actual_status: FindingStatus | None
    correct: bool
    finding_not_found: bool

    @model_validator(mode="after")
    def invariants(self) -> RebuttalResult:
        if self.finding_not_found:
            if self.actual_finding_id is not None:
                raise ValueError(
                    "finding_not_found=True forbids actual_finding_id"
                )
            if self.correct:
                raise ValueError(
                    "finding_not_found=True forbids correct=True"
                )
        elif self.actual_finding_id is None:
            raise ValueError(
                "finding_not_found=False requires actual_finding_id"
            )

        expected_correct = self.actual_status == self.expected_status
        if self.correct and not expected_correct:
            raise ValueError(
                "correct=True requires actual_status to match expected_status"
            )
        return self


class DualMetricResult(BaseModel):
    vulnerable_results: list[TrialResult]
    fixed_results: list[TrialResult]


class CaseResult(BaseModel):
    case_id: str
    trials: list[TrialResult]
    pass_at_1: dict[str, bool]
    pass_at_k: dict[str, bool]
    rebuttal_results: list[RebuttalResult] | None = None
    dual_metric_results: DualMetricResult | None = None


class MetricWithSEM(BaseModel):
    mean: float
    sem: float
    ci_lower: float
    ci_upper: float
    passes_threshold: bool
    method: CIMethod = CIMethod.NORMAL
    ci_tail: Literal["lower", "upper"] = "lower"

    @property
    def status(self) -> MetricStatus:
        if self.method in (CIMethod.WILSON_INSUFFICIENT_N, CIMethod.UNDEFINED):
            return MetricStatus.INCONCLUSIVE
        return MetricStatus.PASS if self.passes_threshold else MetricStatus.FAIL


class AggregateMetrics(BaseModel):
    precision: MetricWithSEM
    recall: MetricWithSEM
    severity_accuracy: MetricWithSEM
    category_accuracy: MetricWithSEM
    fp_rate: MetricWithSEM
    warn_rate: float = 0.0  # Informational: WARN findings on clean cases (no threshold)
    rebuttal_accuracy: MetricWithSEM | None = None
    snr: MetricWithSEM
    severity_qwk: float = 0.0
    # Total ``novel_valid`` findings across the entire run (sum, not mean).
    # FR-004 defines novel-finding count as the number of novel findings
    # across the run; averaging per-trial collapses that signal when
    # --trials > 1 (see F16 / tmp-007-eval-harness-review.md).
    novel_count: int = 0
    pass_at_1_rate: float
    pass_at_k_rate: float


class MetricDelta(BaseModel):
    baseline: float
    current: float
    delta: float
    delta_pct: float


class ComparisonResult(BaseModel):
    baseline_run_id: str
    baseline_timestamp: datetime
    deltas: dict[str, MetricDelta]
    regressions: list[str]
    improvements: list[str]


class EvalRun(BaseModel):
    run_id: str
    timestamp: datetime
    model_evaluated: str
    grader_model: str
    grader_prompt_version: str
    num_trials: int
    line_tolerance: int
    cases: list[CaseResult]
    aggregate: AggregateMetrics
    pass_fail: bool
    duration_seconds: float


class CaseSummary(BaseModel):
    case_id: str
    description: str
    pass_fail: bool
    precision: float
    recall: float
    finding_count: int
    expected_count: int
    novel_count: int


class Scorecard(BaseModel):
    run: EvalRun
    thresholds: dict[str, float]
    per_case_summary: list[CaseSummary]
    comparison: ComparisonResult | None = None
