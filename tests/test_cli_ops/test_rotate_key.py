"""Tests for auth rotate-key CLI command.

Regression tests for: new key written, old key moved to .previous,
idempotent on re-run (new .previous is written).
"""

from pathlib import Path

import pytest

from fourdpocket import cli


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def key_env(tmp_path):
    """Create a temp key directory with an existing secret_key."""
    key_dir = tmp_path / ".secret"
    key_dir.mkdir()
    key_file = key_dir / "secret_key"
    key_file.write_text("original-secret-key-value")
    key_file.chmod(0o600)
    return {"key_dir": key_dir, "key_file": key_file}


# ─── Rotate key: happy path ───────────────────────────────────────────────────


class TestRotateKeyHappyPath:
    def test_new_key_written(self, key_env):
        """After rotation, secret_key contains a new value."""
        from fourdpocket.ops import rotate_key as rk_mod

        rk_mod.run_rotate_key(key_dir=key_env["key_dir"], grace_days=7)

        new_key = key_env["key_file"].read_text().strip()
        assert new_key != "original-secret-key-value"
        assert len(new_key) >= 20  # token_urlsafe(32) is 43 chars

    def test_old_key_moved_to_previous(self, key_env):
        """After rotation, secret_key.previous contains the original key."""
        from fourdpocket.ops import rotate_key as rk_mod

        rk_mod.run_rotate_key(key_dir=key_env["key_dir"], grace_days=7)

        prev_file = key_env["key_dir"] / "secret_key.previous"
        assert prev_file.exists(), "secret_key.previous not created"
        assert prev_file.read_text().strip() == "original-secret-key-value"

    def test_prints_env_var_reminder(self, key_env, capsys):
        """Rotation output mentions the FDP_AUTH__SECRET_KEY_PREVIOUS env var."""
        from fourdpocket.ops import rotate_key as rk_mod

        rk_mod.run_rotate_key(key_dir=key_env["key_dir"], grace_days=7)

        captured = capsys.readouterr()
        assert "FDP_AUTH__SECRET_KEY_PREVIOUS" in captured.out

    def test_grace_days_mentioned_in_output(self, key_env, capsys):
        """Rotation output mentions the grace period duration."""
        from fourdpocket.ops import rotate_key as rk_mod

        rk_mod.run_rotate_key(key_dir=key_env["key_dir"], grace_days=14)

        captured = capsys.readouterr()
        assert "14" in captured.out


# ─── Rotate key: no existing key ──────────────────────────────────────────────


class TestRotateKeyNoExistingKey:
    def test_creates_key_if_none_exists(self, tmp_path):
        """If no secret_key exists, rotation should create one (treating empty as current)."""
        from fourdpocket.ops import rotate_key as rk_mod

        key_dir = tmp_path / ".secret"
        key_dir.mkdir()

        rk_mod.run_rotate_key(key_dir=key_dir, grace_days=7)

        key_file = key_dir / "secret_key"
        assert key_file.exists()
        assert len(key_file.read_text().strip()) >= 20


# ─── Rotate key: idempotent on re-run ─────────────────────────────────────────


class TestRotateKeyIdempotent:
    def test_second_rotation_updates_previous(self, key_env):
        """Running rotate-key twice: .previous should reflect the intermediate key."""
        from fourdpocket.ops import rotate_key as rk_mod

        rk_mod.run_rotate_key(key_dir=key_env["key_dir"], grace_days=7)
        intermediate_key = key_env["key_file"].read_text().strip()

        rk_mod.run_rotate_key(key_dir=key_env["key_dir"], grace_days=7)
        second_key = key_env["key_file"].read_text().strip()

        prev_file = key_env["key_dir"] / "secret_key.previous"
        assert prev_file.read_text().strip() == intermediate_key
        assert second_key != intermediate_key
