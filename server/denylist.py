"""Content denylist validation — T012.

Validates file paths against configurable glob patterns using fnmatch.
Per FR-006/FR-007: path-only matching, no content inspection.
"""

from __future__ import annotations

import os
from fnmatch import fnmatch


class ContentDenylist:
    """Validates file paths against configurable glob patterns."""

    DEFAULT_PATTERNS: list[str] = [
        ".env",
        "*.pem",
        "*.key",
        "*credentials*",
        "*secret*",
        "*.p12",
        "*.pfx",
    ]

    def __init__(self, patterns: list[str] | None = None) -> None:
        self._patterns = patterns if patterns is not None else self.DEFAULT_PATTERNS

    def check(self, file_paths: list[str]) -> list[str]:
        """Returns list of denied file paths. Empty list means all clear."""
        denied = []
        for path in file_paths:
            basename = os.path.basename(path)
            for pattern in self._patterns:
                if fnmatch(basename, pattern):
                    denied.append(path)
                    break
        return denied
