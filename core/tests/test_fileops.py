"""
test_fileops.py - Tests for ayuna_core.fileops module.
"""

import pytest

from ayuna_core.basetypes import AyunaError
from ayuna_core.fileops import (
    delete_dir,
    delete_file,
    dir_exists,
    dir_paths_from_dir,
    file_exists,
    file_paths_from_dir,
    is_dir_readable,
    is_dir_writable,
    is_file_readable,
    is_file_writable,
    read_bytes,
    read_json,
    read_text,
    read_toml,
    read_yaml,
    recursive_dir_content,
    total_files_in_dir,
    write_bytes,
    write_json,
    write_text,
)


class TestFileExists:
    """Tests for file_exists function."""

    def test_existing_file(self, sample_text_file):
        """Should return True for existing file."""
        assert file_exists(str(sample_text_file)) is True

    def test_nonexistent_file(self, temp_dir):
        """Should return False for nonexistent file."""
        assert file_exists(str(temp_dir / "nonexistent.txt")) is False

    def test_directory_returns_false(self, temp_dir):
        """Should return False for directory path."""
        assert file_exists(str(temp_dir)) is False


class TestDirExists:
    """Tests for dir_exists function."""

    def test_existing_dir(self, temp_dir):
        """Should return True for existing directory."""
        assert dir_exists(str(temp_dir)) is True

    def test_nonexistent_dir(self, temp_dir):
        """Should return False for nonexistent directory."""
        assert dir_exists(str(temp_dir / "nonexistent")) is False

    def test_file_returns_false(self, sample_text_file):
        """Should return False for file path."""
        assert dir_exists(str(sample_text_file)) is False


class TestIsFileReadable:
    """Tests for is_file_readable function."""

    def test_readable_file(self, sample_text_file):
        """Should return True for readable file."""
        assert is_file_readable(str(sample_text_file)) is True

    def test_nonexistent_file(self, temp_dir):
        """Should return False for nonexistent file."""
        assert is_file_readable(str(temp_dir / "nonexistent.txt")) is False

    def test_empty_path(self):
        """Should return False for empty path."""
        assert is_file_readable("") is False

    def test_directory(self, temp_dir):
        """Should return False for directory."""
        assert is_file_readable(str(temp_dir)) is False


class TestIsFileWritable:
    """Tests for is_file_writable function."""

    def test_writable_file(self, sample_text_file):
        """Should return True for writable file."""
        assert is_file_writable(str(sample_text_file)) is True

    def test_nonexistent_file_no_check(self, temp_dir):
        """Should return False for nonexistent without check_creatable."""
        assert is_file_writable(str(temp_dir / "new.txt")) is False

    def test_nonexistent_file_with_check(self, temp_dir):
        """Should return True if parent dir is writable."""
        assert is_file_writable(str(temp_dir / "new.txt"), check_creatable=True) is True

    def test_empty_path(self):
        """Should return False for empty path."""
        assert is_file_writable("") is False


class TestIsDirReadable:
    """Tests for is_dir_readable function."""

    def test_readable_dir(self, temp_dir):
        """Should return True for readable directory."""
        assert is_dir_readable(str(temp_dir)) is True

    def test_nonexistent_dir(self, temp_dir):
        """Should return False for nonexistent directory."""
        assert is_dir_readable(str(temp_dir / "nonexistent")) is False

    def test_empty_path(self):
        """Should return False for empty path."""
        assert is_dir_readable("") is False


class TestIsDirWritable:
    """Tests for is_dir_writable function."""

    def test_writable_dir(self, temp_dir):
        """Should return True for writable directory."""
        assert is_dir_writable(str(temp_dir)) is True

    def test_nonexistent_dir_no_check(self, temp_dir):
        """Should return False for nonexistent without check_creatable."""
        assert is_dir_writable(str(temp_dir / "newdir")) is False

    def test_nonexistent_dir_with_check(self, temp_dir):
        """Should return True if parent dir is writable."""
        assert is_dir_writable(str(temp_dir / "newdir"), check_creatable=True) is True


class TestRecursiveDirContent:
    """Tests for recursive_dir_content function."""

    def test_scan_directory(self, temp_dir):
        """Should scan directory recursively."""
        # Create some files and subdirs
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.py").write_text("content2")
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3")

        dirs, files = recursive_dir_content(base_dir=str(temp_dir))

        assert len(files) == 3
        assert len(dirs) >= 1

    def test_filter_by_extension(self, temp_dir):
        """Should filter by extension."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.py").write_text("content2")

        _, files = recursive_dir_content(base_dir=str(temp_dir), extensions=[".txt"])

        assert len(files) == 1
        assert files[0].endswith(".txt")


class TestTotalFilesInDir:
    """Tests for total_files_in_dir function."""

    def test_count_files(self, temp_dir):
        """Should count files in directory."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")

        count = total_files_in_dir(base_dir=str(temp_dir))
        assert count == 2

    def test_count_with_extension_filter(self, temp_dir):
        """Should count only files with specified extension."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.py").write_text("content2")

        count = total_files_in_dir(base_dir=str(temp_dir), extensions=[".txt"])
        assert count == 1

    def test_unreadable_dir_returns_negative(self):
        """Should return -1 for unreadable directory."""
        count = total_files_in_dir(base_dir="/nonexistent/path")
        assert count == -1


class TestFilePathsFromDir:
    """Tests for file_paths_from_dir generator."""

    def test_yields_file_paths(self, temp_dir):
        """Should yield file paths."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")

        paths = list(file_paths_from_dir(base_dir=str(temp_dir), extensions=[".txt"]))

        assert len(paths) == 2
        assert all(p.endswith(".txt") for p in paths)

    def test_with_pattern_filter(self, temp_dir):
        """Should filter by regex pattern."""
        (temp_dir / "test_file.txt").write_text("content1")
        (temp_dir / "other_file.txt").write_text("content2")

        paths = list(
            file_paths_from_dir(
                base_dir=str(temp_dir),
                extensions=[".txt"],
                file_pattern="test_",
            )
        )

        assert len(paths) == 1
        assert "test_file" in paths[0]


