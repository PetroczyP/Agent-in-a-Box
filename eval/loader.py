"""Golden case loader for the eval harness.

Loads and validates golden cases from the fixtures directory structure.
Each case is a directory under fixtures_dir/golden_cases/<case_id>/ containing:
  - meta.json      (required)
  - expected.json   (required)
  - bundle/         (required directory)
    - diff.patch    (required)
    - files/        (required directory with source files)
  - script.json     (optional, multi-turn script)

Adding a new case is a directory operation — no code changes required.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

from eval.models import (
    DualMetricConfig,
    ExpectedFinding,
    GoldenCase,
    GoldenCaseSource,
    TurnScript,
)
from server.models import ReviewBundle


def load_cases(
    fixtures_dir: str | Path,
    case_ids: list[str] | None = None,
) -> list[GoldenCase]:
    """Load golden cases from fixtures directory.

    Args:
        fixtures_dir: Path to fixtures directory (parent of golden_cases/).
        case_ids: Optional filter -- if provided, only load these case IDs.

    Returns:
        List of validated GoldenCase objects, sorted by case_id.

    Raises:
        FileNotFoundError: If fixtures_dir or golden_cases/ doesn't exist.
        ValueError: If a case directory is malformed (missing required files,
                    invalid JSON).
    """
    fixtures_path = Path(fixtures_dir)
    if not fixtures_path.is_dir():
        raise FileNotFoundError(f"Fixtures directory not found: {fixtures_path}")

    golden_dir = fixtures_path / "golden_cases"
    if not golden_dir.is_dir():
        raise FileNotFoundError(
            f"golden_cases/ directory not found in {fixtures_path}"
        )

    # Discover case directories (skip non-directory entries)
    available_dirs = sorted(
        [d for d in golden_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )
    available_ids = {d.name for d in available_dirs}

    # Apply case_ids filter
    if case_ids is not None:
        missing = [cid for cid in case_ids if cid not in available_ids]
        if missing:
            raise ValueError(
                f"Case IDs not found in {golden_dir}: {', '.join(missing)}"
            )
        id_set = set(case_ids)
        available_dirs = [d for d in available_dirs if d.name in id_set]

    cases: list[GoldenCase] = []
    for case_dir in available_dirs:
        cases.append(_load_single_case(case_dir))

    return cases


def _load_single_case(case_dir: Path) -> GoldenCase:
    """Load and validate a single golden case from its directory."""
    case_id = case_dir.name

    meta = _read_json(case_dir / "meta.json", case_id)
    expected = _read_json(case_dir / "expected.json", case_id)

    bundle_dir = case_dir / "bundle"
    if not bundle_dir.is_dir():
        raise ValueError(
            f"Case '{case_id}': required bundle/ directory is missing"
        )

    diff_path = bundle_dir / "diff.patch"
    if not diff_path.is_file():
        raise ValueError(
            f"Case '{case_id}': required bundle/diff.patch is missing"
        )
    diff_content = diff_path.read_text(encoding="utf-8")

    files_dir = bundle_dir / "files"
    if not files_dir.is_dir():
        raise ValueError(
            f"Case '{case_id}': required bundle/files/ directory is missing"
        )
    bundle_files = _load_bundle_files(files_dir, case_id)

    bundle = ReviewBundle(diff=diff_content, files=bundle_files)

    multi_turn_script = _load_optional_script(case_dir, case_id)

    try:
        expected_findings = [
            ExpectedFinding(**ef) for ef in expected["expected_findings"]
        ]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"Case '{case_id}': invalid expected.json: {exc}"
        ) from exc

    expected_non_findings = expected.get("expected_non_findings", [])

    dual_metric = None
    if "dual_metric" in meta:
        dm_config = meta["dual_metric"]
        fixed_bundle = _load_bundle_from_dir(
            case_dir / dm_config["fixed_dir"], case_id
        )
        dual_metric = DualMetricConfig(
            vulnerable_dir=dm_config["vulnerable_dir"],
            fixed_dir=dm_config["fixed_dir"],
            fixed_bundle=fixed_bundle,
        )

    return GoldenCase(
        case_id=meta["case_id"],
        description=meta["description"],
        source=GoldenCaseSource(meta["source"]),
        tags=meta["tags"],
        bundle=bundle,
        expected_findings=expected_findings,
        expected_non_findings=expected_non_findings,
        multi_turn_script=multi_turn_script,
        dual_metric=dual_metric,
    )


def _load_bundle_from_dir(bundle_dir: Path, case_id: str) -> ReviewBundle:
    """Load a ReviewBundle from a bundle directory (diff.patch + files/).

    Raises:
        ValueError: If the directory or required files are missing.
    """
    if not bundle_dir.is_dir():
        raise ValueError(
            f"Case '{case_id}': bundle directory missing: {bundle_dir.name}"
        )
    diff_path = bundle_dir / "diff.patch"
    if not diff_path.is_file():
        raise ValueError(
            f"Case '{case_id}': required {bundle_dir.name}/diff.patch is missing"
        )
    files_dir = bundle_dir / "files"
    if not files_dir.is_dir():
        raise ValueError(
            f"Case '{case_id}': required {bundle_dir.name}/files/ is missing"
        )
    return ReviewBundle(
        diff=diff_path.read_text(encoding="utf-8"),
        files=_load_bundle_files(files_dir, case_id),
    )


def _read_json(path: Path, case_id: str) -> dict:
    """Read and parse a JSON file, raising ValueError with context on failure."""
    if not path.is_file():
        raise ValueError(
            f"Case '{case_id}': required {path.name} is missing"
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Case '{case_id}': invalid JSON in {path.name}: {exc}"
        ) from exc


def _load_bundle_files(files_dir: Path, case_id: str) -> dict[str, str]:
    """Load source files from bundle/files/ directory.

    Filenames are URL-encoded to support paths with slashes:
    e.g. 'src%2Fmain.py' decodes to 'src/main.py'.

    Rejects symlinks and any entry whose resolved path escapes files_dir,
    so a malicious fixture cannot exfiltrate host files.
    """
    files: dict[str, str] = {}
    root = files_dir.resolve()
    for file_path in sorted(files_dir.iterdir()):
        if file_path.is_symlink():
            raise ValueError(
                f"Case '{case_id}': symlink not allowed in bundle/files/: "
                f"{file_path.name}"
            )
        resolved = file_path.resolve()
        if root not in resolved.parents and resolved != root:
            raise ValueError(
                f"Case '{case_id}': bundle entry escapes fixture root: "
                f"{file_path.name}"
            )
        if file_path.is_file():
            relative_path = unquote(file_path.name)
            files[relative_path] = file_path.read_text(encoding="utf-8")
    return files


def _load_optional_script(case_dir: Path, case_id: str) -> list[TurnScript] | None:
    """Load optional script.json if present."""
    script_path = case_dir / "script.json"
    if not script_path.is_file():
        return None

    try:
        raw = json.loads(script_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Case '{case_id}': invalid JSON in script.json: {exc}"
        ) from exc

    if not isinstance(raw, list):
        raise ValueError(
            f"Case '{case_id}': script.json must be a JSON array, got {type(raw).__name__}"
        )

    try:
        return [TurnScript(**turn) for turn in raw]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Case '{case_id}': invalid script.json content: {exc}"
        ) from exc
