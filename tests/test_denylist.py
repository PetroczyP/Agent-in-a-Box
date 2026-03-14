"""Tests for content denylist — T008."""

from __future__ import annotations

import pytest

from server.denylist import ContentDenylist


class TestDefaultPatterns:
    def test_blocks_env_file(self):
        dl = ContentDenylist()
        denied = dl.check([".env"])
        assert ".env" in denied

    def test_blocks_pem_files(self):
        dl = ContentDenylist()
        denied = dl.check(["server.pem", "ca.pem"])
        assert "server.pem" in denied
        assert "ca.pem" in denied

    def test_blocks_key_files(self):
        dl = ContentDenylist()
        denied = dl.check(["private.key", "id_rsa.key"])
        assert "private.key" in denied

    def test_blocks_credentials_pattern(self):
        dl = ContentDenylist()
        denied = dl.check(["credentials.json", "my_credentials.yaml"])
        assert "credentials.json" in denied
        assert "my_credentials.yaml" in denied

    def test_blocks_secret_pattern(self):
        dl = ContentDenylist()
        denied = dl.check(["secret.txt", "app_secret_config.json"])
        assert "secret.txt" in denied
        assert "app_secret_config.json" in denied

    def test_blocks_p12_files(self):
        dl = ContentDenylist()
        denied = dl.check(["cert.p12"])
        assert "cert.p12" in denied

    def test_blocks_pfx_files(self):
        dl = ContentDenylist()
        denied = dl.check(["cert.pfx"])
        assert "cert.pfx" in denied


class TestAllowedFiles:
    def test_allows_python_files(self):
        dl = ContentDenylist()
        denied = dl.check(["main.py", "utils.py"])
        assert denied == []

    def test_allows_config_files(self):
        dl = ContentDenylist()
        denied = dl.check(["pyproject.toml", "Dockerfile"])
        assert denied == []

    def test_allows_markdown(self):
        dl = ContentDenylist()
        denied = dl.check(["README.md", "CHANGELOG.md"])
        assert denied == []


class TestCustomPatterns:
    def test_custom_pattern_overrides_defaults(self):
        dl = ContentDenylist(patterns=["*.log"])
        denied = dl.check(["app.log", ".env"])
        assert "app.log" in denied
        # .env is NOT denied because custom patterns replace defaults
        assert ".env" not in denied

    def test_empty_patterns(self):
        dl = ContentDenylist(patterns=[])
        denied = dl.check([".env", "private.key"])
        assert denied == []


class TestPathMatching:
    def test_matches_filename_only_not_content(self):
        """Denylist matches file paths, not file content."""
        dl = ContentDenylist()
        # A file named "normal.py" should pass even if its content has "secret"
        denied = dl.check(["normal.py"])
        assert denied == []

    def test_matches_basename_for_nested_paths(self):
        """Patterns should match against the basename of the path."""
        dl = ContentDenylist()
        denied = dl.check(["config/.env", "certs/server.pem"])
        assert "config/.env" in denied
        assert "certs/server.pem" in denied

    def test_empty_file_list(self):
        dl = ContentDenylist()
        denied = dl.check([])
        assert denied == []

    def test_mixed_allowed_and_denied(self):
        dl = ContentDenylist()
        files = ["main.py", ".env", "utils.py", "private.key"]
        denied = dl.check(files)
        assert set(denied) == {".env", "private.key"}