class TestDirPathsFromDir:
    """Tests for dir_paths_from_dir generator."""

    def test_yields_dir_paths(self, temp_dir):
        """Should yield directory paths."""
        (temp_dir / "subdir1").mkdir()
        (temp_dir / "subdir2").mkdir()

        paths = list(dir_paths_from_dir(base_dir=str(temp_dir)))

        assert len(paths) == 2


class TestReadBytes:
    """Tests for read_bytes function."""

    def test_read_bytes(self, temp_dir):
        """Should read file as bytes."""
        file_path = temp_dir / "binary.bin"
        content = b"\x00\x01\x02\x03"
        file_path.write_bytes(content)

        result = read_bytes(str(file_path))
        assert result == content

    def test_read_nonexistent_raises(self, temp_dir):
        """Should raise AyunaError for nonexistent file."""
        with pytest.raises(AyunaError):
            read_bytes(str(temp_dir / "nonexistent.bin"))


class TestReadText:
    """Tests for read_text function."""

    def test_read_text(self, sample_text_file):
        """Should read file as text."""
        result = read_text(str(sample_text_file))
        assert "Hello, World!" in result

    def test_read_nonexistent_raises(self, temp_dir):
        """Should raise AyunaError for nonexistent file."""
        with pytest.raises(AyunaError):
            read_text(str(temp_dir / "nonexistent.txt"))


class TestReadJson:
    """Tests for read_json function."""

    def test_read_json(self, sample_json_file):
        """Should read and parse JSON file."""
        result = read_json(str(sample_json_file))
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_read_nonexistent_raises(self, temp_dir):
        """Should raise AyunaError for nonexistent file."""
        with pytest.raises(AyunaError):
            read_json(str(temp_dir / "nonexistent.json"))


class TestReadYaml:
    """Tests for read_yaml function."""

    def test_read_yaml(self, sample_yaml_file):
        """Should read and parse YAML file."""
        result = read_yaml(str(sample_yaml_file))
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_read_nonexistent_raises(self, temp_dir):
        """Should raise AyunaError for nonexistent file."""
        with pytest.raises(AyunaError):
            read_yaml(str(temp_dir / "nonexistent.yaml"))


class TestReadToml:
    """Tests for read_toml function."""

    def test_read_toml(self, sample_toml_file):
        """Should read and parse TOML file."""
        result = read_toml(str(sample_toml_file))
        assert result["section"]["key"] == "value"
        assert result["section"]["number"] == 42

    def test_read_nonexistent_raises(self, temp_dir):
        """Should raise AyunaError for nonexistent file."""
        with pytest.raises(AyunaError):
            read_toml(str(temp_dir / "nonexistent.toml"))


class TestWriteBytes:
    """Tests for write_bytes function."""

    def test_write_bytes(self, temp_dir):
        """Should write bytes to file."""
        file_path = temp_dir / "output.bin"
        content = b"\x00\x01\x02\x03"

        write_bytes(str(file_path), content, overwrite=True)

        assert file_path.read_bytes() == content

    def test_write_no_overwrite(self, temp_dir):
        """Should not overwrite existing file without flag."""
        file_path = temp_dir / "existing.bin"
        file_path.write_bytes(b"original")

        result = write_bytes(str(file_path), b"new", overwrite=False)

        assert result == -1
        assert file_path.read_bytes() == b"original"


class TestWriteText:
    """Tests for write_text function."""

    def test_write_text(self, temp_dir):
        """Should write text to file."""
        file_path = temp_dir / "output.txt"

        write_text(str(file_path), "Hello, World!", overwrite=True)

        assert file_path.read_text() == "Hello, World!"


class TestWriteJson:
    """Tests for write_json function."""

    def test_write_json(self, temp_dir):
        """Should write JSON to file."""
        file_path = temp_dir / "output.json"
        data = {"key": "value", "number": 42}

        write_json(str(file_path), data, overwrite=True)

        import json

        result = json.loads(file_path.read_text())
        assert result["key"] == "value"


class TestDeleteFile:
    """Tests for delete_file function."""

    def test_delete_file(self, temp_dir):
        """Should delete existing file."""
        file_path = temp_dir / "to_delete.txt"
        file_path.write_text("content")

        delete_file(str(file_path))

        assert not file_path.exists()

    def test_delete_nonexistent_raises(self, temp_dir):
        """Should raise AyunaError for nonexistent file."""
        with pytest.raises(AyunaError):
            delete_file(str(temp_dir / "nonexistent.txt"))


class TestDeleteDir:
    """Tests for delete_dir function."""

    def test_delete_empty_dir(self, temp_dir):
        """Should delete empty directory."""
        dir_path = temp_dir / "to_delete"
        dir_path.mkdir()

        delete_dir(str(dir_path))

        assert not dir_path.exists()

    def test_delete_nonexistent_raises(self, temp_dir):
        """Should raise AyunaError for nonexistent directory."""
        with pytest.raises(AyunaError):
            delete_dir(str(temp_dir / "nonexistent"))
