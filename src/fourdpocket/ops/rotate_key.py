"""Secret key rotation operation.

Reads the current secret_key, generates a new one, moves the current to
secret_key.previous, and writes the new key.

NOTE: This command ONLY rotates the key on disk.
Wiring secret_key_previous into JWT decode is owned by the auth subsystem.
Until that is wired, old JWTs will be rejected immediately after rotation.
To preserve a grace period, set the env var FDP_AUTH__SECRET_KEY_PREVIOUS
to the OLD key value, then restart the server.
"""

import secrets
from pathlib import Path


def _resolve_key_dir() -> Path:
    """Resolve key directory using the same precedence as _get_or_create_secret_key."""
    import os

    explicit_dir = os.environ.get("FDP_AUTH__SECRET_KEY_DIR")
    if explicit_dir:
        return Path(explicit_dir)

    storage_base = os.environ.get("FDP_STORAGE__BASE_PATH")
    if storage_base:
        return Path(storage_base) / ".secret"

    return Path.home() / ".4dpocket"


def run_rotate_key(*, key_dir: Path, grace_days: int) -> None:
    """Rotate the secret key in *key_dir*.

    Steps:
      1. Read current secret_key (if it exists).
      2. Generate a new token_urlsafe(32) key.
      3. Write current → secret_key.previous.
      4. Write new → secret_key.
      5. Print instructions for the grace-period env var.

    Args:
        key_dir: Directory containing secret_key (and where .previous is written).
        grace_days: Number of days mentioned in the grace-period reminder.
    """
    key_dir.mkdir(parents=True, exist_ok=True)
    key_file = key_dir / "secret_key"
    prev_file = key_dir / "secret_key.previous"

    # Read current key (may not exist on first rotation)
    current_key: str = ""
    if key_file.exists():
        current_key = key_file.read_text().strip()

    # Generate new key
    new_key = secrets.token_urlsafe(32)

    # Move current → .previous
    if current_key:
        prev_file.write_text(current_key)
        prev_file.chmod(0o600)

    # Write new key
    key_file.write_text(new_key)
    key_file.chmod(0o600)

    print("Secret key rotated successfully.")
    print(f"  New key written to: {key_file}")
    if current_key:
        print(f"  Old key saved to:   {prev_file}")
    print()
    print("IMPORTANT — Grace-period instructions:")
    print("  Old JWTs will be INVALID immediately unless you configure the grace period.")
    print(f"  To allow existing sessions to remain valid for up to {grace_days} day(s):")
    print()
    print("  1. Set this environment variable before restarting:")
    print(f"       FDP_AUTH__SECRET_KEY_PREVIOUS={current_key or '<old-key>'}")
    print()
    print("  2. Or add to your .env file:")
    print(f"       FDP_AUTH__SECRET_KEY_PREVIOUS={current_key or '<old-key>'}")
    print()
    print("  3. Restart the server:  ./app.sh restart")
    print()
    print("  NOTE: JWT validation of the previous key requires the auth subsystem")
    print("  to be configured to accept FDP_AUTH__SECRET_KEY_PREVIOUS.")
    print("  Consult the auth documentation for your deployment.")
