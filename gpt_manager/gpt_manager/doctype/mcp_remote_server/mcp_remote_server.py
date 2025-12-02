"""MCP Remote Server - DocType for configuring remote MCP servers."""

from __future__ import annotations

import json
import re

# In Frappe environment, these will be available
# import frappe
# from frappe.model.document import Document


# Server name pattern: lowercase letters, numbers, hyphens, underscores, dots
SERVER_NAME_PATTERN = re.compile(r'^[a-z0-9\-_.]+$')


def validate_server_name(name: str) -> bool:
    """Validate that server_name is slug-like.

    Args:
        name: The server name to validate.

    Returns:
        True if valid, False otherwise.
    """
    return bool(SERVER_NAME_PATTERN.match(name))


def validate_args_json(args_json: str) -> list:
    """Validate that args_json parses into a Python list.

    Args:
        args_json: The JSON string to parse.

    Returns:
        The parsed list.

    Raises:
        ValueError: If args_json is not a valid JSON list.
    """
    try:
        args = json.loads(args_json or '[]')
        if not isinstance(args, list):
            raise ValueError('args_json must be a JSON list')
        return args
    except json.JSONDecodeError as e:
        raise ValueError(f'args_json is not valid JSON: {e}') from e


# Uncomment when running in Frappe environment
# class MCPRemoteServer(Document):
#     """DocType for configuring remote MCP servers.
#
#     This DocType stores configuration for remote MCP servers that will be
#     launched as subprocesses and communicate over stdio.
#
#     Fields:
#         server_name: Internal ID (required, unique, slug-like)
#         label: Human-readable label (required)
#         enabled: Whether the server is enabled (default: True)
#         command: Command to run (required, e.g., 'npx')
#         args_json: JSON list of arguments (required)
#         working_directory: Optional working directory
#         namespace: Optional namespace for tool names
#         auto_create_paths: Auto-create directories/files (default: True)
#         allowed_directories: Child table of allowed directories
#         memory_files: Child table of memory files
#         environment_variables: Child table of environment variables
#
#     Example Configuration for Memory Server:
#         server_name: "memory"
#         label: "MCP Memory Server"
#         enabled: True
#         command: "npx"
#         args_json: '["-y", "@modelcontextprotocol/server-memory"]'
#         namespace: "memory"
#         auto_create_paths: True
#
#         allowed_directories:
#             - path: "./sites/memory_data"
#
#         memory_files:
#             - path: "./sites/memory_data/memory.json"
#               env_var_name: "MEMORY_FILE"
#               auto_create: True
#
#     Example Configuration for Sequential-Thinking Server:
#         server_name: "sequential-thinking"
#         label: "Sequential Thinking Server"
#         enabled: True
#         command: "npx"
#         args_json: '["-y", "@modelcontextprotocol/server-sequential-thinking"]'
#         namespace: "seq"
#         auto_create_paths: True
#     """
#
#     def validate(self):
#         """Validate the document before saving."""
#         self._validate_server_name()
#         self._validate_args_json()
#
#     def _validate_server_name(self):
#         """Validate server_name is slug-like."""
#         if self.server_name and not validate_server_name(self.server_name):
#             frappe.throw(
#                 f"Server name '{self.server_name}' must be slug-like "
#                 "(lowercase letters, numbers, hyphens, underscores, dots)"
#             )
#
#     def _validate_args_json(self):
#         """Validate args_json parses into a Python list."""
#         try:
#             validate_args_json(self.args_json)
#         except ValueError as e:
#             frappe.throw(str(e))
