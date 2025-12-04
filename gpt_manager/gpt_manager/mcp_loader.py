"""MCP Loader - Loads remote server configurations from Frappe DocTypes.

This module provides functionality to load MCP Remote Server configurations
from Frappe DocTypes and register them with the MCP instance.

Example usage in a Frappe app:
    ```python
    from gpt_manager.gpt_manager.mcp import mcp
    from gpt_manager.gpt_manager.mcp_loader import configure_remote_servers_from_doctype

    @mcp.register()
    def handle_mcp():
        configure_remote_servers_from_doctype()
        mcp.start_remote_servers()
    ```
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

from frappe_mcp.server.remote import RemoteServerConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Flag to track if configuration has been loaded
_configured = False


def _ensure_dirs_and_files(doc) -> dict[str, str]:
    """Ensure directories and files exist for a remote server configuration.

    This function:
    1. Creates allowed directories if auto_create_paths is enabled
    2. Creates memory files if auto_create is enabled
    3. Sets up environment variables for file paths

    Args:
        doc: A loaded MCP Remote Server document.

    Returns:
        A dict of extra environment variables to set.
    """
    extra_env: dict[str, str] = {}
    paths: list[str] = []

    # Process allowed_directories
    for row in doc.allowed_directories or []:
        try:
            abs_path = os.path.abspath(row.path)

            if doc.auto_create_paths:
                os.makedirs(abs_path, exist_ok=True)
                logger.debug(f'Created/verified directory: {abs_path}')

            paths.append(abs_path)
        except (OSError, AttributeError) as e:
            logger.error(f'Error processing allowed directory {row.path}: {e}')
            # Try to log to Frappe if available
            _log_frappe_error(f'Error processing allowed directory {row.path}: {e}')

    # Set ALLOWED_DIRECTORIES env var if we have paths
    if paths:
        extra_env['ALLOWED_DIRECTORIES'] = os.pathsep.join(paths)

    # Process memory_files
    for row in doc.memory_files or []:
        try:
            file_path = os.path.abspath(row.path)

            should_create = doc.auto_create_paths or getattr(row, 'auto_create', True)
            if should_create:
                # Ensure parent directory exists
                parent_dir = os.path.dirname(file_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)

                # Touch the file (create if not exists)
                with open(file_path, 'a'):
                    pass
                logger.debug(f'Created/verified file: {file_path}')

            # Set environment variable if specified
            env_var_name = getattr(row, 'env_var_name', None)
            if env_var_name:
                extra_env[env_var_name] = file_path

        except (OSError, AttributeError) as e:
            logger.error(f'Error processing memory file {row.path}: {e}')
            _log_frappe_error(f'Error processing memory file {row.path}: {e}')

    return extra_env


def _log_frappe_error(message: str) -> None:
    """Log an error to Frappe's error log if available.

    Args:
        message: The error message to log.
    """
    try:
        import frappe

        frappe.log_error(message=message, title='MCP Loader Error')
    except ImportError:
        pass  # Not in Frappe environment


def configure_remote_servers_from_doctype(mcp_instance=None) -> None:
    """Load enabled MCP Remote Server records and register them with MCP.

    This function queries the MCP Remote Server DocType for enabled records
    and registers each one with the provided MCP instance.

    Args:
        mcp_instance: The MCP instance to register servers with.
            If None, imports from gpt_manager.gpt_manager.mcp.

    Note:
        This function is idempotent - it will only configure servers once.
        Subsequent calls will do nothing.
    """
    global _configured
    if _configured:
        return

    if mcp_instance is None:
        try:
            from gpt_manager.gpt_manager.mcp import mcp

            mcp_instance = mcp
        except ImportError:
            logger.error('Could not import MCP instance from gpt_manager.gpt_manager.mcp')
            return

    try:
        import frappe
    except ImportError:
        logger.warning('Frappe not available, skipping DocType configuration')
        _configured = True
        return

    try:
        docs = frappe.get_all(
            'MCP Remote Server',
            filters={'enabled': 1},
            fields=['name'],
        )
    except Exception as e:
        logger.warning(f'Could not query MCP Remote Server DocType: {e}')
        _configured = True
        return

    for d in docs:
        try:
            doc = frappe.get_doc('MCP Remote Server', d.name)
            _register_remote_server(mcp_instance, doc)
        except Exception as e:
            logger.error(f'Error loading MCP Remote Server {d.name}: {e}')
            _log_frappe_error(f'Error loading MCP Remote Server {d.name}: {e}')

    _configured = True


def _register_remote_server(mcp_instance, doc) -> None:
    """Register a single remote server from a DocType document.

    Args:
        mcp_instance: The MCP instance to register with.
        doc: The MCP Remote Server document.
    """
    # Parse args_json
    try:
        args = json.loads(doc.args_json or '[]')
        if not isinstance(args, list):
            raise ValueError('args_json must be a JSON list')
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f'Invalid args_json for MCP Remote Server {doc.name}: {e}')
        _log_frappe_error(f'Invalid args_json for MCP Remote Server {doc.name}: {e}')
        return

    # Ensure directories and files exist
    extra_env = _ensure_dirs_and_files(doc)

    # Merge environment_variables from child table
    for row in doc.environment_variables or []:
        if row.key:
            extra_env[row.key] = row.value

    # Create configuration
    config = RemoteServerConfig(
        name=doc.server_name,
        command=doc.command,
        args=args,
        env=extra_env if extra_env else None,
        cwd=doc.working_directory or None,
        namespace=doc.namespace or doc.server_name,
    )

    # Register with MCP
    mcp_instance.add_remote_server(config)
    logger.info(f'Registered remote MCP server: {doc.server_name}')


def reset_configuration() -> None:
    """Reset the configuration state to allow reconfiguration.

    This is mainly useful for testing or when you need to reload
    the configuration from DocTypes.
    """
    global _configured
    _configured = False
