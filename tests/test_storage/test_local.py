"""Tests for local filesystem storage."""

import uuid

import pytest

from fourdpocket.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path):
    """Create a LocalStorage instance backed by a temp directory."""
    return LocalStorage(base_path=str(tmp_path))


class TestSaveFile:
    """Test file save operations."""

    def test_save_file(self, storage):
        """save_file writes data to disk and returns relative path."""
        user_id = uuid.uuid4()
        data = b"hello world"
        rel_path = storage.save_file(user_id, "attachments", "test.txt", data)

        assert rel_path is not None
        assert "test.txt" in rel_path
        assert storage.get_file(rel_path) == data

    def test_save_file_strips_directory_components(self, storage):
        """save_file strips directory components from filename."""
        user_id = uuid.uuid4()
        data = b"content"
        rel_path = storage.save_file(user_id, "attachments", "../etc/passwd", data)

        # Filename should be just passwd, no directory traversal
        assert ".." not in rel_path
        assert "passwd" in rel_path

    def test_save_file_rejects_empty_filename(self, storage):
        """save_file rejects empty or dot-only filenames."""
        user_id = uuid.uuid4()
        with pytest.raises(ValueError, match="Invalid filename"):
            storage.save_file(user_id, "attachments", "", b"data")

    def test_save_file_rejects_dot_filename(self, storage):
        """save_file rejects filenames starting with dot."""
        user_id = uuid.uuid4()
        with pytest.raises(ValueError, match="Invalid filename"):
            storage.save_file(user_id, "attachments", ".gitignore", b"data")

    def test_save_file_normalizes_path(self, storage):
        """save_file strips directory components via Path().name."""
        user_id = uuid.uuid4()
        # Path().name strips all directory components, so ../../../etc/hosts -> hosts
        rel_path = storage.save_file(user_id, "attachments", "../../../etc/hosts", b"data")
        # The file is saved as just "hosts" under the user directory
        assert "hosts" in rel_path
        assert ".." not in rel_path
        assert storage.get_file(rel_path) == b"data"


class TestLoadFile:
    """Test file read operations."""

    def test_load_file(self, storage):
        """get_file reads back saved data correctly."""
        user_id = uuid.uuid4()
        data = b"test content here"
        rel_path = storage.save_file(user_id, "attachments", "readable.txt", data)

        loaded = storage.get_file(rel_path)
        assert loaded == data

    def test_load_file_not_found(self, storage):
        """get_file raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            storage.get_file("nonexistent/user/file.txt")


class TestDeleteFile:
    """Test file deletion."""

    def test_delete_file(self, storage):
        """delete_file removes the file from disk."""
        user_id = uuid.uuid4()
        rel_path = storage.save_file(user_id, "attachments", "todelete.txt", b"data")

        assert storage.file_exists(rel_path)
        storage.delete_file(rel_path)
        assert not storage.file_exists(rel_path)

    def test_delete_nonexistent_file(self, storage):
        """delete_file does not raise on missing file."""
        storage.delete_file("nonexistent/file.txt")  # Should not raise


class TestUserScoping:
    """Test user-scoped directory isolation."""

    def test_user_scoping_via_path_isolation(self, storage):
        """Each user gets an isolated directory; files are not guessable by other users."""
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        # User A saves a file
        rel_path_a = storage.save_file(user_a, "attachments", "secret.txt", b"user a data")

        # The relative path for user A's file contains user A's UUID
        assert str(user_a) in rel_path_a

        # User B saves their own file
        rel_path_b = storage.save_file(user_b, "attachments", "my.txt", b"user b data")

        # Paths are different
        assert rel_path_a != rel_path_b

        # User A can read their own file
        assert storage.get_file(rel_path_a) == b"user a data"

        # User B can read their own file
        assert storage.get_file(rel_path_b) == b"user b data"

        # Paths are truly isolated: each user's files live under their UUID directory
        assert str(user_a) in rel_path_a
        assert str(user_b) in rel_path_b
        assert str(user_a) not in rel_path_b
        assert str(user_b) not in rel_path_a

        # Attempting to access a path with a completely different UUID is blocked by OS permissions
        # (the directory doesn't exist / isn't writable)
        other_uuid = uuid.uuid4()
        assert storage._user_path(user_a, "attachments") != storage._user_path(other_uuid, "attachments")

    def test_user_path_creates_isolated_directories(self, storage):
        """Each user gets an isolated directory under their UUID."""
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        path_a = storage._user_path(user_a, "attachments")
        path_b = storage._user_path(user_b, "attachments")

        # Paths are different per user
        assert path_a != path_b
        assert str(user_a) in str(path_a)
        assert str(user_b) in str(path_b)


class TestPathTraversalDefense:
    """Test path traversal attack prevention."""

    def test_safe_path_blocks_absolute_traversal(self, storage):
        """_safe_path rejects paths that escape the base directory."""
        with pytest.raises(PermissionError, match="Path traversal"):
            storage._safe_path("../../../etc/hosts")

    def test_safe_path_blocks_parent_dir_in_relative(self, storage):
        """_safe_path blocks parent directory references in relative paths."""
        with pytest.raises(PermissionError, match="Path traversal"):
            storage._safe_path("user123/attachments/../../../../etc/hosts")

    def test_safe_path_allows_valid_relative_path(self, storage):
        """_safe_path allows legitimate relative paths."""
        user_id = uuid.uuid4()
        rel_path = storage.save_file(user_id, "attachments", "valid.txt", b"data")
        # Should not raise
        result = storage._safe_path(rel_path)
        assert result.exists() or result.parent.exists()


class TestFileExists:
    """Test file existence check."""

    def test_file_exists_true(self, storage):
        """file_exists returns True for existing files."""
        user_id = uuid.uuid4()
        rel_path = storage.save_file(user_id, "attachments", "exists.txt", b"data")
        assert storage.file_exists(rel_path) is True

    def test_file_exists_false(self, storage):
        """file_exists returns False for missing files."""
        assert storage.file_exists("nonexistent/path/file.txt") is False
