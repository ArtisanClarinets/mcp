"""Tests for MCP Loader."""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import dataclass

from gpt_manager.gpt_manager.mcp_loader import (
    _ensure_dirs_and_files,
    reset_configuration,
)


@dataclass
class MockRow:
    """Mock row for child tables."""

    path: str = ''
    env_var_name: str | None = None
    auto_create: bool = True
    description: str = ''


@dataclass
class MockDoc:
    """Mock document for MCP Remote Server."""

    server_name: str = 'test'
    auto_create_paths: bool = True
    allowed_directories: list = None
    memory_files: list = None
    environment_variables: list = None

    def __post_init__(self):
        if self.allowed_directories is None:
            self.allowed_directories = []
        if self.memory_files is None:
            self.memory_files = []
        if self.environment_variables is None:
            self.environment_variables = []


class TestEnsureDirsAndFiles(unittest.TestCase):
    """Test _ensure_dirs_and_files function."""

    def test_empty_doc(self):
        """Test with no directories or files."""
        doc = MockDoc()
        result = _ensure_dirs_and_files(doc)
        self.assertEqual(result, {})

    def test_allowed_directories_creates_dirs(self):
        """Test that allowed directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, 'subdir')
            doc = MockDoc(
                allowed_directories=[MockRow(path=test_path)],
            )

            result = _ensure_dirs_and_files(doc)

            self.assertTrue(os.path.isdir(test_path))
            self.assertIn('ALLOWED_DIRECTORIES', result)
            self.assertEqual(result['ALLOWED_DIRECTORIES'], test_path)

    def test_multiple_allowed_directories(self):
        """Test that multiple directories are joined with os.pathsep."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, 'dir1')
            path2 = os.path.join(tmpdir, 'dir2')
            doc = MockDoc(
                allowed_directories=[MockRow(path=path1), MockRow(path=path2)],
            )

            result = _ensure_dirs_and_files(doc)

            self.assertTrue(os.path.isdir(path1))
            self.assertTrue(os.path.isdir(path2))
            self.assertIn('ALLOWED_DIRECTORIES', result)
            self.assertIn(os.pathsep, result['ALLOWED_DIRECTORIES'])

    def test_memory_file_creates_file(self):
        """Test that memory files are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, 'subdir', 'memory.json')
            doc = MockDoc(
                memory_files=[MockRow(path=test_path)],
            )

            _ensure_dirs_and_files(doc)

            self.assertTrue(os.path.isfile(test_path))

    def test_memory_file_with_env_var(self):
        """Test that memory file env var is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, 'memory.json')
            doc = MockDoc(
                memory_files=[MockRow(path=test_path, env_var_name='MEMORY_FILE')],
            )

            result = _ensure_dirs_and_files(doc)

            self.assertIn('MEMORY_FILE', result)
            self.assertEqual(result['MEMORY_FILE'], os.path.abspath(test_path))

    def test_auto_create_paths_disabled(self):
        """Test that paths are not created when auto_create_paths is False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, 'nonexistent', 'subdir')
            doc = MockDoc(
                auto_create_paths=False,
                allowed_directories=[MockRow(path=test_path)],
            )

            _ensure_dirs_and_files(doc)

            # Directory should not be created
            self.assertFalse(os.path.isdir(test_path))


class TestResetConfiguration(unittest.TestCase):
    """Test reset_configuration function."""

    def test_reset_configuration(self):
        """Test that reset_configuration clears the configured flag."""
        import gpt_manager.gpt_manager.mcp_loader as loader

        # Set configured to True
        loader._configured = True
        self.assertTrue(loader._configured)

        # Reset
        reset_configuration()

        # Should be False now
        self.assertFalse(loader._configured)


if __name__ == '__main__':
    unittest.main()
