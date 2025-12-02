"""Local MCP Tools - Example local tools for the GPT Manager app.

This module defines local MCP tools that are registered with the MCP instance.
These tools can compose Frappe logic with remote MCP server calls.

Example usage in other modules:
    ```python
    from gpt_manager.gpt_manager.mcp import mcp

    @mcp.tool()
    def my_tool(param: str) -> str:
        '''My tool description.'''
        return f"Result: {param}"
    ```
"""

from __future__ import annotations

from typing import Any

from gpt_manager.gpt_manager.mcp import mcp


@mcp.tool()
def remember_customer(
    customer_name: str,
    customer_id: str,
    observations: list[str] | None = None,
) -> dict[str, Any]:
    """Remember customer information using the memory server.

    This tool stores customer information in the MCP memory server,
    creating a persistent memory of customer details.

    Args:
        customer_name: The name of the customer.
        customer_id: The unique identifier for the customer.
        observations: A list of observations about the customer.

    Returns:
        The result from the memory server.

    Example:
        >>> remember_customer(
        ...     customer_name="John Doe",
        ...     customer_id="CUST-001",
        ...     observations=["VIP customer", "Prefers email"]
        ... )
    """
    from gpt_manager.gpt_manager.mcp_helpers import call_memory

    # Default observations if none provided
    if observations is None:
        observations = [f'Customer ID: {customer_id}']

    try:
        result = call_memory(
            'create_entities',
            {
                'entities': [
                    {
                        'name': customer_id,
                        'entityType': 'customer',
                        'observations': [
                            f'Name: {customer_name}',
                            *observations,
                        ],
                    }
                ]
            },
        )
        return result
    except RuntimeError as e:
        return {'error': str(e), 'success': False}


@mcp.tool()
def get_mcp_status() -> dict[str, Any]:
    """Get the status of all configured MCP remote servers.

    Returns information about which remote servers are configured
    and whether they are running.

    Returns:
        A dictionary with server status information.
    """
    from gpt_manager.gpt_manager.mcp import mcp as mcp_instance

    status = {
        'local_tools': list(mcp_instance._tool_registry.keys()),
        'remote_servers': {},
        'remote_started': mcp_instance._remote_started,
    }

    for name, server in mcp_instance._remote_servers.items():
        status['remote_servers'][name] = {
            'command': server.config.command,
            'args': server.config.args,
            'namespace': server.config.namespace,
            'is_running': server.is_running(),
        }

    return status


@mcp.tool()
def ping_frappe() -> dict[str, Any]:
    """Test connectivity to Frappe.

    This is a simple test tool to verify that the MCP endpoint
    is working correctly with Frappe.

    Returns:
        A dictionary with connectivity status.
    """
    try:
        import frappe

        site_name = frappe.local.site if hasattr(frappe.local, 'site') else 'unknown'
        return {
            'status': 'connected',
            'site': site_name,
            'message': 'Frappe is available and MCP endpoint is working.',
        }
    except ImportError:
        return {
            'status': 'not_connected',
            'site': None,
            'message': 'Running outside of Frappe environment.',
        }
