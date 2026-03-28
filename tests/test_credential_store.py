"""Tests for CredentialStore — T006 (RED).

Covers: store(), load(), delete(), has_stored_credential(), get_metadata(),
update_last_validated(), atomic writes, key loss handling.
Per contract: specs/002-credential-setup/contracts/credential-store.md
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from server.credential_store import CredentialMetadata, CredentialStore


@pytest.fixture
def data_dir(tmp_path):
    """Provide a temp directory simulating /data/."""
    return str(tmp_path)


@pytest.fixture
def store(data_dir):
    return CredentialStore(data_dir=data_dir)


class TestStore:
    def test_store_creates_fernet_key(self, store, data_dir):
        """First store() creates .fernet_key file."""
        store.store("github_pat_test1234")
        key_path = os.path.join(data_dir, ".fernet_key")
        assert os.path.exists(key_path)

    def test_store_creates_encrypted_file(self, store, data_dir):
        """store() creates credentials.enc."""
        store.store("github_pat_test1234")
        enc_path = os.path.join(data_dir, "credentials.enc")
        assert os.path.exists(enc_path)
        # Encrypted file should NOT contain plaintext token
        with open(enc_path, "rb") as f:
            content = f.read()
        assert b"github_pat_test1234" not in content

    def test_store_creates_metadata(self, store, data_dir):
        """store() creates credential_meta.json with timestamps."""
        store.store("github_pat_test1234")
        meta_path = os.path.join(data_dir, "credential_meta.json")
        assert os.path.exists(meta_path)
        with open(meta_path) as f:
            meta = json.load(f)
        assert "created_at" in meta
        assert "last_validated_at" in meta

    def test_store_reuses_existing_key(self, store, data_dir):
        """Second store() reuses existing .fernet_key."""
        store.store("github_pat_first")
        key_path = os.path.join(data_dir, ".fernet_key")
        with open(key_path, "rb") as f:
            key1 = f.read()
        store.store("github_pat_second")
        with open(key_path, "rb") as f:
            key2 = f.read()
        assert key1 == key2

    def test_store_key_permissions(self, store, data_dir):
        """Fernet key file should have restrictive permissions (chmod 600)."""
        store.store("github_pat_test1234")
        key_path = os.path.join(data_dir, ".fernet_key")
        mode = os.stat(key_path).st_mode & 0o777
        assert mode == 0o600


class TestLoad:
    def test_load_decrypts_stored_token(self, store):
        """load() returns the original plaintext token."""
        store.store("github_pat_my_secret_token")
        loaded = store.load()
        assert loaded == "github_pat_my_secret_token"

    def test_load_returns_none_on_missing_file(self, store):
        """load() returns None when no credentials.enc exists."""
        assert store.load() is None

    def test_load_returns_none_on_missing_key(self, store, data_dir):
        """FR-001: Key loss → load() returns None (AC-9)."""
        store.store("github_pat_test1234")
        # Delete the key file
        os.remove(os.path.join(data_dir, ".fernet_key"))
        assert store.load() is None

    def test_load_returns_none_on_corrupted_file(self, store, data_dir):
        """Decryption failure → load() returns None."""
        store.store("github_pat_test1234")
        enc_path = os.path.join(data_dir, "credentials.enc")
        with open(enc_path, "wb") as f:
            f.write(b"corrupted data")
        assert store.load() is None


class TestDelete:
    def test_delete_removes_credential_files(self, store, data_dir):
        """delete() removes credentials.enc and credential_meta.json."""
        store.store("github_pat_test1234")
        store.delete()
        assert not os.path.exists(os.path.join(data_dir, "credentials.enc"))
        assert not os.path.exists(os.path.join(data_dir, "credential_meta.json"))

    def test_delete_keeps_fernet_key(self, store, data_dir):
        """delete() does NOT remove .fernet_key."""
        store.store("github_pat_test1234")
        store.delete()
        assert os.path.exists(os.path.join(data_dir, ".fernet_key"))

    def test_delete_noop_when_no_credential(self, store):
        """delete() does not raise when nothing to delete."""
        store.delete()  # Should not raise


class TestHasStoredCredential:
    def test_returns_true_when_stored(self, store):
        store.store("github_pat_test1234")
        assert store.has_stored_credential() is True

    def test_returns_false_when_empty(self, store):
        assert store.has_stored_credential() is False

    def test_returns_false_after_delete(self, store):
        store.store("github_pat_test1234")
        store.delete()
        assert store.has_stored_credential() is False


class TestGetMetadata:
    def test_returns_metadata_after_store(self, store):
        store.store("github_pat_test1234")
        meta = store.get_metadata()
        assert meta is not None
        assert isinstance(meta, CredentialMetadata)
        assert isinstance(meta.created_at, datetime)
        # last_validated_at is None until update_last_validated() is called
        assert meta.last_validated_at is None

    def test_returns_none_when_no_metadata(self, store):
        assert store.get_metadata() is None

    def test_returns_none_with_missing_keys(self, store, data_dir):
        """get_metadata returns None when JSON has missing keys."""
        store.store("github_pat_test1234")
        meta_path = os.path.join(data_dir, "credential_meta.json")
        with open(meta_path, "w") as f:
            json.dump({"some_other_key": "value"}, f)
        assert store.get_metadata() is None


class TestUpdateLastValidated:
    def test_updates_last_validated_at(self, store):
        store.store("github_pat_test1234")
        meta_before = store.get_metadata()
        assert meta_before is not None

        assert meta_before.last_validated_at is None

        store.update_last_validated()
        meta_after = store.get_metadata()
        assert meta_after is not None
        assert isinstance(meta_after.last_validated_at, datetime)

    def test_noop_when_no_metadata(self, store):
        """update_last_validated with no metadata file is a no-op."""
        store.update_last_validated()  # Should not raise
        assert store.get_metadata() is None

    def test_noop_when_metadata_corrupted(self, store, data_dir):
        """update_last_validated is a no-op when metadata is corrupted."""
        store.store("github_pat_test1234")
        meta_path = os.path.join(data_dir, "credential_meta.json")
        with open(meta_path, "w") as f:
            f.write("not valid json")
        store.update_last_validated()  # Should not raise


class TestLoadIOErrorPropagation:
    """H-1: File I/O errors must propagate, not silently return None."""

    def test_load_propagates_permission_error(self, store, data_dir):
        """PermissionError on credentials.enc must raise, not return None."""
        store.store("github_pat_test1234")
        enc_path = os.path.join(data_dir, "credentials.enc")
        os.chmod(enc_path, 0o000)
        try:
            with pytest.raises(PermissionError):
                store.load()
        finally:
            os.chmod(enc_path, 0o644)

    def test_load_propagates_key_permission_error(self, store, data_dir):
        """PermissionError on .fernet_key must raise, not return None."""
        store.store("github_pat_test1234")
        key_path = os.path.join(data_dir, ".fernet_key")
        os.chmod(key_path, 0o000)
        try:
            with pytest.raises(PermissionError):
                store.load()
        finally:
            os.chmod(key_path, 0o600)


class TestCorruptedMetadata:
    """C-1: _read_meta_dict handles corrupted JSON gracefully."""

    def test_read_meta_dict_with_corrupted_json(self, store, data_dir):
        """_read_meta_dict returns {} when credential_meta.json contains invalid JSON."""
        meta_path = os.path.join(data_dir, "credential_meta.json")
        with open(meta_path, "w") as f:
            f.write("{invalid json content!!!")
        assert store._read_meta_dict() == {}

    def test_store_succeeds_with_corrupted_metadata(self, store, data_dir):
        """store() succeeds even when existing metadata is corrupted."""
        # First store to create key and files
        store.store("github_pat_first")
        # Corrupt the metadata file
        meta_path = os.path.join(data_dir, "credential_meta.json")
        with open(meta_path, "w") as f:
            f.write("not valid json")
        # store() should still succeed — corrupted meta treated as empty
        store.store("github_pat_second")
        assert store.load() == "github_pat_second"
        # Metadata should be valid again after re-store
        meta = store.get_metadata()
        assert meta is not None

    def test_get_metadata_returns_none_with_malformed_dates(self, store, data_dir):
        """get_metadata() returns None when date strings are malformed."""
        meta_path = os.path.join(data_dir, "credential_meta.json")
        with open(meta_path, "w") as f:
            json.dump({"created_at": "not-a-date", "last_validated_at": "also-bad"}, f)
        assert store.get_metadata() is None


class TestAtomicWrites:
    def test_store_uses_atomic_writes(self, store, data_dir):
        """Verify store() uses os.replace() — encrypted file is valid after store."""
        store.store("github_pat_first")
        store.store("github_pat_second")
        # Both stores should produce valid state
        assert store.load() == "github_pat_second"
