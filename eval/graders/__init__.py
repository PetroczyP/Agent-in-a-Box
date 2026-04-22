"""Grader package: Tier 1 fingerprint + Tier 2 LLM-as-Judge."""

import os

DEFAULT_GRADER_MODEL = os.environ.get("GRADER_MODEL", "claude-sonnet-4-6")


class MissingGraderCredentialError(Exception):
    """Raised when the Tier 2 grader cannot authenticate.

    Treated as a fatal harness configuration error — the pipeline must not
    downgrade this to a per-finding ``GRADING_ERROR`` because every
    unmatched finding would then silently skip scoring. The CLI contract
    (eval-cli.md:84-90) requires exit code 2 when the required grader is
    unavailable.
    """
