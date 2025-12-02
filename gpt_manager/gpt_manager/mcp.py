"""MCP Entrypoint - Main MCP endpoint for the GPT Manager app.

This module provides the central MCP endpoint that acts as an "MCP hub",
hosting both local tools and proxying to remote MCP servers.

The endpoint is accessible at:
    /api/method/gpt_manager.gpt_manager.mcp.handle_mcp

Example usage:
    ```python
    # Import the MCP instance to register tools
    from gpt_manager.gpt_manager.mcp import mcp

    @mcp.tool()
    def my_custom_tool(param: str) -> str:
        '''My custom tool description.'''
        return f"Result: {param}"
    ```
"""

from __future__ import annotations

from frappe_mcp import MCP

# Create the central MCP instance
mcp = MCP(name='gpt-manager-mcp-host')


# Import local tools so they register via @mcp.tool()
# Note: The tools module imports are done at runtime inside handle_mcp()
# to avoid circular imports. Tools defined in tools.py will automatically
# register when that module is imported.
#
# If you prefer static imports, uncomment the line below after ensuring
# the tools module doesn't cause circular imports:
# from gpt_manager.gpt_manager import tools


@mcp.register()
def handle_mcp():
    """The main MCP endpoint for handling all MCP requests.

    This function is called before each MCP request and is responsible for:
    1. Loading remote server configurations from DocTypes
    2. Starting remote servers if not already started

    The endpoint is exposed at:
        /api/method/gpt_manager.gpt_manager.mcp.handle_mcp
    """
    # Import here to avoid circular imports
    from gpt_manager.gpt_manager.mcp_loader import configure_remote_servers_from_doctype

    # Configure and start remote servers
    configure_remote_servers_from_doctype(mcp)
    mcp.start_remote_servers()
