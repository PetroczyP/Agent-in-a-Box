"""RED tests for golden case loader (T002).

Tests loading golden cases from fixture directories, error handling for
malformed cases, optional file loading, and case ID filtering.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.loader import load_cases
from eval.models import (
    DualMetricConfig,
    ExpectedFinding,
    GoldenCase,
    GoldenCaseSource,
    TurnScript,
)
from server.models import FindingStatus, Severity, Category


# --- Helpers to build fixture directories ---


def _write_meta(case_dir: Path, **overrides: object) -> None:
    """Write a valid meta.json to a case directory."""
    meta = {
        "case_id": case_dir.name,
        "description": f"Test case {case_dir.name}",
        "source": "hand_curated",
        "tags": ["security", "python"],
    }
    meta.update(overrides)
    (case_dir / "meta.json").write_text(json.dumps(meta))


def _write_expected(case_dir: Path, **overrides: object) -> None:
    """Write a valid expected.json to a case directory."""
    expected = {
        "expected_findings": [
            {
                "expected_id": "EF-001",
                "rule_id": "sql-injection",
                "severity": "BUG",
                "category": "security",
                "file": "src/main.py",
                "approximate_line": 10,
                "description": "SQL injection vulnerability",
            }
        ],
    }
    expected.update(overrides)
    (case_dir / "expected.json").write_text(json.dumps(expected))


def _write_bundle(case_dir: Path) -> None:
    """Write a valid bundle/ directory with diff.patch and files/."""
    bundle_dir = case_dir / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "diff.patch").write_text(
        "--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new"
    )
    files_dir = bundle_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    # Create a source file using URL-encoded path: src%2Fmain.py -> src/main.py
    (files_dir / "src%2Fmain.py").write_text("def query(user_input):\n    return f'SELECT * FROM users WHERE id={user_input}'")


def _make_valid_case(fixtures_dir: Path, case_id: str = "case-001") -> Path:
    """Create a complete, valid golden case directory."""
    golden_dir = fixtures_dir / "golden_cases"
    golden_dir.mkdir(parents=True, exist_ok=True)
    case_dir = golden_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    _write_meta(case_dir)
    _write_expected(case_dir)
    _write_bundle(case_dir)
    return case_dir


# --- Tests ---


class TestLoadValidCase:
    """Loading a well-formed case directory produces a correct GoldenCase."""

    def test_loads_single_valid_case(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert len(cases) == 1
        case = cases[0]
        assert isinstance(case, GoldenCase)
        assert case.case_id == "case-001"
        assert case.description == "Test case case-001"
        assert case.source == GoldenCaseSource.HAND_CURATED
        assert case.tags == ["security", "python"]

    def test_bundle_diff_loaded(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert "--- a/src/main.py" in cases[0].bundle.diff

    def test_bundle_files_loaded(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert "src/main.py" in cases[0].bundle.files
        assert "def query" in cases[0].bundle.files["src/main.py"]

    def test_expected_findings_loaded(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert len(cases[0].expected_findings) == 1
        ef = cases[0].expected_findings[0]
        assert ef.expected_id == "EF-001"
        assert ef.rule_id == "sql-injection"
        assert ef.severity == Severity.BUG
        assert ef.category == Category.SECURITY

    def test_multiple_cases_sorted_by_id(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-bravo")
        _make_valid_case(tmp_path, "case-alpha")
        _make_valid_case(tmp_path, "case-charlie")

        cases = load_cases(tmp_path)

        assert len(cases) == 3
        assert [c.case_id for c in cases] == ["case-alpha", "case-bravo", "case-charlie"]

    def test_bundle_multiple_files(self, tmp_path: Path) -> None:
        """Bundle files/ directory with multiple source files."""
        case_dir = _make_valid_case(tmp_path, "case-001")
        files_dir = case_dir / "bundle" / "files"
        (files_dir / "lib%2Futils.py").write_text("def helper(): pass")

        cases = load_cases(tmp_path)

        assert "src/main.py" in cases[0].bundle.files
        assert "lib/utils.py" in cases[0].bundle.files


class TestMissingRequiredFiles:
    """Missing required files raise clear ValueError."""

    def test_missing_meta_json(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-bad")
        (case_dir / "meta.json").unlink()

        with pytest.raises(ValueError, match="meta.json"):
            load_cases(tmp_path)

    def test_missing_expected_json(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-bad")
        (case_dir / "expected.json").unlink()

        with pytest.raises(ValueError, match="expected.json"):
            load_cases(tmp_path)

    def test_missing_bundle_dir(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-bad")
        import shutil
        shutil.rmtree(case_dir / "bundle")

        with pytest.raises(ValueError, match="bundle"):
            load_cases(tmp_path)

    def test_missing_diff_patch(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-bad")
        (case_dir / "bundle" / "diff.patch").unlink()

        with pytest.raises(ValueError, match="diff.patch"):
            load_cases(tmp_path)

    def test_missing_files_subdir(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-bad")
        import shutil
        shutil.rmtree(case_dir / "bundle" / "files")

        with pytest.raises(ValueError, match="files"):
            load_cases(tmp_path)


class TestInvalidJson:
    """Invalid JSON in required files raises ValueError."""

    def test_invalid_meta_json(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-bad")
        (case_dir / "meta.json").write_text("{invalid json")

        with pytest.raises(ValueError, match="meta.json"):
            load_cases(tmp_path)

    def test_invalid_expected_json(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-bad")
        (case_dir / "expected.json").write_text("not json at all")

        with pytest.raises(ValueError, match="expected.json"):
            load_cases(tmp_path)


class TestOptionalScriptJson:
    """Optional script.json loading."""

    def test_case_without_script_has_none(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert cases[0].multi_turn_script is None

    def test_case_with_script_loaded(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-001")
        script = [
            {
                "turn_number": 1,
                "rebuttal_message_template": "I disagree with {finding_id}",
                "target_expected_id": "EF-001",
                "expected_status_after": "dismissed",
                "is_valid_rebuttal": True,
            }
        ]
        (case_dir / "script.json").write_text(json.dumps(script))

        cases = load_cases(tmp_path)

        assert cases[0].multi_turn_script is not None
        assert len(cases[0].multi_turn_script) == 1
        ts = cases[0].multi_turn_script[0]
        assert ts.turn_number == 1
        assert ts.target_expected_id == "EF-001"
        assert ts.expected_status_after == FindingStatus.DISMISSED
        assert ts.is_valid_rebuttal is True

    def test_invalid_script_json_raises(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-001")
        (case_dir / "script.json").write_text("{not a list}")

        with pytest.raises(ValueError, match="script.json"):
            load_cases(tmp_path)


class TestOptionalDualMetric:
    """Optional dual_metric loading from meta.json."""

    def test_case_without_dual_metric_has_none(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert cases[0].dual_metric is None

    def test_case_with_dual_metric_loaded(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-001")
        meta = json.loads((case_dir / "meta.json").read_text())
        meta["dual_metric"] = {
            "vulnerable_dir": "bundle",
            "fixed_dir": "bundle-fixed",
        }
        (case_dir / "meta.json").write_text(json.dumps(meta))

        # Create the fixed bundle directory structure
        fixed_dir = case_dir / "bundle-fixed"
        fixed_dir.mkdir()
        (fixed_dir / "diff.patch").write_text(
            "--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+fixed"
        )
        files_dir = fixed_dir / "files"
        files_dir.mkdir()
        (files_dir / "src%2Fmain.py").write_text(
            "def query(user_input):\n    return cursor.execute('SELECT ...', (user_input,))"
        )

        cases = load_cases(tmp_path)

        assert cases[0].dual_metric is not None
        assert cases[0].dual_metric.vulnerable_dir == "bundle"
        assert cases[0].dual_metric.fixed_dir == "bundle-fixed"
        assert cases[0].dual_metric.fixed_bundle is not None
        assert "fixed" in cases[0].dual_metric.fixed_bundle.diff


class TestOptionalExpectedNonFindings:
    """Optional expected_non_findings loading from expected.json."""

    def test_defaults_to_empty_list(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert cases[0].expected_non_findings == []

    def test_loaded_when_present(self, tmp_path: Path) -> None:
        case_dir = _make_valid_case(tmp_path, "case-001")
        expected = json.loads((case_dir / "expected.json").read_text())
        expected["expected_non_findings"] = ["no-false-positive-on-sanitized-input"]
        (case_dir / "expected.json").write_text(json.dumps(expected))

        cases = load_cases(tmp_path)

        assert cases[0].expected_non_findings == ["no-false-positive-on-sanitized-input"]


class TestCaseIdFilter:
    """--cases filter by case ID."""

    def test_filter_single_case(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")
        _make_valid_case(tmp_path, "case-002")
        _make_valid_case(tmp_path, "case-003")

        cases = load_cases(tmp_path, case_ids=["case-002"])

        assert len(cases) == 1
        assert cases[0].case_id == "case-002"

    def test_filter_multiple_cases(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")
        _make_valid_case(tmp_path, "case-002")
        _make_valid_case(tmp_path, "case-003")

        cases = load_cases(tmp_path, case_ids=["case-001", "case-003"])

        assert len(cases) == 2
        assert [c.case_id for c in cases] == ["case-001", "case-003"]

    def test_nonexistent_case_id_raises(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        with pytest.raises(ValueError, match="case-999"):
            load_cases(tmp_path, case_ids=["case-999"])

    def test_mix_of_valid_and_invalid_ids_raises(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        with pytest.raises(ValueError, match="case-bad"):
            load_cases(tmp_path, case_ids=["case-001", "case-bad"])


class TestEmptyAndMissingDirectories:
    """Edge cases for empty or non-existent directories."""

    def test_empty_golden_cases_returns_empty_list(self, tmp_path: Path) -> None:
        golden_dir = tmp_path / "golden_cases"
        golden_dir.mkdir()

        cases = load_cases(tmp_path)

        assert cases == []

    def test_nonexistent_fixtures_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_cases(tmp_path / "no_such_dir")

    def test_nonexistent_golden_cases_subdir_raises(self, tmp_path: Path) -> None:
        # fixtures_dir exists but golden_cases/ does not
        with pytest.raises(FileNotFoundError, match="golden_cases"):
            load_cases(tmp_path)

    def test_non_directory_entries_ignored(self, tmp_path: Path) -> None:
        """Regular files inside golden_cases/ are silently skipped."""
        golden_dir = tmp_path / "golden_cases"
        golden_dir.mkdir()
        (golden_dir / "README.md").write_text("just a file, not a case")
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert len(cases) == 1
        assert cases[0].case_id == "case-001"


class TestStringAndPathInput:
    """Accepts both str and Path for fixtures_dir."""

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(str(tmp_path))

        assert len(cases) == 1

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        _make_valid_case(tmp_path, "case-001")

        cases = load_cases(tmp_path)

        assert len(cases) == 1


# ===========================================================================
# TestFixtureLibraryRequirements (T014)
# ===========================================================================


class TestFixtureLibraryRequirements:
    """Validates that the golden case fixture library meets T014 requirements:
    10+ bug cases, 5+ clean, 5+ dimension-specific, 2+ multi-turn, 2+ dual-metric."""

    @pytest.fixture
    def all_cases(self) -> list[GoldenCase]:
        """Load all golden cases from the real fixtures directory."""
        return load_cases("eval/fixtures")

    def test_at_least_20_cases_total(self, all_cases: list[GoldenCase]) -> None:
        assert len(all_cases) >= 20, (
            f"Need at least 20 golden cases, found {len(all_cases)}"
        )

    def test_at_least_10_bug_cases(self, all_cases: list[GoldenCase]) -> None:
        """Cases with non-empty expected_findings are bug cases."""
        bug_cases = [c for c in all_cases if len(c.expected_findings) > 0]
        assert len(bug_cases) >= 10, (
            f"Need at least 10 bug cases (non-empty expected_findings), "
            f"found {len(bug_cases)}"
        )

    def test_at_least_5_clean_cases(self, all_cases: list[GoldenCase]) -> None:
        """Cases with empty expected_findings are clean-code cases for FP measurement."""
        clean_cases = [c for c in all_cases if len(c.expected_findings) == 0]
        assert len(clean_cases) >= 5, (
            f"Need at least 5 clean-code cases (empty expected_findings), "
            f"found {len(clean_cases)}"
        )

    def test_at_least_5_dimensions_covered(self, all_cases: list[GoldenCase]) -> None:
        """Tags across all cases must cover at least 5 review dimensions."""
        dimensions = {"security", "correctness", "design", "tests",
                      "documentation", "performance", "error-handling",
                      "style", "multi-turn", "dual-metric"}
        covered = set()
        for case in all_cases:
            covered.update(t for t in case.tags if t in dimensions)
        assert len(covered) >= 5, (
            f"Need at least 5 review dimensions covered, "
            f"found {len(covered)}: {covered}"
        )

    def test_at_least_2_multi_turn_cases(self, all_cases: list[GoldenCase]) -> None:
        mt_cases = [c for c in all_cases if c.multi_turn_script is not None]
        assert len(mt_cases) >= 2, (
            f"Need at least 2 multi-turn cases with script.json, "
            f"found {len(mt_cases)}"
        )

    def test_at_least_2_dual_metric_cases(self, all_cases: list[GoldenCase]) -> None:
        dm_cases = [c for c in all_cases if c.dual_metric is not None]
        assert len(dm_cases) >= 2, (
            f"Need at least 2 dual-metric cases, found {len(dm_cases)}"
        )

    def test_all_cases_load_without_errors(self, all_cases: list[GoldenCase]) -> None:
        """Every case must be a valid GoldenCase (no load errors)."""
        for case in all_cases:
            assert case.case_id, f"Case missing case_id"
            assert case.description, f"Case {case.case_id} missing description"
            assert case.bundle.diff, f"Case {case.case_id} missing diff"
            assert case.bundle.files, f"Case {case.case_id} missing files"
