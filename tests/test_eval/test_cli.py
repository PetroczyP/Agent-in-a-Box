"""Tests for eval CLI (T011).

RED phase: all tests mock external dependencies.
Tests parse_args (sync) separately from run() (async).
"""

from __future__ import annotations

import argparse
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eval.cli import _warn_if_inconclusive
from eval.models import (
    AggregateMetrics,
    CaseResult,
    CIMethod,
    EvalRun,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
    MetricWithSEM,
    TrialMetrics,
    TrialResult,
)
from server.models import (
    Category,
    Finding,
    FindingStatus,
    Location,
    Severity,
)


# ---------------------------------------------------------------------------
# Helpers: factory functions for test data
# ---------------------------------------------------------------------------


def _make_metric(
    mean: float = 0.85,
    passes: bool = True,
    method: CIMethod = CIMethod.NORMAL,
) -> MetricWithSEM:
    sem = 0.02
    return MetricWithSEM(
        mean=mean,
        sem=sem,
        ci_lower=mean - 1.96 * sem,
        ci_upper=mean + 1.96 * sem,
        passes_threshold=passes,
        method=method,
    )


def _make_aggregate(all_pass: bool = True) -> AggregateMetrics:
    return AggregateMetrics(
        precision=_make_metric(0.85, all_pass),
        recall=_make_metric(0.75, all_pass),
        severity_accuracy=_make_metric(0.90, all_pass),
        category_accuracy=_make_metric(0.80, all_pass),
        fp_rate=_make_metric(0.10, all_pass),
        snr=_make_metric(4.0, all_pass),
        novel_count=2,
        pass_at_1_rate=0.90,
        pass_at_k_rate=0.95,
    )


def _make_trial() -> TrialResult:
    return TrialResult(
        trial_number=1,
        findings=[
            Finding(
                finding_id="F-001",
                rule_id="sql-injection",
                severity=Severity.BUG,
                category=Category.SECURITY,
                message="SQL injection",
                primary_location=Location(
                    file="main.py", start_line=10, end_line=15
                ),
                fingerprint="abc",
                confidence="high",
                evidence="test",
            )
        ],
        graded=[
            GraderResult(
                tier=1,
                verdict=GraderVerdict.MATCH,
                confidence=GraderConfidence.HIGH,
                matched_expected_id="EF-001",
                actual_finding_id="F-001",
            )
        ],
        metrics=TrialMetrics(
            precision=0.85,
            recall=0.75,
            severity_accuracy=0.90,
            category_accuracy=0.80,
            snr=4.0,
            novel_count=0,
            grading_error_count=0,
            finding_count=1,
        ),
    )


def _make_eval_run(pass_fail: bool = True) -> EvalRun:
    return EvalRun(
        run_id="run-test-001",
        timestamp=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        model_evaluated="copilot",
        grader_model="claude-sonnet-4-6",
        grader_prompt_version="abc123def456",
        num_trials=3,
        line_tolerance=5,
        cases=[
            CaseResult(
                case_id="case-001",
                trials=[_make_trial()],
                pass_at_1={"precision": True, "recall": True},
                pass_at_k={"precision": True, "recall": True},
            )
        ],
        aggregate=_make_aggregate(all_pass=pass_fail),
        pass_fail=pass_fail,
        duration_seconds=120.5,
    )


def _mock_connect():
    """Return a mock for eval.cli.connect that yields a MagicMock session."""

    @asynccontextmanager
    async def _fake_connect(container: str):
        yield MagicMock()

    return _fake_connect


# ---------------------------------------------------------------------------
# Import target
# ---------------------------------------------------------------------------

from eval.cli import main, parse_args, run  # noqa: E402


# ===========================================================================
# parse_args tests
# ===========================================================================


