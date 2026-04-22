"""RED tests for eval harness Pydantic models (T001).

Tests model instantiation, enum membership, JSON round-trip serialization,
and validation rejection of invalid data.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval.models import (
    AggregateMetrics,
    CaseResult,
    CaseSummary,
    ComparisonResult,
    DualMetricConfig,
    DualMetricResult,
    EvalRun,
    ExpectedFinding,
    GoldenCase,
    GoldenCaseSource,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
    MetricDelta,
    MetricWithSEM,
    RebuttalResult,
    Scorecard,
    TrialMetrics,
    TrialResult,
    TurnScript,
)
from server.models import (
    Category,
    Finding,
    FindingStatus,
    Location,
    ReviewBundle,
    Severity,
)


# --- Enum membership tests ---


class TestEnumMembership:
    def test_golden_case_source_values(self) -> None:
        assert GoldenCaseSource.HAND_CURATED == "hand_curated"
        assert GoldenCaseSource.BUG_FIX_PR == "bug_fix_pr"
        assert GoldenCaseSource.VULNERABILITY_DATASET == "vulnerability_dataset"
        assert GoldenCaseSource.SYNTHETIC == "synthetic"
        assert len(GoldenCaseSource) == 4

    def test_grader_verdict_values(self) -> None:
        assert GraderVerdict.MATCH == "match"
        assert GraderVerdict.PARTIAL_MATCH == "partial_match"
        assert GraderVerdict.NOVEL_VALID == "novel_valid"
        assert GraderVerdict.NO_MATCH == "no_match"
        assert GraderVerdict.GRADING_ERROR == "grading_error"
        assert len(GraderVerdict) == 5

    def test_grader_confidence_values(self) -> None:
        assert GraderConfidence.HIGH == "high"
        assert GraderConfidence.MEDIUM == "medium"
        assert GraderConfidence.LOW == "low"
        assert len(GraderConfidence) == 3


# --- Model instantiation tests ---


class TestExpectedFinding:
    def test_instantiation(self, sample_expected_finding: ExpectedFinding) -> None:
        assert sample_expected_finding.expected_id == "EF-001"
        assert sample_expected_finding.rule_id == "sql-injection"
        assert sample_expected_finding.severity == Severity.BUG
        assert sample_expected_finding.category == Category.SECURITY
        assert sample_expected_finding.file == "src/main.py"
        assert sample_expected_finding.approximate_line == 10

    def test_rejects_negative_line(self) -> None:
        with pytest.raises(ValueError):
            ExpectedFinding(
                expected_id="EF-001",
                rule_id="test",
                severity=Severity.BUG,
                category=Category.SECURITY,
                file="test.py",
                approximate_line=-1,
                description="test",
            )


class TestTurnScript:
    def test_instantiation(self) -> None:
        ts = TurnScript(
            turn_number=1,
            rebuttal_message_template="I disagree with {finding_id}",
            target_expected_id="EF-001",
            expected_status_after=FindingStatus.DISMISSED,
            is_valid_rebuttal=True,
        )
        assert ts.turn_number == 1
        assert ts.target_expected_id == "EF-001"
        assert ts.is_valid_rebuttal is True

    def test_rejects_zero_turn_number(self) -> None:
        with pytest.raises(ValueError):
            TurnScript(
                turn_number=0,
                rebuttal_message_template="test",
                target_expected_id="EF-001",
                expected_status_after=FindingStatus.DISMISSED,
                is_valid_rebuttal=True,
            )


class TestDualMetricConfig:
    def test_instantiation(self) -> None:
        dmc = DualMetricConfig(
            vulnerable_dir="vulnerable",
            fixed_dir="fixed",
        )
        assert dmc.vulnerable_dir == "vulnerable"
        assert dmc.fixed_dir == "fixed"


class TestGoldenCase:
    def test_instantiation(self, sample_golden_case: GoldenCase) -> None:
        assert sample_golden_case.case_id == "case-001"
        assert sample_golden_case.source == GoldenCaseSource.HAND_CURATED
        assert len(sample_golden_case.expected_findings) == 1
        assert sample_golden_case.multi_turn_script is None
        assert sample_golden_case.dual_metric is None

    def test_optional_fields_default_none(
        self, sample_review_bundle: ReviewBundle, sample_expected_finding: ExpectedFinding
    ) -> None:
        gc = GoldenCase(
            case_id="case-002",
            description="Clean code",
            source=GoldenCaseSource.SYNTHETIC,
            tags=[],
            bundle=sample_review_bundle,
            expected_findings=[sample_expected_finding],
        )
        assert gc.multi_turn_script is None
        assert gc.dual_metric is None
        assert gc.expected_non_findings == []

    def test_with_multi_turn(
        self, sample_review_bundle: ReviewBundle, sample_expected_finding: ExpectedFinding
    ) -> None:
        script = TurnScript(
            turn_number=1,
            rebuttal_message_template="I disagree with {finding_id}",
            target_expected_id="EF-001",
            expected_status_after=FindingStatus.DISMISSED,
            is_valid_rebuttal=True,
        )
        gc = GoldenCase(
            case_id="case-003",
            description="Multi-turn case",
            source=GoldenCaseSource.HAND_CURATED,
            tags=["multi-turn"],
            bundle=sample_review_bundle,
            expected_findings=[sample_expected_finding],
            multi_turn_script=[script],
        )
        assert gc.multi_turn_script is not None
        assert len(gc.multi_turn_script) == 1


class TestGraderResult:
    def test_tier_1_instantiation(self, sample_grader_result: GraderResult) -> None:
        assert sample_grader_result.tier == 1
        assert sample_grader_result.verdict == GraderVerdict.MATCH
        assert sample_grader_result.confidence == GraderConfidence.HIGH
        assert sample_grader_result.reasoning is None

    def test_tier_2_with_reasoning(self) -> None:
        gr = GraderResult(
            tier=2,
            verdict=GraderVerdict.PARTIAL_MATCH,
            confidence=GraderConfidence.MEDIUM,
            reasoning="The finding is semantically similar but targets a different line",
            matched_expected_id="EF-002",
            actual_finding_id="F-003",
        )
        assert gr.tier == 2
        assert gr.reasoning is not None

    def test_grading_error_verdict(self) -> None:
        gr = GraderResult(
            tier=2,
            verdict=GraderVerdict.GRADING_ERROR,
            confidence=GraderConfidence.LOW,
            reasoning="API timeout after retries",
            actual_finding_id="F-005",
        )
        assert gr.verdict == GraderVerdict.GRADING_ERROR
        assert gr.matched_expected_id is None

    def test_rejects_invalid_tier(self) -> None:
        with pytest.raises(ValueError):
            GraderResult(
                tier=3,
                verdict=GraderVerdict.MATCH,
                confidence=GraderConfidence.HIGH,
                actual_finding_id="F-001",
            )


class TestTrialMetrics:
    def test_instantiation(self, sample_trial_metrics: TrialMetrics) -> None:
        assert sample_trial_metrics.precision == 0.8
        assert sample_trial_metrics.recall == 0.9
        assert sample_trial_metrics.snr == 4.0
        assert sample_trial_metrics.grading_error_count == 0

    def test_rejects_negative_finding_count(self) -> None:
        with pytest.raises(ValueError):
            TrialMetrics(
                precision=0.8,
                recall=0.9,
                severity_accuracy=0.85,
                category_accuracy=0.75,
                snr=4.0,
                novel_count=0,
                grading_error_count=0,
                finding_count=-1,
            )


class TestTrialResult:
    def test_instantiation(self, sample_trial_result: TrialResult) -> None:
        assert sample_trial_result.trial_number == 1
        assert len(sample_trial_result.findings) == 1
        assert len(sample_trial_result.graded) == 1
        assert sample_trial_result.error is None

    def test_rejects_negative_trial_number(
        self, sample_finding: Finding, sample_grader_result: GraderResult, sample_trial_metrics: TrialMetrics
    ) -> None:
        with pytest.raises(ValueError):
            TrialResult(
                trial_number=-1,
                findings=[sample_finding],
                graded=[sample_grader_result],
                metrics=sample_trial_metrics,
            )

    def test_with_error(self, sample_trial_metrics: TrialMetrics) -> None:
        tr = TrialResult(
            trial_number=1,
            findings=[],
            graded=[],
            metrics=sample_trial_metrics,
            error="Rate limit exceeded",
        )
        assert tr.error == "Rate limit exceeded"


class TestCaseResult:
    def test_instantiation(self, sample_trial_result: TrialResult) -> None:
        cr = CaseResult(
            case_id="case-001",
            trials=[sample_trial_result],
            pass_at_1={"EF-001": True},
            pass_at_k={"EF-001": True},
        )
        assert cr.case_id == "case-001"
        assert cr.rebuttal_results is None
        assert cr.dual_metric_results is None


class TestRebuttalResult:
    def test_successful_rebuttal(self) -> None:
        rr = RebuttalResult(
            turn_number=1,
            target_expected_id="EF-001",
            actual_finding_id="F-001",
            expected_status=FindingStatus.DISMISSED,
            actual_status=FindingStatus.DISMISSED,
            correct=True,
            finding_not_found=False,
        )
        assert rr.correct is True
        assert rr.finding_not_found is False

    def test_finding_not_found(self) -> None:
        rr = RebuttalResult(
            turn_number=1,
            target_expected_id="EF-001",
            actual_finding_id=None,
            expected_status=FindingStatus.DISMISSED,
            actual_status=None,
            correct=False,
            finding_not_found=True,
        )
        assert rr.correct is False
        assert rr.finding_not_found is True


class TestMetricWithSEM:
    def test_instantiation(self, sample_metric_with_sem: MetricWithSEM) -> None:
        assert sample_metric_with_sem.mean == 0.85
        assert sample_metric_with_sem.sem == 0.03
        assert sample_metric_with_sem.passes_threshold is True
        assert sample_metric_with_sem.ci_lower == pytest.approx(0.85 - 1.96 * 0.03)
        assert sample_metric_with_sem.ci_upper == pytest.approx(0.85 + 1.96 * 0.03)


class TestAggregateMetrics:
    def test_instantiation(self, sample_metric_with_sem: MetricWithSEM) -> None:
        am = AggregateMetrics(
            precision=sample_metric_with_sem,
            recall=sample_metric_with_sem,
            severity_accuracy=sample_metric_with_sem,
            category_accuracy=sample_metric_with_sem,
            fp_rate=sample_metric_with_sem,
            snr=sample_metric_with_sem,
            novel_count=3,
            pass_at_1_rate=0.9,
            pass_at_k_rate=0.95,
        )
        assert am.rebuttal_accuracy is None
        assert am.novel_count == 3


class TestMetricDelta:
    def test_instantiation(self) -> None:
        md = MetricDelta(
            baseline=0.80,
            current=0.85,
            delta=0.05,
            delta_pct=6.25,
        )
        assert md.delta == 0.05


class TestEvalRun:
    def test_instantiation(
        self,
        sample_trial_result: TrialResult,
        sample_metric_with_sem: MetricWithSEM,
    ) -> None:
        case_result = CaseResult(
            case_id="case-001",
            trials=[sample_trial_result],
            pass_at_1={"EF-001": True},
            pass_at_k={"EF-001": True},
        )
        aggregate = AggregateMetrics(
            precision=sample_metric_with_sem,
            recall=sample_metric_with_sem,
            severity_accuracy=sample_metric_with_sem,
            category_accuracy=sample_metric_with_sem,
            fp_rate=sample_metric_with_sem,
            snr=sample_metric_with_sem,
            novel_count=1,
            pass_at_1_rate=0.9,
            pass_at_k_rate=0.95,
        )
        run = EvalRun(
            run_id="test-run-001",
            timestamp=datetime(2026, 4, 2, tzinfo=timezone.utc),
            model_evaluated="copilot-gpt-4",
            grader_model="claude-sonnet-4-6",
            grader_prompt_version="abc123hash",
            num_trials=3,
            line_tolerance=5,
            cases=[case_result],
            aggregate=aggregate,
            pass_fail=True,
            duration_seconds=120.5,
        )
        assert run.run_id == "test-run-001"
        assert run.pass_fail is True


class TestScorecard:
    def test_instantiation(
        self,
        sample_trial_result: TrialResult,
        sample_metric_with_sem: MetricWithSEM,
    ) -> None:
        case_result = CaseResult(
            case_id="case-001",
            trials=[sample_trial_result],
            pass_at_1={"EF-001": True},
            pass_at_k={"EF-001": True},
        )
        aggregate = AggregateMetrics(
            precision=sample_metric_with_sem,
            recall=sample_metric_with_sem,
            severity_accuracy=sample_metric_with_sem,
            category_accuracy=sample_metric_with_sem,
            fp_rate=sample_metric_with_sem,
            snr=sample_metric_with_sem,
            novel_count=1,
            pass_at_1_rate=0.9,
            pass_at_k_rate=0.95,
        )
        run = EvalRun(
            run_id="test-run-001",
            timestamp=datetime(2026, 4, 2, tzinfo=timezone.utc),
            model_evaluated="copilot-gpt-4",
            grader_model="claude-sonnet-4-6",
            grader_prompt_version="abc123hash",
            num_trials=3,
            line_tolerance=5,
            cases=[case_result],
            aggregate=aggregate,
            pass_fail=True,
            duration_seconds=120.5,
        )
        summary = CaseSummary(
            case_id="case-001",
            description="SQL injection test",
            pass_fail=True,
            precision=0.8,
            recall=0.9,
            finding_count=5,
            expected_count=4,
            novel_count=1,
        )
        scorecard = Scorecard(
            run=run,
            thresholds={"precision": 0.7, "recall": 0.6},
            per_case_summary=[summary],
        )
        assert scorecard.comparison is None
        assert len(scorecard.per_case_summary) == 1


# --- JSON round-trip tests ---


class TestJsonRoundTrip:
    def test_expected_finding_roundtrip(self, sample_expected_finding: ExpectedFinding) -> None:
        json_str = sample_expected_finding.model_dump_json()
        restored = ExpectedFinding.model_validate_json(json_str)
        assert restored == sample_expected_finding

    def test_golden_case_roundtrip(self, sample_golden_case: GoldenCase) -> None:
        json_str = sample_golden_case.model_dump_json()
        restored = GoldenCase.model_validate_json(json_str)
        assert restored == sample_golden_case

    def test_grader_result_roundtrip(self, sample_grader_result: GraderResult) -> None:
        json_str = sample_grader_result.model_dump_json()
        restored = GraderResult.model_validate_json(json_str)
        assert restored == sample_grader_result

    def test_trial_result_roundtrip(self, sample_trial_result: TrialResult) -> None:
        json_str = sample_trial_result.model_dump_json()
        restored = TrialResult.model_validate_json(json_str)
        assert restored == sample_trial_result

    def test_metric_with_sem_roundtrip(self, sample_metric_with_sem: MetricWithSEM) -> None:
        json_str = sample_metric_with_sem.model_dump_json()
        restored = MetricWithSEM.model_validate_json(json_str)
        assert restored == sample_metric_with_sem


# --- Validation rejection tests ---


class TestValidationRejection:
    def test_expected_finding_rejects_invalid_severity(self) -> None:
        with pytest.raises(ValueError):
            ExpectedFinding(
                expected_id="EF-001",
                rule_id="test",
                severity="INVALID",  # type: ignore[arg-type]
                category=Category.SECURITY,
                file="test.py",
                approximate_line=10,
                description="test",
            )

    def test_grader_result_rejects_invalid_verdict(self) -> None:
        with pytest.raises(ValueError):
            GraderResult(
                tier=1,
                verdict="INVALID",  # type: ignore[arg-type]
                confidence=GraderConfidence.HIGH,
                actual_finding_id="F-001",
            )

    def test_golden_case_rejects_missing_required(self) -> None:
        with pytest.raises(ValueError):
            GoldenCase(  # type: ignore[call-arg]
                case_id="case-001",
                # missing description, source, tags, bundle, expected_findings
            )

    def test_trial_metrics_rejects_negative_novel_count(self) -> None:
        with pytest.raises(ValueError):
            TrialMetrics(
                precision=0.8,
                recall=0.9,
                severity_accuracy=0.85,
                category_accuracy=0.75,
                snr=4.0,
                novel_count=-1,
                grading_error_count=0,
                finding_count=5,
            )
