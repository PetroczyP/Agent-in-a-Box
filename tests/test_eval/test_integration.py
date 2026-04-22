"""End-to-end integration tests for the eval harness (T013).

Mock ONLY the MCP session -- uses real loader, fingerprint grader, scorer,
and reporter. The Tier 2 model grader is also mocked (requires API key).

TDD checkpoint tests:
  1. Full pipeline: mock MCP -> load cases -> run eval -> scorecard
  2. --ci exit code 0 with passing thresholds
  3. --ci exit code 1 with failing thresholds
  4. Regression detection: swap mock responses for degraded results
  5. Multi-turn: rebuttal_accuracy in scorecard
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eval.loader import load_cases
from eval.models import (
    AggregateMetrics,
    CaseResult,
    EvalRun,
    GraderConfidence,
    GraderResult,
    GraderVerdict,
    MetricWithSEM,
    Scorecard,
    TrialMetrics,
    TrialResult,
)
from eval.reporter import generate_scorecard, render_markdown
from eval.runner import run_eval
from eval.scorer import check_thresholds
from server.models import (
    Category,
    Finding,
    FindingStatus,
    Location,
    Severity,
)


# ===========================================================================
# Helpers: fixture creation on disk
# ===========================================================================


def _write_case_001(base: Path) -> None:
    """Write case-001 (SQL injection bug) fixture files to disk."""
    case_dir = base / "golden_cases" / "case-001"
    bundle_dir = case_dir / "bundle"
    files_dir = bundle_dir / "files"
    files_dir.mkdir(parents=True)

    (case_dir / "meta.json").write_text(json.dumps({
        "case_id": "case-001",
        "description": "SQL injection vulnerability in user lookup endpoint.",
        "source": "hand_curated",
        "tags": ["security", "python"],
    }))

    (case_dir / "expected.json").write_text(json.dumps({
        "expected_findings": [
            {
                "expected_id": "EF-001",
                "rule_id": "sql-injection",
                "severity": "BUG",
                "category": "security",
                "file": "app.py",
                "approximate_line": 12,
                "description": "SQL injection via string concatenation.",
            }
        ],
        "expected_non_findings": [],
    }))

    (bundle_dir / "diff.patch").write_text(
        "diff --git a/app.py b/app.py\n"
        "new file 100644\n"
        "--- /dev/null\n"
        "+++ b/app.py\n"
        "@@ -0,0 +1,5 @@\n"
        "+import sqlite3\n"
        "+def get_user(username):\n"
        "+    db = sqlite3.connect('users.db')\n"
        "+    query = 'SELECT * FROM users WHERE name = \\'' + username + '\\''\n"
        "+    return db.execute(query).fetchall()\n"
    )

    (files_dir / "app.py").write_text(
        "import sqlite3\n"
        "def get_user(username):\n"
        "    db = sqlite3.connect('users.db')\n"
        "    query = 'SELECT * FROM users WHERE name = \\'' + username + '\\''\n"
        "    return db.execute(query).fetchall()\n"
    )


def _write_case_002(base: Path) -> None:
    """Write case-002 (clean code, no findings expected) fixture files."""
    case_dir = base / "golden_cases" / "case-002"
    bundle_dir = case_dir / "bundle"
    files_dir = bundle_dir / "files"
    files_dir.mkdir(parents=True)

    (case_dir / "meta.json").write_text(json.dumps({
        "case_id": "case-002",
        "description": "Clean utility module. No issues expected.",
        "source": "hand_curated",
        "tags": ["clean", "python"],
    }))

    (case_dir / "expected.json").write_text(json.dumps({
        "expected_findings": [],
        "expected_non_findings": ["sql-injection", "xss"],
    }))

    (bundle_dir / "diff.patch").write_text(
        "diff --git a/utils.py b/utils.py\n"
        "new file 100644\n"
        "--- /dev/null\n"
        "+++ b/utils.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+def add(a, b):\n"
        "+    return a + b\n"
    )

    (files_dir / "utils.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
    )


def _write_case_003(base: Path) -> None:
    """Write case-003 (multi-turn, unused import rebuttal) fixture files."""
    case_dir = base / "golden_cases" / "case-003"
    bundle_dir = case_dir / "bundle"
    files_dir = bundle_dir / "files"
    files_dir.mkdir(parents=True)

    (case_dir / "meta.json").write_text(json.dumps({
        "case_id": "case-003",
        "description": "Dynamic module loader with unused import. Multi-turn rebuttal.",
        "source": "hand_curated",
        "tags": ["multi-turn", "python", "false-positive"],
    }))

    (case_dir / "expected.json").write_text(json.dumps({
        "expected_findings": [
            {
                "expected_id": "EF-003",
                "rule_id": "unused-import",
                "severity": "NIT",
                "category": "style",
                "file": "dynamic_loader.py",
                "approximate_line": 3,
                "description": "Import 'json' appears unused but is loaded dynamically.",
            }
        ],
        "expected_non_findings": [],
    }))

    (bundle_dir / "diff.patch").write_text(
        "diff --git a/dynamic_loader.py b/dynamic_loader.py\n"
        "new file 100644\n"
        "--- /dev/null\n"
        "+++ b/dynamic_loader.py\n"
        "@@ -0,0 +1,5 @@\n"
        "+import json\n"
        "+import importlib\n"
        "+def load_module(name):\n"
        "+    return importlib.import_module(name)\n"
    )

    (files_dir / "dynamic_loader.py").write_text(
        "import json\n"
        "import importlib\n"
        "def load_module(name):\n"
        "    return importlib.import_module(name)\n"
    )

    (case_dir / "script.json").write_text(json.dumps([
        {
            "turn_number": 1,
            "rebuttal_message_template": (
                "The 'json' import is used dynamically via importlib. "
                "Please dismiss finding {finding_id}."
            ),
            "target_expected_id": "EF-003",
            "expected_status_after": "dismissed",
            "is_valid_rebuttal": True,
        }
    ]))


def _write_all_fixtures(base: Path) -> None:
    """Write all three golden case fixtures."""
    _write_case_001(base)
    _write_case_002(base)
    _write_case_003(base)


# ===========================================================================
# Helpers: mock MCP session
# ===========================================================================


def _make_finding(
    *,
    finding_id: str = "F-001",
    rule_id: str = "sql-injection",
    severity: Severity = Severity.BUG,
    category: Category = Category.SECURITY,
    file: str = "app.py",
    start_line: int = 12,
    end_line: int = 14,
    status: FindingStatus = FindingStatus.OPEN,
) -> Finding:
    return Finding(
        finding_id=finding_id,
        rule_id=rule_id,
        severity=severity,
        category=category,
        message=f"Test finding: {rule_id}",
        primary_location=Location(file=file, start_line=start_line, end_line=end_line),
        fingerprint=f"fp-{finding_id}",
        confidence="high",
        evidence="Test evidence",
        status=status,
    )


def _make_mcp_review_response(
    *,
    session_id: str = "sess-int-001",
    findings: list[Finding] | None = None,
) -> dict:
    """Build a dict matching what call_start_review returns."""
    finding_dicts = [f.model_dump(mode="json") for f in (findings or [])]
    return {
        "session_id": session_id,
        "model": "copilot-gpt-4",
        "findings": finding_dicts,
        "finding_count": len(finding_dicts),
        "severity_summary": {},
    }


def _make_mcp_summary_response(
    *,
    session_id: str = "sess-int-001",
    findings: list[Finding] | None = None,
) -> dict:
    """Build a dict matching what call_get_review_summary returns."""
    finding_dicts = [f.model_dump(mode="json") for f in (findings or [])]
    return {
        "session_id": session_id,
        "status": "completed",
        "model": "copilot-gpt-4",
        "round_count": 2,
        "findings": finding_dicts,
        "finding_count": len(finding_dicts),
        "by_severity": {},
        "by_category": {},
        "by_status": {},
    }


class MockMCPSession:
    """Mock MCP session that returns predetermined findings per case.

    For case-001: 1 finding (sql-injection, BUG, SECURITY, app.py, line 12)
    For case-002: 0 findings (clean code)
    For case-003: 1 finding (unused-import, NIT, STYLE, dynamic_loader.py, line 3)
    """

    def __init__(self) -> None:
        self._call_count = 0

    def _case_001_findings(self) -> list[Finding]:
        return [
            _make_finding(
                finding_id="F-001",
                rule_id="sql-injection",
                severity=Severity.BUG,
                category=Category.SECURITY,
                file="app.py",
                start_line=12,
                end_line=14,
            )
        ]

    def _case_002_findings(self) -> list[Finding]:
        return []

    def _case_003_findings(self) -> list[Finding]:
        return [
            _make_finding(
                finding_id="F-003",
                rule_id="unused-import",
                severity=Severity.NIT,
                category=Category.STYLE,
                file="dynamic_loader.py",
                start_line=3,
                end_line=3,
            )
        ]

    def get_review_response(self, case_id: str) -> dict:
        findings_map = {
            "case-001": self._case_001_findings,
            "case-002": self._case_002_findings,
            "case-003": self._case_003_findings,
        }
        getter = findings_map.get(case_id, self._case_002_findings)
        return _make_mcp_review_response(
            session_id=f"sess-{case_id}",
            findings=getter(),
        )

    def get_discuss_response(self, case_id: str) -> dict:
        """After discuss, return updated findings with dismissed status."""
        if case_id == "case-003":
            dismissed = _make_finding(
                finding_id="F-003",
                rule_id="unused-import",
                severity=Severity.NIT,
                category=Category.STYLE,
                file="dynamic_loader.py",
                start_line=3,
                end_line=3,
                status=FindingStatus.DISMISSED,
            )
            return {
                "response": "Finding dismissed.",
                "updated_findings": [dismissed.model_dump(mode="json")],
                "finding_count_by_status": {"dismissed": 1},
            }
        return {"response": "OK", "updated_findings": [], "finding_count_by_status": {}}

    def get_summary_response(self, case_id: str) -> dict:
        """Return summary with updated statuses after discuss."""
        if case_id == "case-003":
            dismissed = _make_finding(
                finding_id="F-003",
                rule_id="unused-import",
                severity=Severity.NIT,
                category=Category.STYLE,
                file="dynamic_loader.py",
                start_line=3,
                end_line=3,
                status=FindingStatus.DISMISSED,
            )
            return _make_mcp_summary_response(
                session_id=f"sess-{case_id}",
                findings=[dismissed],
            )
        return _make_mcp_summary_response(session_id=f"sess-{case_id}")


class RealisticMCPSession(MockMCPSession):
    """MockMCPSession variant that adds a noise finding to case-001.

    This produces finite SNR values (signal/noise != inf) which avoids
    statistics.stdev crashes when aggregating across multiple cases.
    Used for tests that run all 3 cases together or multiple trials.
    """

    def _case_001_findings(self) -> list[Finding]:
        return [
            _make_finding(
                finding_id="F-001",
                rule_id="sql-injection",
                severity=Severity.BUG,
                category=Category.SECURITY,
                file="app.py",
                start_line=12,
                end_line=14,
            ),
            _make_finding(
                finding_id="F-NOISE",
                rule_id="style-nitpick",
                severity=Severity.NIT,
                category=Category.STYLE,
                file="other.py",
                start_line=99,
                end_line=99,
            ),
        ]

    def _case_002_findings(self) -> list[Finding]:
        """Return a noise finding for case-002 so SNR is finite (not inf)."""
        return [
            _make_finding(
                finding_id="F-NOISE-002",
                rule_id="false-alarm",
                severity=Severity.NIT,
                category=Category.STYLE,
                file="utils.py",
                start_line=1,
                end_line=1,
            ),
        ]

    def _case_003_findings(self) -> list[Finding]:
        """Also add noise to case-003 so SNR is finite everywhere."""
        return [
            _make_finding(
                finding_id="F-003",
                rule_id="unused-import",
                severity=Severity.NIT,
                category=Category.STYLE,
                file="dynamic_loader.py",
                start_line=3,
                end_line=3,
            ),
            _make_finding(
                finding_id="F-NOISE-003",
                rule_id="some-noise",
                severity=Severity.NIT,
                category=Category.STYLE,
                file="other.py",
                start_line=50,
                end_line=50,
            ),
        ]


def _default_thresholds() -> dict[str, float]:
    return {
        "precision": 0.70,
        "recall": 0.60,
        "severity_accuracy": 0.80,
        "category_accuracy": 0.70,
        "fp_rate": 0.20,
        "rebuttal_accuracy": 0.75,
        "snr": 3.0,
    }


def _easy_thresholds() -> dict[str, float]:
    """Thresholds that are easy to pass for integration tests."""
    return {
        "precision": 0.50,
        "recall": 0.30,
        "severity_accuracy": 0.50,
        "category_accuracy": 0.50,
        "fp_rate": 0.50,
        "rebuttal_accuracy": 0.50,
        "snr": 0.5,
    }


def _impossible_thresholds() -> dict[str, float]:
    """Thresholds that are impossible to pass."""
    return {
        "precision": 1.0,
        "recall": 1.0,
        "severity_accuracy": 1.0,
        "category_accuracy": 1.0,
        "fp_rate": 0.0,
        "rebuttal_accuracy": 1.0,
        "snr": 100.0,
    }


# ===========================================================================
# Helpers: mock MCP function builders
# ===========================================================================


def _build_mock_start_review(mock_mcp: MockMCPSession) -> AsyncMock:
    """Build a mock call_start_review that dispatches based on case_id."""
    async def _mock_start_review(session, bundle, case_id, **kwargs):
        return mock_mcp.get_review_response(case_id)
    return AsyncMock(side_effect=_mock_start_review)


def _build_mock_discuss(mock_mcp: MockMCPSession) -> AsyncMock:
    """Build a mock call_discuss that dispatches based on session_id."""
    async def _mock_discuss(session, session_id, message, **kwargs):
        # Extract case_id from session_id (sess-case-NNN)
        case_id = session_id.replace("sess-", "")
        return mock_mcp.get_discuss_response(case_id)
    return AsyncMock(side_effect=_mock_discuss)


def _build_mock_summary(mock_mcp: MockMCPSession) -> AsyncMock:
    """Build a mock call_get_review_summary that dispatches per session."""
    async def _mock_summary(session, session_id, **kwargs):
        case_id = session_id.replace("sess-", "")
        return mock_mcp.get_summary_response(case_id)
    return AsyncMock(side_effect=_mock_summary)


# ===========================================================================
# Test: Full pipeline end-to-end
# ===========================================================================


class TestFullPipeline:
    """Full pipeline: load cases -> mock MCP -> run harness -> scorecard."""

    async def test_full_pipeline_produces_scorecard(self, tmp_path: Path) -> None:
        """Load real fixtures, run through pipeline with mock MCP, get valid scorecard."""
        fixtures_dir = tmp_path / "fixtures"
        _write_all_fixtures(fixtures_dir)

        cases = load_cases(str(fixtures_dir))
        assert len(cases) == 3

        # Use RealisticMCPSession: adds a noise finding to case-001 so that
        # SNR is finite (avoids stdev(inf, inf, inf) crash in aggregation).
        mock_mcp = RealisticMCPSession()
        mock_session = AsyncMock()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock) as mock_model_grade,
        ):
            # Tier 2 model grader called for the noise finding -> return no_match
            mock_model_grade.return_value = GraderResult(
                tier=2,
                verdict=GraderVerdict.NO_MATCH,
                confidence=GraderConfidence.MEDIUM,
                matched_expected_id=None,
                actual_finding_id="F-NOISE",
                reasoning="Model grader: noise finding",
            )

            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_easy_thresholds(),
            )

        assert isinstance(harness_run, EvalRun)
        assert len(harness_run.cases) == 3
        assert harness_run.aggregate is not None
        assert harness_run.duration_seconds >= 0
        assert harness_run.model_evaluated == "copilot-gpt-4"

        # Generate scorecard
        case_descriptions = {c.case_id: c.description for c in cases}
        scorecard = generate_scorecard(
            harness_run, _easy_thresholds(), case_descriptions=case_descriptions
        )
        assert isinstance(scorecard, Scorecard)
        assert len(scorecard.per_case_summary) == 3

        # Render markdown (should not crash)
        md = render_markdown(scorecard)
        assert "Scorecard" in md

    async def test_case_001_has_correct_metrics(self, tmp_path: Path) -> None:
        """case-001: 1 finding matching 1 expected -> precision=1.0, recall=1.0."""
        fixtures_dir = tmp_path / "fixtures"
        _write_case_001(fixtures_dir)

        cases = load_cases(str(fixtures_dir), case_ids=["case-001"])
        assert len(cases) == 1

        mock_mcp = MockMCPSession()
        mock_session = AsyncMock()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        case_result = harness_run.cases[0]
        assert case_result.case_id == "case-001"
        trial = case_result.trials[0]
        # Fingerprint grader should match: same rule_id, same file, line 12 vs 12
        assert trial.metrics.precision == 1.0
        assert trial.metrics.recall == 1.0
        assert trial.metrics.severity_accuracy == 1.0
        assert trial.metrics.category_accuracy == 1.0

    async def test_case_002_clean_code_no_false_positives(self, tmp_path: Path) -> None:
        """case-002: 0 findings, 0 expected -> precision=1.0, recall=0.0 (none expected)."""
        fixtures_dir = tmp_path / "fixtures"
        _write_case_002(fixtures_dir)

        cases = load_cases(str(fixtures_dir), case_ids=["case-002"])
        assert len(cases) == 1

        mock_mcp = MockMCPSession()
        mock_session = AsyncMock()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        case_result = harness_run.cases[0]
        assert case_result.case_id == "case-002"
        trial = case_result.trials[0]
        # 0 findings, 0 expected => precision defaults to 1.0, recall is NaN
        # (clean cases have no recall denominator — see F7 / FR-004).
        assert trial.metrics.finding_count == 0
        assert trial.metrics.precision == 1.0
        assert math.isnan(trial.metrics.recall)

    async def test_case_003_fingerprint_matches_expected(self, tmp_path: Path) -> None:
        """case-003: finding matches expected via fingerprint grader."""
        fixtures_dir = tmp_path / "fixtures"
        _write_case_003(fixtures_dir)

        cases = load_cases(str(fixtures_dir), case_ids=["case-003"])
        assert len(cases) == 1

        mock_mcp = MockMCPSession()
        mock_session = AsyncMock()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_easy_thresholds(),
            )

        case_result = harness_run.cases[0]
        assert case_result.case_id == "case-003"
        trial = case_result.trials[0]
        # unused-import, same file, line 3 vs 3 -> match
        assert trial.metrics.recall == 1.0
        assert trial.metrics.precision == 1.0

    async def test_deterministic_across_trials(self, tmp_path: Path) -> None:
        """Mock MCP returns consistent results: all trials should have identical metrics."""
        fixtures_dir = tmp_path / "fixtures"
        _write_case_001(fixtures_dir)

        cases = load_cases(str(fixtures_dir), case_ids=["case-001"])

        # Use RealisticMCPSession so SNR is finite (avoids stdev crash
        # when aggregating 3 trials with identical inf values).
        mock_mcp = RealisticMCPSession()
        mock_session = AsyncMock()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock) as mock_t2,
        ):
            mock_t2.return_value = GraderResult(
                tier=2,
                verdict=GraderVerdict.NO_MATCH,
                confidence=GraderConfidence.MEDIUM,
                matched_expected_id=None,
                actual_finding_id="F-NOISE",
                reasoning="Noise",
            )
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=3,
                thresholds=_default_thresholds(),
            )

        case_result = harness_run.cases[0]
        assert len(case_result.trials) == 3

        metrics_0 = case_result.trials[0].metrics
        for trial in case_result.trials[1:]:
            assert trial.metrics.precision == metrics_0.precision
            assert trial.metrics.recall == metrics_0.recall
            assert trial.metrics.severity_accuracy == metrics_0.severity_accuracy
            assert trial.metrics.category_accuracy == metrics_0.category_accuracy


# ===========================================================================
# Test: CI exit codes
# ===========================================================================


class TestCIExitCodes:
    """--ci exit code 0 with passing thresholds, 1 with failing thresholds."""

    async def test_ci_exit_0_with_passing_thresholds(self, tmp_path: Path) -> None:
        """When all metrics pass thresholds, check_thresholds returns True -> exit 0."""
        fixtures_dir = tmp_path / "fixtures"
        _write_case_001(fixtures_dir)

        cases = load_cases(str(fixtures_dir), case_ids=["case-001"])

        mock_mcp = MockMCPSession()
        mock_session = AsyncMock()

        # Use easy thresholds that the perfect case-001 results will pass
        thresholds = _easy_thresholds()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=thresholds,
            )

        passes = check_thresholds(harness_run.aggregate, thresholds)
        assert passes is True

    async def test_ci_exit_1_with_failing_thresholds(self, tmp_path: Path) -> None:
        """When metrics fail strict thresholds, check_thresholds returns False."""
        fixtures_dir = tmp_path / "fixtures"
        _write_case_001(fixtures_dir)

        cases = load_cases(str(fixtures_dir), case_ids=["case-001"])

        # Use a mock that returns no findings (misses the expected finding),
        # producing recall=0.0 which will fail even moderate thresholds.
        class EmptyMCP(MockMCPSession):
            def _case_001_findings(self):
                return []  # No findings -> recall=0.0

        empty_mcp = EmptyMCP()
        mock_session = AsyncMock()

        thresholds = _default_thresholds()  # recall >= 0.60 will fail

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(empty_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(empty_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(empty_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=thresholds,
            )

        # recall=0.0 should fail the 0.60 threshold
        assert harness_run.aggregate.recall.mean == 0.0
        passes = check_thresholds(harness_run.aggregate, thresholds)
        assert passes is False

    async def test_cli_run_ci_exit_0(self, tmp_path: Path) -> None:
        """Full CLI run() with --ci returns exit code 0 for passing results."""
        from eval.cli import parse_args, run as cli_run

        thresholds = _easy_thresholds()
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))
        output_dir = tmp_path / "results"

        # Build a known-passing run result
        run_result = _build_passing_run_result()

        args = parse_args([
            "--ci",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_cli_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=run_result),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=True),
        ):
            mock_sc.return_value = MagicMock()
            exit_code = await cli_run(args)

        assert exit_code == 0

    async def test_cli_run_ci_exit_1(self, tmp_path: Path) -> None:
        """Full CLI run() with --ci returns exit code 1 for failing results."""
        from eval.cli import parse_args, run as cli_run

        thresholds = _impossible_thresholds()
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_file.write_text(json.dumps(thresholds))
        output_dir = tmp_path / "results"

        run_result = _build_failing_run_result()

        args = parse_args([
            "--ci",
            "--thresholds", str(thresholds_file),
            "--output-dir", str(output_dir),
            "--container", "test-container",
        ])

        with (
            patch("eval.cli.check_prompt_version", return_value="abc123def456"),
            patch("eval.cli.load_cases", return_value=[MagicMock()]),
            patch("eval.cli.connect", _mock_cli_connect()),
            patch("eval.cli.run_eval", new_callable=AsyncMock, return_value=run_result),
            patch("eval.cli.generate_scorecard") as mock_sc,
            patch("eval.cli.render_markdown", return_value="# Scorecard"),
            patch("eval.cli.render_json", return_value='{"run_id": "test"}'),
            patch("eval.cli.check_thresholds", return_value=False),
        ):
            mock_sc.return_value = MagicMock()
            exit_code = await cli_run(args)

        assert exit_code == 1


# ===========================================================================
# Test: Regression detection
# ===========================================================================


class TestRegressionDetection:
    """Swap mock responses to simulate degraded prompt (fewer matches)."""

    async def test_regression_detected_when_recall_drops(self, tmp_path: Path) -> None:
        """Baseline has recall=1.0, degraded run has recall=0.0 -> regression."""
        from eval.reporter import compare_runs

        fixtures_dir = tmp_path / "fixtures"
        _write_case_001(fixtures_dir)
        cases = load_cases(str(fixtures_dir), case_ids=["case-001"])

        mock_session = AsyncMock()

        # --- Baseline run: good results (finding matches) ---
        good_mcp = MockMCPSession()
        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(good_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(good_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(good_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            baseline_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        assert baseline_run.aggregate.recall.mean == 1.0

        # --- Degraded run: mock returns NO findings for case-001 ---
        class DegradedMCP(MockMCPSession):
            def _case_001_findings(self):
                return []  # No findings returned -> recall drops to 0

        degraded_mcp = DegradedMCP()
        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(degraded_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(degraded_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(degraded_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            degraded_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        assert degraded_run.aggregate.recall.mean == 0.0

        # --- Compare ---
        comparison = compare_runs(degraded_run, baseline_run)
        assert "recall" in comparison.regressions
        assert comparison.deltas["recall"].delta < 0
        assert comparison.deltas["recall"].delta_pct == pytest.approx(-100.0)

    async def test_improvement_detected_when_precision_rises(self, tmp_path: Path) -> None:
        """Baseline has lower precision, improved run has higher -> improvement."""
        from eval.reporter import compare_runs

        fixtures_dir = tmp_path / "fixtures"
        _write_case_001(fixtures_dir)
        cases = load_cases(str(fixtures_dir), case_ids=["case-001"])

        mock_session = AsyncMock()

        # --- Baseline: returns 1 match + 1 noise finding ---
        class NoisyMCP(MockMCPSession):
            def _case_001_findings(self):
                return [
                    _make_finding(
                        finding_id="F-001",
                        rule_id="sql-injection",
                        severity=Severity.BUG,
                        category=Category.SECURITY,
                        file="app.py",
                        start_line=12,
                    ),
                    _make_finding(
                        finding_id="F-NOISE",
                        rule_id="some-noise",
                        severity=Severity.NIT,
                        category=Category.STYLE,
                        file="other.py",
                        start_line=99,
                    ),
                ]

        noisy_mcp = NoisyMCP()
        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(noisy_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(noisy_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(noisy_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock) as mock_t2,
        ):
            # Tier 2 will be called for F-NOISE: return no_match
            mock_t2.return_value = GraderResult(
                tier=2,
                verdict=GraderVerdict.NO_MATCH,
                confidence=GraderConfidence.MEDIUM,
                matched_expected_id=None,
                actual_finding_id="F-NOISE",
                reasoning="Noise finding",
            )
            baseline_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        # Baseline has precision < 1.0 (1 match, 1 no_match)
        assert baseline_run.aggregate.precision.mean < 1.0

        # --- Improved run: only the matching finding ---
        good_mcp = MockMCPSession()
        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(good_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(good_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(good_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            improved_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_default_thresholds(),
            )

        assert improved_run.aggregate.precision.mean == 1.0

        comparison = compare_runs(improved_run, baseline_run)
        assert "precision" in comparison.improvements
        assert comparison.deltas["precision"].delta > 0


# ===========================================================================
# Test: Multi-turn rebuttal accuracy
# ===========================================================================


class TestMultiTurnRebuttal:
    """Multi-turn case produces rebuttal_accuracy in scorecard."""

    async def test_rebuttal_accuracy_in_scorecard(self, tmp_path: Path) -> None:
        """case-003 multi-turn: discuss -> dismiss -> rebuttal_accuracy = 1.0."""
        fixtures_dir = tmp_path / "fixtures"
        _write_case_003(fixtures_dir)

        cases = load_cases(str(fixtures_dir), case_ids=["case-003"])
        assert len(cases) == 1
        assert cases[0].multi_turn_script is not None

        mock_mcp = MockMCPSession()
        mock_session = AsyncMock()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_easy_thresholds(),
            )

        # The multi-turn case should have rebuttal results
        case_result = harness_run.cases[0]
        assert case_result.rebuttal_results is not None
        assert len(case_result.rebuttal_results) == 1

        rebuttal = case_result.rebuttal_results[0]
        assert rebuttal.turn_number == 1
        assert rebuttal.target_expected_id == "EF-003"
        assert rebuttal.correct is True
        assert rebuttal.finding_not_found is False
        assert rebuttal.expected_status == FindingStatus.DISMISSED
        assert rebuttal.actual_status == FindingStatus.DISMISSED

        # Aggregate should have rebuttal_accuracy
        assert harness_run.aggregate.rebuttal_accuracy is not None
        assert harness_run.aggregate.rebuttal_accuracy.mean == 1.0

    async def test_rebuttal_accuracy_in_rendered_scorecard(self, tmp_path: Path) -> None:
        """Rebuttal accuracy appears in generated scorecard."""
        fixtures_dir = tmp_path / "fixtures"
        _write_case_003(fixtures_dir)

        cases = load_cases(str(fixtures_dir), case_ids=["case-003"])

        mock_mcp = MockMCPSession()
        mock_session = AsyncMock()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock),
        ):
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_easy_thresholds(),
            )

        thresholds = _easy_thresholds()
        scorecard = generate_scorecard(
            harness_run, thresholds,
            case_descriptions={c.case_id: c.description for c in cases},
        )
        md = render_markdown(scorecard)

        assert "Rebuttal Accuracy" in md
        assert "1.00" in md  # rebuttal_accuracy mean

    async def test_multi_turn_with_all_cases(self, tmp_path: Path) -> None:
        """Full run with all 3 cases: only case-003 has rebuttal_results."""
        fixtures_dir = tmp_path / "fixtures"
        _write_all_fixtures(fixtures_dir)

        cases = load_cases(str(fixtures_dir))

        # Use RealisticMCPSession so SNR is finite across cases.
        mock_mcp = RealisticMCPSession()
        mock_session = AsyncMock()

        with (
            patch("eval.runner.call_start_review", _build_mock_start_review(mock_mcp)),
            patch("eval.runner.call_discuss", _build_mock_discuss(mock_mcp)),
            patch("eval.runner.call_get_review_summary", _build_mock_summary(mock_mcp)),
            patch("eval.graders.pipeline.model_grade", new_callable=AsyncMock) as mock_t2,
        ):
            mock_t2.return_value = GraderResult(
                tier=2,
                verdict=GraderVerdict.NO_MATCH,
                confidence=GraderConfidence.MEDIUM,
                matched_expected_id=None,
                actual_finding_id="F-NOISE",
                reasoning="Noise",
            )
            harness_run = await run_eval(
                cases=cases,
                session=mock_session,
                num_trials=1,
                thresholds=_easy_thresholds(),
            )

        # Only case-003 should have rebuttal_results
        for case_result in harness_run.cases:
            if case_result.case_id == "case-003":
                assert case_result.rebuttal_results is not None
                assert len(case_result.rebuttal_results) == 1
                assert case_result.rebuttal_results[0].correct is True
            else:
                assert case_result.rebuttal_results is None


# ===========================================================================
# Helpers: factory functions for CLI tests
# ===========================================================================


def _make_metric(mean: float = 0.85, passes: bool = True) -> MetricWithSEM:
    sem = 0.02
    return MetricWithSEM(
        mean=mean,
        sem=sem,
        ci_lower=mean - 1.96 * sem,
        ci_upper=mean + 1.96 * sem,
        passes_threshold=passes,
    )


def _build_passing_run_result() -> EvalRun:
    return EvalRun(
        run_id="run-integration-pass",
        timestamp=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        model_evaluated="copilot-gpt-4",
        grader_model="claude-sonnet-4-6",
        grader_prompt_version="abc123",
        num_trials=1,
        line_tolerance=5,
        cases=[
            CaseResult(
                case_id="case-001",
                trials=[TrialResult(
                    trial_number=1,
                    findings=[],
                    graded=[],
                    metrics=TrialMetrics(
                        precision=1.0, recall=1.0,
                        severity_accuracy=1.0, category_accuracy=1.0,
                        snr=float("inf"), novel_count=0,
                        grading_error_count=0, finding_count=1,
                    ),
                )],
                pass_at_1={"EF-001": True},
                pass_at_k={"EF-001": True},
            ),
        ],
        aggregate=AggregateMetrics(
            precision=_make_metric(1.0, True),
            recall=_make_metric(1.0, True),
            severity_accuracy=_make_metric(1.0, True),
            category_accuracy=_make_metric(1.0, True),
            fp_rate=_make_metric(0.0, True),
            snr=_make_metric(float("inf"), True),
            novel_count=0,
            pass_at_1_rate=1.0,
            pass_at_k_rate=1.0,
        ),
        pass_fail=True,
        duration_seconds=1.0,
    )


def _build_failing_run_result() -> EvalRun:
    return EvalRun(
        run_id="run-integration-fail",
        timestamp=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        model_evaluated="copilot-gpt-4",
        grader_model="claude-sonnet-4-6",
        grader_prompt_version="abc123",
        num_trials=1,
        line_tolerance=5,
        cases=[
            CaseResult(
                case_id="case-001",
                trials=[TrialResult(
                    trial_number=1,
                    findings=[],
                    graded=[],
                    metrics=TrialMetrics(
                        precision=0.3, recall=0.2,
                        severity_accuracy=0.4, category_accuracy=0.3,
                        snr=0.5, novel_count=0,
                        grading_error_count=0, finding_count=1,
                    ),
                )],
                pass_at_1={"EF-001": False},
                pass_at_k={"EF-001": False},
            ),
        ],
        aggregate=AggregateMetrics(
            precision=_make_metric(0.3, False),
            recall=_make_metric(0.2, False),
            severity_accuracy=_make_metric(0.4, False),
            category_accuracy=_make_metric(0.3, False),
            fp_rate=_make_metric(0.7, False),
            snr=_make_metric(0.5, False),
            novel_count=0,
            pass_at_1_rate=0.0,
            pass_at_k_rate=0.0,
        ),
        pass_fail=False,
        duration_seconds=1.0,
    )


def _mock_cli_connect():
    """Return a mock for the CLI connect that yields a MagicMock session."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_connect(container: str):
        yield MagicMock()

    return _fake_connect