class TestParseArgs:
    """Test all 14 flags parse correctly with defaults."""

    def test_defaults(self):
        args = parse_args([])
        assert args.trials == 3
        assert args.ci is False
        assert args.grader_model == "claude-sonnet-4-6"
        assert args.thresholds == "eval/fixtures/thresholds.json"
        assert args.baseline is None
        assert args.cases == "all"
        assert args.container is None
        assert args.output_dir == "eval/results/"
        assert args.line_tolerance == 5
        assert args.max_retries == 3
        assert args.prompt_consistency_check is False
        assert args.accept_prompt is False
        assert args.verbose is False
        assert args.concurrency == 5

    def test_concurrency_flag(self):
        args = parse_args(["--concurrency", "10"])
        assert args.concurrency == 10

    def test_trials_flag(self):
        args = parse_args(["--trials", "5"])
        assert args.trials == 5

    def test_ci_flag(self):
        args = parse_args(["--ci"])
        assert args.ci is True

    def test_grader_model_flag(self):
        args = parse_args(["--grader-model", "claude-opus-4"])
        assert args.grader_model == "claude-opus-4"

    def test_thresholds_flag(self):
        args = parse_args(["--thresholds", "/custom/thresholds.json"])
        assert args.thresholds == "/custom/thresholds.json"

    def test_baseline_flag(self):
        args = parse_args(["--baseline", "eval/results/run-prev.json"])
        assert args.baseline == "eval/results/run-prev.json"

    def test_cases_flag(self):
        args = parse_args(["--cases", "case-001,case-003"])
        assert args.cases == "case-001,case-003"

    def test_container_flag(self):
        args = parse_args(["--container", "my-container"])
        assert args.container == "my-container"

    def test_output_dir_flag(self):
        args = parse_args(["--output-dir", "/tmp/results"])
        assert args.output_dir == "/tmp/results"

    def test_line_tolerance_flag(self):
        args = parse_args(["--line-tolerance", "10"])
        assert args.line_tolerance == 10

    def test_max_retries_flag(self):
        args = parse_args(["--max-retries", "5"])
        assert args.max_retries == 5

    def test_prompt_consistency_check_flag(self):
        args = parse_args(["--prompt-consistency-check"])
        assert args.prompt_consistency_check is True

    def test_accept_prompt_flag(self):
        args = parse_args(["--accept-prompt"])
        assert args.accept_prompt is True

    def test_verbose_flag(self):
        args = parse_args(["--verbose"])
        assert args.verbose is True

    def test_strict_flag_default_false(self):
        """--strict defaults to False (inconclusive metrics do not block)."""
        args = parse_args([])
        assert args.strict is False

    def test_strict_flag_true(self):
        """--strict sets strict mode (inconclusive counts as fail)."""
        args = parse_args(["--strict"])
        assert args.strict is True


# ===========================================================================
# run() tests (async, all deps mocked)
# ===========================================================================


