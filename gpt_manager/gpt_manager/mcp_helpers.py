"""MCP Helpers - Helper functions for calling remote MCP tools from Python.

This module provides convenience functions for calling tools on remote
MCP servers directly from Python code, without going through the HTTP endpoint.

Example usage:
    ```python
    from gpt_manager.gpt_manager.mcp_helpers import call_memory, call_seq

    # Call a tool on the memory server
    result = call_memory('create_entities', {
        'entities': [{'name': 'example', 'entityType': 'note', 'observations': ['test']}]
    })

    # Call a tool on the sequential-thinking server
    result = call_seq('think', {'thought': 'Analyzing the problem...'})
    ```
"""

from __future__ import annotations

from typing import Any


def call_memory(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a tool on the 'memory' remote MCP server directly from Python.

    This function provides a convenient way to call tools on the memory
    server without going through the HTTP endpoint.

    Args:
        tool_name: The raw remote tool name (e.g., "create_entities").
        arguments: Arguments to pass to the tool.

    Returns:
        The tool call result.

    Raises:
        RuntimeError: If the memory server is not configured.
        RemoteServerError: If the tool call fails.

    Example:
        ```python
        result = call_memory('create_entities', {
            'entities': [
                {
                    'name': 'customer_123',
                    'entityType': 'customer',
                    'observations': ['VIP customer', 'Prefers email contact']
                }
            ]
        })
        ```
    """
    from gpt_manager.gpt_manager.mcp import mcp

    mcp.start_remote_servers()

    server = mcp._remote_servers.get('memory')
    if not server:
        raise RuntimeError(
            "Memory server not configured. "
            "Please add an 'MCP Remote Server' record with server_name='memory'."
        )

    return server.call_tool(tool_name, arguments)


def call_seq(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a tool on the 'sequential-thinking' remote MCP server directly.

    This function provides a convenient way to call tools on the
    sequential-thinking server without going through the HTTP endpoint.

    Args:
        tool_name: The raw remote tool name (e.g., "think").
        arguments: Arguments to pass to the tool.

    Returns:
        The tool call result.

    Raises:
        RuntimeError: If the sequential-thinking server is not configured.
        RemoteServerError: If the tool call fails.

    Example:
        ```python
        result = call_seq('think', {
            'thought': 'I need to analyze this problem step by step...'
        })
        ```
    """
    from gpt_manager.gpt_manager.mcp import mcp

    mcp.start_remote_servers()

    server = mcp._remote_servers.get('sequential-thinking')
    if not server:
        raise RuntimeError(
            "Sequential-thinking server not configured. "
            "Please add an 'MCP Remote Server' record with "
            "server_name='sequential-thinking'."
        )

    return server.call_tool(tool_name, arguments)


def call_remote(
    server_name: str, tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Call a tool on any configured remote MCP server.

    This is a generic helper for calling tools on any remote server
    by its server_name.

    Args:
        server_name: The server_name of the remote server.
        tool_name: The raw remote tool name.
        arguments: Arguments to pass to the tool.

    Returns:
        The tool call result.

    Raises:
        RuntimeError: If the server is not configured.
        RemoteServerError: If the tool call fails.

    Example:
        ```python
        result = call_remote('memory', 'create_entities', {...})
        ```
    """
    from gpt_manager.gpt_manager.mcp import mcp

    mcp.start_remote_servers()

    server = mcp._remote_servers.get(server_name)
    if not server:
        raise RuntimeError(
            f"Remote server '{server_name}' not configured. "
            f"Please add an 'MCP Remote Server' record with "
            f"server_name='{server_name}'."
        )

    return server.call_tool(tool_name, arguments)
