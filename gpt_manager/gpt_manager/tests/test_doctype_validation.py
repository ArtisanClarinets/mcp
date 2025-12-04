"""Tests for MCP Remote Server DocType validation."""

from __future__ import annotations

import unittest

from gpt_manager.gpt_manager.doctype.mcp_remote_server.mcp_remote_server import (
    validate_args_json,
    validate_server_name,
)


class TestServerNameValidation(unittest.TestCase):
    """Test server name validation."""

    def test_valid_server_names(self):
        """Test that valid server names pass validation."""
        valid_names = [
            'memory',
            'sequential-thinking',
            'my_server',
            'server.name',
            'server123',
            'my-cool-server_v2.0',
        ]
        for name in valid_names:
            self.assertTrue(
                validate_server_name(name), f"Expected '{name}' to be valid"
            )

    def test_invalid_server_names(self):
        """Test that invalid server names fail validation."""
        invalid_names = [
            'Invalid Name',
            'Server With Spaces',
            'UPPERCASE',
            'special@char',
            'server/name',
            '',
        ]
        for name in invalid_names:
            self.assertFalse(
                validate_server_name(name), f"Expected '{name}' to be invalid"
            )


class TestArgsJsonValidation(unittest.TestCase):
    """Test args_json validation."""

    def test_valid_args_json(self):
        """Test that valid JSON lists pass validation."""
        valid_inputs = [
            ('[]', []),
            ('["-y"]', ['-y']),
            ('["-y", "@modelcontextprotocol/server-memory"]', ['-y', '@modelcontextprotocol/server-memory']),
            ('["arg1", "arg2", "arg3"]', ['arg1', 'arg2', 'arg3']),
        ]
        for json_str, expected in valid_inputs:
            result = validate_args_json(json_str)
            self.assertEqual(result, expected)

    def test_empty_args_json(self):
        """Test that empty or None args_json returns empty list."""
        self.assertEqual(validate_args_json(''), [])
        self.assertEqual(validate_args_json(None), [])

    def test_invalid_args_json_not_list(self):
        """Test that non-list JSON raises ValueError."""
        invalid_inputs = [
            '{"key": "value"}',
            '"string"',
            '123',
            'null',
        ]
        for json_str in invalid_inputs:
            with self.assertRaises(ValueError) as ctx:
                validate_args_json(json_str)
            self.assertIn('must be a JSON list', str(ctx.exception))

    def test_invalid_args_json_syntax(self):
        """Test that invalid JSON syntax raises ValueError."""
        invalid_inputs = [
            '[missing quote"]',
            '{not: valid}',
            '[1, 2, 3',
        ]
        for json_str in invalid_inputs:
            with self.assertRaises(ValueError) as ctx:
                validate_args_json(json_str)
            self.assertIn('not valid JSON', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