class TestRunExitCodes:
    """Test exit codes from run()."""

    @pytest.mark.asyncio
    async def test_ci_mode_exit_0_on_passing_thresholds(self, tmp_path):
        """--ci mode returns 0 when all thresholds pass."""
        thresholds = {"precision": 0.70, "recall": 0.60}
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))

        output_dir = tmp_path / "results"

        args = parse_args([
            "--ci",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            exit_code = await run(args)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_ci_mode_strict_propagates_to_check_thresholds(self, tmp_path):
        """--ci --strict passes strict=True to check_thresholds.

        The strict flag must flow through the run() pipeline so that
        inconclusive metrics (wilson_insufficient_n) fail CI in strict
        mode. Asserts check_thresholds is called with strict=True.
        """
        thresholds = {"precision": 0.70, "recall": 0.60}
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))

        args = parse_args([
            "--ci", "--strict",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True) as mock_check,
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        # Extract the `strict` kwarg from the call (may be positional or kw)
        assert mock_check.called
        _, kwargs = mock_check.call_args
        assert kwargs.get("strict") is True

    @pytest.mark.asyncio
    async def test_ci_mode_default_strict_false(self, tmp_path):
        """--ci without --strict passes strict=False to check_thresholds."""
        thresholds = {"precision": 0.70, "recall": 0.60}
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))

        args = parse_args([
            "--ci",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True) as mock_check,
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        assert mock_check.called
        _, kwargs = mock_check.call_args
        assert kwargs.get("strict") is False

    @pytest.mark.asyncio
    async def test_ci_strict_overrides_pass_fail_before_rendering(
        self, tmp_path
    ):
        """Under --ci --strict, the scorecard must not render PASS while the
        process exits non-zero. The CLI overrides eval_run.pass_fail using
        strict-mode check_thresholds BEFORE generate_scorecard is called."""
        thresholds = {"precision": 0.70, "recall": 0.60}
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))

        args = parse_args([
            "--ci", "--strict",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
        ])

        # Non-strict run produced pass_fail=True, but strict mode must fail
        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch(
                "eval.cli.run_eval",
                new_callable=AsyncMock,
                return_value=eval_run,
            ),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=False),
        ):
            mock_sc.return_value = MagicMock()
            exit_code = await run(args)

        # Exit code 1 (strict fail)
        assert exit_code == 1
        # generate_scorecard saw pass_fail=False (consistent with exit code)
        assert mock_sc.called
        scorecard_run = mock_sc.call_args[0][0]
        assert scorecard_run.pass_fail is False

    @pytest.mark.asyncio
    async def test_ci_mode_exit_1_on_threshold_failure(self, tmp_path):
        """--ci mode returns 1 when thresholds fail."""
        thresholds = {"precision": 0.70, "recall": 0.60}
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))

        output_dir = tmp_path / "results"

        args = parse_args([
            "--ci",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=False)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=False),
        ):
            mock_sc.return_value = MagicMock()
            exit_code = await run(args)

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_exit_2_on_no_container(self, tmp_path):
        """Exit code 2 when container detection fails."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
        ])

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch(
                "eval.cli.detect_container",
                new_callable=AsyncMock,
                side_effect=RuntimeError("No running container found"),
            ),
        ):
            exit_code = await run(args)

        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_exit_2_on_bad_fixtures(self, tmp_path):
        """Exit code 2 when fixture loading fails."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
        ])

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123"),
            patch(
                "eval.cli.load_cases",
                side_effect=FileNotFoundError("Fixtures directory not found"),
            ),
        ):
            exit_code = await run(args)

        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_exit_2_on_bad_case_id(self, tmp_path):
        """Exit code 2 when case ID filter has invalid IDs."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
            "--cases", "case-nonexistent",
        ])

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123"),
            patch(
                "eval.cli.load_cases",
                side_effect=ValueError("Case IDs not found: case-nonexistent"),
            ),
        ):
            exit_code = await run(args)

        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_non_ci_mode_exit_0(self, tmp_path):
        """Non-CI mode always exits 0 (even when thresholds would fail)."""
        thresholds = {"precision": 0.70, "recall": 0.60}
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))

        output_dir = tmp_path / "results"

        # Note: --ci is NOT passed
        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        # Even with failing thresholds
        eval_run = _make_eval_run(pass_fail=False)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=False),
        ):
            mock_sc.return_value = MagicMock()
            exit_code = await run(args)

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_non_ci_mode_exit_2_on_runtime_error(self, tmp_path):
        """Non-CI mode still exits 2 on runtime errors."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
        ])

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch(
                "eval.cli.detect_container",
                new_callable=AsyncMock,
                side_effect=RuntimeError("No running container found"),
            ),
        ):
            exit_code = await run(args)

        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_exit_2_on_missing_grader_credential(self, tmp_path):
        """Missing ANTHROPIC_API_KEY must exit 2 (not complete the run).

        Regression guard for F10: the CLI contract treats missing grader
        credentials as a configuration error. Previously the pipeline
        downgraded the ValueError into per-finding GRADING_ERROR and the
        harness completed successfully with those findings excluded from
        scoring, hiding the fact that the required grader never ran.
        """
        from eval.graders import MissingGraderCredentialError

        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
        ])

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch(
                "eval.cli.run_eval",
                new_callable=AsyncMock,
                side_effect=MissingGraderCredentialError(
                    "ANTHROPIC_API_KEY is not set"
                ),
            ),
        ):
            exit_code = await run(args)

        assert exit_code == 2


