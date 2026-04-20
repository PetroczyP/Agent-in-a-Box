"""CLI entry point for the eval harness.

Wires together: loader -> runner -> scorer -> reporter pipeline.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from eval.graders import DEFAULT_GRADER_MODEL
from eval.loader import load_cases
from eval.mcp_client import MCPAbortError, connect, detect_container
from eval.models import CIMethod, EvalRun
from eval.prompt_version import (
    PromptDirtyError,
    accept_prompt,
    check_prompt_version,
    compute_prompt_hash,
    record_flip_rate,
    run_consistency_check,
    run_full_consistency_check,
)
from eval.reporter import (
    compare_runs,
    generate_scorecard,
    render_json,
    render_markdown,
)
from eval.runner import run_eval
from eval.scorer import check_thresholds

logger = logging.getLogger(__name__)

# Default fixtures and grader prompt directory (relative to CWD).
_FIXTURES_DIR = Path("eval/fixtures")
_GRADER_DIR = _FIXTURES_DIR / "grader"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with all 14 flags.
    """
    parser = argparse.ArgumentParser(
        prog="python -m eval",
        description="AgentinaBox eval harness — measure reviewer quality.",
    )

    parser.add_argument(
        "--trials",
        type=int,
        default=3,
        help="Number of trials per golden case (default: 3)",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        default=False,
        help="CI mode: exit 0/1 based on thresholds, print markdown",
    )
    parser.add_argument(
        "--grader-model",
        type=str,
        default=DEFAULT_GRADER_MODEL,
        help=f"Model for Tier 2 grading (default: {DEFAULT_GRADER_MODEL})",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default="eval/fixtures/thresholds.json",
        help="Path to thresholds JSON file",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Path to previous run JSON for comparison",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default="all",
        help="Comma-separated case IDs to run, or 'all' (default: all)",
    )
    parser.add_argument(
        "--container",
        type=str,
        default=None,
        help="Docker container name/ID (default: auto-detect)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="eval/results/",
        help="Directory for output files (default: eval/results/)",
    )
    parser.add_argument(
        "--line-tolerance",
        type=int,
        default=5,
        help="Line number tolerance for fingerprint matching (default: 5)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries per case on rate limit/timeout (default: 3)",
    )
    parser.add_argument(
        "--prompt-consistency-check",
        action="store_true",
        default=False,
        help="Run old-vs-new grader prompt comparison and exit",
    )
    parser.add_argument(
        "--accept-prompt",
        action="store_true",
        default=False,
        help="Accept current grader prompt as new baseline and exit",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print per-case progress to stderr",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent cases (default: 5)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help=(
            "Strict mode: inconclusive (wilson_insufficient_n) metrics "
            "fail the gate. Default off — inconclusive metrics are "
            "surfaced but do not fail --ci runs."
        ),
    )

    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    """Main execution flow. Returns exit code (0, 1, or 2).

    Execution flow:
    1. Parse args (already done by caller)
    2. Handle --prompt-consistency-check early exit
    3. Handle --accept-prompt early exit
    4. Check prompt version (unless skipped)
    5. Load thresholds
    6. Load golden cases (with optional --cases filter)
    7. Connect to container (auto-detect or --container)
    8. Run eval via runner.run_eval()
    9. Generate scorecard via reporter
    10. Write output files (JSON + markdown)
    11. If --baseline: compare runs
    12. If --ci: print markdown to stdout, exit 0 or 1
    13. Otherwise exit 0
    """
    grader_dir = _GRADER_DIR

    if args.prompt_consistency_check:
        try:
            computed = compute_prompt_hash(grader_dir)

            try:
                cases = load_cases(fixtures_dir=str(_FIXTURES_DIR))
            except (FileNotFoundError, ValueError) as exc:
                print(f"Error loading cases for consistency check: {exc}", file=sys.stderr)
                return 2

            flip_rate = await run_full_consistency_check(
                cases=cases,
                grader_dir=grader_dir,
                grader_model=args.grader_model,
                max_retries=args.max_retries,
                verbose=args.verbose,
            )

            run_consistency_check(grader_dir, computed)
            record_flip_rate(grader_dir, flip_rate)

            print(f"Consistency check complete. Hash: {computed}, flip rate: {flip_rate:.1%}")
            return 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Consistency check failed")
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.accept_prompt:
        try:
            new_hash = accept_prompt(grader_dir)
            print(f"Prompt accepted. New hash: {new_hash}")
            return 0
        except (OSError, ValueError) as exc:
            logger.exception("Accept-prompt failed")
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    try:
        prompt_hash = check_prompt_version(grader_dir)
    except PromptDirtyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        thresholds_path = Path(args.thresholds)
        thresholds = json.loads(thresholds_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Error loading thresholds: {exc}", file=sys.stderr)
        return 2

    case_ids = None
    if args.cases != "all":
        case_ids = [cid.strip() for cid in args.cases.split(",")]

    try:
        cases = load_cases(
            fixtures_dir=str(_FIXTURES_DIR),
            case_ids=case_ids,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error loading cases: {exc}", file=sys.stderr)
        return 2

    container_name = args.container
    if container_name is None:
        try:
            container_name = await detect_container()
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    prompt_template = _load_grader_file(grader_dir / "prompt_template.txt")
    rubric = _load_grader_file(grader_dir / "rubric.md")
    few_shot_examples = _load_grader_json(grader_dir / "few_shot_examples.json")

    try:
        async with connect(container_name) as session:
            eval_run = await run_eval(
                cases,
                session,
                grader_model=args.grader_model,
                num_trials=args.trials,
                line_tolerance=args.line_tolerance,
                thresholds=thresholds,
                max_retries=args.max_retries,
                prompt_template=prompt_template,
                rubric=rubric,
                few_shot_examples=few_shot_examples,
                grader_prompt_version=prompt_hash,
                verbose=args.verbose,
                concurrency=args.concurrency,
            )
    except MCPAbortError as exc:
        print(f"Run aborted (non-retryable MCP error): {exc}", file=sys.stderr)
        return 2
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Harness run failed")
        print(f"Error running harness: {exc}", file=sys.stderr)
        return 2

    case_descriptions = {c.case_id: c.description for c in cases}
    case_expected_counts = {
        c.case_id: len(c.expected_findings) for c in cases
    }

    # When --ci --strict is active, recompute pass_fail under strict
    # semantics before rendering so the scorecard heading agrees with
    # the exit code (inconclusive metrics flip the run to FAIL).
    if args.ci and args.strict:
        eval_run.pass_fail = check_thresholds(
            eval_run.aggregate, thresholds, strict=True
        )

    scorecard = generate_scorecard(
        eval_run, thresholds,
        case_descriptions=case_descriptions,
        case_expected_counts=case_expected_counts,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"run-{timestamp_str}.json"
    md_path = output_dir / f"scorecard-{timestamp_str}.md"

    json_content = render_json(scorecard)
    md_content = render_markdown(scorecard)

    json_path.write_text(json_content)
    md_path.write_text(md_content)

    if args.baseline:
        try:
            baseline_data = json.loads(Path(args.baseline).read_text())
            baseline_run = EvalRun.model_validate(baseline_data)
            comparison = compare_runs(eval_run, baseline_run)
            scorecard.comparison = comparison
            md_content = render_markdown(scorecard)
            md_path.write_text(md_content)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Baseline comparison skipped: %s", exc)
            print(f"Warning: baseline comparison failed: {exc}", file=sys.stderr)

    if args.ci:
        print(md_content)
        _warn_if_inconclusive(eval_run, strict=args.strict)
        passes = check_thresholds(
            eval_run.aggregate, thresholds, strict=args.strict
        )
        return 0 if passes else 1

    return 0


def _warn_if_inconclusive(eval_run: EvalRun, strict: bool) -> None:
    """Emit a stderr warning when any metric is inconclusive.

    Makes the INCONCLUSIVE scorecard state visible to CI log scrapers
    without requiring them to parse the markdown. In non-strict mode the
    run still exits 0 if thresholds otherwise pass, but the warning
    records the corpus-maturity gap.
    """
    agg = eval_run.aggregate
    inconclusive: list[str] = []
    for name in (
        "precision",
        "recall",
        "severity_accuracy",
        "category_accuracy",
        "fp_rate",
        "snr",
        "rebuttal_accuracy",
    ):
        m = getattr(agg, name, None)
        if m is not None and m.method == CIMethod.WILSON_INSUFFICIENT_N:
            inconclusive.append(name)

    if not inconclusive:
        return

    mode = "strict: gating as FAIL" if strict else "non-strict: not gating"
    print(
        f"Warning: inconclusive metrics (insufficient sample size): "
        f"{', '.join(inconclusive)} — {mode}.",
        file=sys.stderr,
    )


def _load_grader_file(path: Path) -> str | None:
    """Load a grader prompt file, returning None if missing."""
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def _load_grader_json(path: Path) -> list[dict] | None:
    """Load grader JSON file (few-shot examples), returning None if missing."""
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def main() -> int:
    """Entry point called from __main__.py.

    Parses args, runs the async flow, returns exit code.
    """
    load_dotenv()
    args = parse_args()
    return asyncio.run(run(args))