class TestCIOutput:
    """Test CI mode outputs."""

    @pytest.mark.asyncio
    async def test_ci_mode_prints_markdown_to_stdout(self, tmp_path, capsys):
        """--ci mode prints markdown scorecard to stdout."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        output_dir = tmp_path / "results"

        args = parse_args([
            "--ci",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)
        markdown_content = "# Eval Scorecard\nAll tests pass."

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value=markdown_content),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        captured = capsys.readouterr()
        assert markdown_content in captured.out


class TestWarnIfInconclusive:
    """Direct tests for _warn_if_inconclusive.

    The CLI uses this helper to surface INCONCLUSIVE metrics on stderr so
    CI log scrapers see them without parsing markdown. Coverage through
    integration tests only hides regressions in the name list or the
    strict-mode banner; test it directly.
    """

    @staticmethod
    def _run(
        metric_overrides: dict[str, MetricWithSEM] | None = None,
        strict: bool = False,
    ) -> EvalRun:
        agg = _make_aggregate(all_pass=True)
        for name, metric in (metric_overrides or {}).items():
            setattr(agg, name, metric)
        eval_run = _make_eval_run(pass_fail=True)
        eval_run.aggregate = agg
        return eval_run

    def test_no_inconclusive_metrics_emits_nothing(self, capsys):
        eval_run = self._run()
        _warn_if_inconclusive(eval_run, strict=False)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_single_inconclusive_metric_is_named(self, capsys):
        eval_run = self._run(
            metric_overrides={
                "recall": _make_metric(
                    mean=0.5, passes=False,
                    method=CIMethod.WILSON_INSUFFICIENT_N,
                ),
            },
        )
        _warn_if_inconclusive(eval_run, strict=False)
        err = capsys.readouterr().err
        assert "recall" in err
        assert "not gating" in err

    def test_multiple_inconclusive_metrics_all_named(self, capsys):
        eval_run = self._run(
            metric_overrides={
                "precision": _make_metric(
                    mean=0.8, passes=True,
                    method=CIMethod.WILSON_INSUFFICIENT_N,
                ),
                "fp_rate": _make_metric(
                    mean=0.1, passes=True,
                    method=CIMethod.WILSON_INSUFFICIENT_N,
                ),
            },
        )
        _warn_if_inconclusive(eval_run, strict=False)
        err = capsys.readouterr().err
        assert "precision" in err
        assert "fp_rate" in err

    def test_strict_mode_labels_as_fail(self, capsys):
        eval_run = self._run(
            metric_overrides={
                "recall": _make_metric(
                    mean=0.5, passes=False,
                    method=CIMethod.WILSON_INSUFFICIENT_N,
                ),
            },
        )
        _warn_if_inconclusive(eval_run, strict=True)
        err = capsys.readouterr().err
        assert "gating as FAIL" in err

    def test_rebuttal_accuracy_is_checked_when_present(self, capsys):
        eval_run = self._run(
            metric_overrides={
                "rebuttal_accuracy": _make_metric(
                    mean=0.6, passes=False,
                    method=CIMethod.WILSON_INSUFFICIENT_N,
                ),
            },
        )
        _warn_if_inconclusive(eval_run, strict=False)
        assert "rebuttal_accuracy" in capsys.readouterr().err

    def test_missing_rebuttal_accuracy_does_not_crash(self, capsys):
        eval_run = self._run()
        eval_run.aggregate.rebuttal_accuracy = None
        _warn_if_inconclusive(eval_run, strict=False)
        assert capsys.readouterr().err == ""


class TestPromptVersion:
    """Test prompt version handling."""

    @pytest.mark.asyncio
    async def test_prompt_consistency_check_invokes_prompt_version(self, tmp_path):
        """--prompt-consistency-check runs full comparison and records results."""
        args = parse_args(["--prompt-consistency-check"])

        with (
            patch("eval.cli.compute_prompt_hash", return_value="abc123") as mock_hash,
            patch("eval.cli.load_cases", return_value=[]) as mock_load,
            patch("eval.cli.run_full_consistency_check", new_callable=AsyncMock, return_value=0.05) as mock_full,
            patch("eval.cli.run_consistency_check") as mock_check,
            patch("eval.cli.record_flip_rate") as mock_flip,
        ):
            exit_code = await run(args)

        mock_hash.assert_called_once()
        mock_load.assert_called_once()
        mock_full.assert_called_once()
        mock_check.assert_called_once()
        mock_flip.assert_called_once()
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_accept_prompt_invokes_prompt_version(self, tmp_path):
        """--accept-prompt calls accept_prompt and exits."""
        args = parse_args(["--accept-prompt"])

        with patch("eval.cli.accept_prompt", return_value="abc123") as mock_accept:
            exit_code = await run(args)

        mock_accept.assert_called_once()
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_dirty_prompt_exits_2(self, tmp_path):
        """Dirty prompt (PromptDirtyError) exits with code 2."""
        from eval.prompt_version import PromptDirtyError

        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
        ])

        with patch(
            "eval.cli.check_prompt_version",
            side_effect=PromptDirtyError("Grader prompt has changed"),
        ):
            exit_code = await run(args)

        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_dirty_prompt_prints_message(self, tmp_path, capsys):
        """Dirty prompt prints a clear error message to stderr."""
        from eval.prompt_version import PromptDirtyError

        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
        ])

        with patch(
            "eval.cli.check_prompt_version",
            side_effect=PromptDirtyError("Grader prompt has changed"),
        ):
            await run(args)

        captured = capsys.readouterr()
        assert "Grader prompt has changed" in captured.err


class TestBaselineComparison:
    """Test --baseline flag."""

    @pytest.mark.asyncio
    async def test_baseline_loads_previous_run(self, tmp_path):
        """--baseline loads and passes baseline EvalRun to compare_runs."""
        thresholds = {"precision": 0.70}
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))

        # Write a baseline run JSON
        baseline_run = _make_eval_run(pass_fail=True)
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(baseline_run.model_dump_json())

        output_dir = tmp_path / "results"

        args = parse_args([
            "--baseline", str(baseline_file),
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
            patch("eval.cli.compare_runs") as mock_compare,
        ):
            mock_sc.return_value = MagicMock()
            mock_compare.return_value = MagicMock()
            exit_code = await run(args)

        mock_compare.assert_called_once()
        # The first arg should be the current run, second should be an EvalRun
        call_args = mock_compare.call_args
        assert call_args[0][0] == eval_run


class TestThresholdsPassthrough:
    """Custom --thresholds must be forwarded to run_eval.

    Without this plumbing, aggregate_metrics runs against
    DEFAULT_THRESHOLDS and the metrics' passes_threshold flags are
    computed against the wrong threshold — a scorecard can then claim
    a PASS even when the caller configured a stricter bar.
    """

    @pytest.mark.asyncio
    async def test_thresholds_file_passed_to_run(self, tmp_path):
        custom_thresholds = {
            "precision": 0.95,
            "recall": 0.85,
            "fp_rate": 0.05,
        }
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(custom_thresholds))

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(tmp_path / "results"),
            "--container", "test-container",
        ])

        out = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch(
                "eval.cli.run_eval",
                new_callable=AsyncMock,
                return_value=out,
            ) as mock_run,
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs.get("thresholds") == custom_thresholds


class TestGraderModelPassthrough:
    """Test --grader-model passed through to runner."""

    @pytest.mark.asyncio
    async def test_grader_model_passed_to_runner(self, tmp_path):
        """--grader-model value is forwarded to run_eval."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        output_dir = tmp_path / "results"

        args = parse_args([
            "--grader-model", "claude-opus-4",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run) as mock_run,
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        # Verify grader_model was passed to run_eval
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("grader_model") == "claude-opus-4"


class TestCasesFilter:
    """Test --cases filter passed to loader."""

    @pytest.mark.asyncio
    async def test_cases_filter_passed_to_loader(self, tmp_path):
        """--cases filter is forwarded to load_cases."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        output_dir = tmp_path / "results"

        args = parse_args([
            "--cases", "case-001,case-003",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]) as mock_load,
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        call_kwargs = mock_load.call_args
        assert call_kwargs.kwargs.get("case_ids") == ["case-001", "case-003"]

    @pytest.mark.asyncio
    async def test_cases_all_passes_none_to_loader(self, tmp_path):
        """--cases 'all' (default) passes None to load_cases."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        output_dir = tmp_path / "results"

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]) as mock_load,
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        call_kwargs = mock_load.call_args
        assert call_kwargs.kwargs.get("case_ids") is None


class TestOutputFiles:
    """Test output file generation."""

    @pytest.mark.asyncio
    async def test_output_dir_created(self, tmp_path):
        """Output directory is created if it doesn't exist."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        output_dir = tmp_path / "new_results_dir"
        assert not output_dir.exists()

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        assert output_dir.exists()

    @pytest.mark.asyncio
    async def test_output_files_written(self, tmp_path):
        """JSON and markdown files are written to output dir."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps({"precision": 0.70}))

        output_dir = tmp_path / "results"

        args = parse_args([
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=eval_run),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard md"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            await run(args)

        # Check that output_dir has .json and .md files
        json_files = list(output_dir.glob("run-*.json"))
        md_files = list(output_dir.glob("scorecard-*.md"))
        assert len(json_files) == 1
        assert len(md_files) == 1
        assert json_files[0].read_text() == '{"run_id": "test"}'
        assert md_files[0].read_text() == "# Scorecard md"


class TestMainEntrypoint:
    """Test the main() sync entry point."""

    def test_main_returns_int(self):
        """main() returns an integer exit code."""
        eval_run = _make_eval_run(pass_fail=True)

        with (
            patch("eval.cli.parse_args") as mock_parse,
            patch("eval.cli.run", new_callable=AsyncMock, return_value=0),
        ):
            mock_parse.return_value = parse_args(["--container", "test"])
            result = main()

        assert isinstance(result, int)
