from __future__ import annotations

import json
import logging
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError
from werkzeug.wrappers import Request, Response

import frappe_mcp.server.handlers as handlers
import frappe_mcp.server.tools as tools
from frappe_mcp.server import types
from frappe_mcp.server.remote import (
    RemoteMCPServer,
    RemoteServerConfig,
    RemoteServerError,
)

__all__ = ['MCP', 'RemoteMCPServer', 'RemoteServerConfig', 'RemoteServerError']

logger = logging.getLogger(__name__)


class MCP:
    """The main class for creating an MCP server.

    This class orchestrates the handling of JSON-RPC requests, manages a
    registry of available tools, and integrates with a web server framework
    to expose the MCP functionality.

    In a Frappe application, you would typically create a single instance of
    this class and use the `@mcp.register()` decorator on an API endpoint.
    Tools can be added using the `@mcp.tool()` decorator.

    Example:
        ```python
        # In app/mcp.py
        from frappe_mcp import MCP

        mcp = MCP(name="my-mcp-server")

        @mcp.tool()
        def my_tool(param1: str):
            '''A simple tool.'''
            return f"You said: {param1}"

        @mcp.register()
        def mcp_endpoint():
            '''The entry point for MCP requests.'''
            # This function body is executed before request handling.
            # It's a good place to import modules that register tools.
            pass
        ```

    For use in other Werkzeug-based servers, you can use the `mcp.handle()`
    method directly.
    """

    _name: str | None
    _tool_registry: OrderedDict[str, tools.Tool]
    _mcp_entry_fn: Callable | None
    _remote_servers: dict[str, RemoteMCPServer]
    _remote_tools: dict[str, str]  # host_tool_name -> remote_server_name
    _remote_started: bool

    def __init__(self, name: str | None = None):
        self._tool_registry = OrderedDict()
        self._name = name
        self._mcp_entry_fn = None
        self._remote_servers = {}
        self._remote_tools = {}
        self._remote_started = False

    def register(
        self,
        *,
        allow_guest: bool = False,
        xss_safe: bool = False,
    ):
        """A decorator to mark a function as an MCP endpoint.

        This is a wrapper around frappe.whitelist() that sets up the necessary
        configuration for handling MCP requests. The decorated function will be
        used as the entry point for all MCP requests.

        Only one function can be registered as an MCP endpoint per MCP instance.

        Args:
            allow_guest: If True, allows unauthenticated access to the endpoint.
            xss_safe: If True, response will not be sanitized for XSS.

        Raises:
            Exception: If not used in a Frappe app, or if already registered.
        """
        from werkzeug import Response

        try:
            import frappe
        except ImportError as e:
            raise Exception(
                'mcp.register can be used only in a Frappe app.\n'
                'If you are using it in some other Werkzeug based server\n'
                'you should use the mcp.handle function instead.'
            ) from e

        whitelister = frappe.whitelist(
            allow_guest=allow_guest,
            xss_safe=xss_safe,
            methods=['GET', 'POST'],
        )

        def decorator(fn):
            if self._mcp_entry_fn is not None:
                raise Exception('mcp.register can be used only once per MCP instance')

            self._mcp_entry_fn = fn

            def wrapper() -> Response:
                # Runs wrapped dummy mcp handler before handling the request.
                # This should import all the files with the registered mcp
                # functions.
                fn()

                request = frappe.request
                response = Response()

                return self.handle(request, response)

            return whitelister(wrapper)

        return decorator

    def handle(self, request: Request, response: Response) -> Response:
        """Handle an MCP request in any Werkzeug based server.

        This method can be used directly to integrate MCP functionality into any Werkzeug based server.
        It processes the request according to the MCP specification and returns an appropriate response.

        Args:
            request: The Werkzeug Request object containing the MCP request
            response: A Werkzeug Response object to be populated with the MCP response

        Returns:
            The populated Werkzeug Response object
        """
        if request.method != 'POST':
            response.status_code = 405
            return response

        try:
            data = request.get_json(force=True)
        except json.JSONDecodeError:
            return handle_invalid(None, response, types.PARSE_ERROR, 'Parse error')

        if get_is_notification(data):
            return handle_notification(data, response)

        if (request_id := data.get('id')) is None:
            return handle_invalid(
                request_id,
                response,
                types.INVALID_REQUEST,
                'Invalid Request',
            )

        return self._handle_request(request_id, data, response)

    def tool(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        input_schema: dict | None = None,
        use_entire_docstring: bool = False,
        annotations: tools.ToolAnnotations | None = None,
        # stream: bool = False,  # stream yes or no (SSE)
        # whitelist: list | None = None,
        # role: str | None = None,
    ):
        """A decorator that registers a function as a tool that can be used by an LLM.

        Example:
            >>> @mcp.tool()
            ... def get_current_weather(location: str, unit: str = "celsius"):
            ...     '''Get the current weather in a given location.'''
            ...     # ... implementation ...

        Args:
            name: The name of the tool. If not provided, the function's `__name__` will be used.
            description: A description of what the tool does. If not provided, it will be
                extracted from the function's docstring.
            input_schema: The JSON schema for the tool's input. If not provided, it will be
                inferred from the function's signature and docstring.
            use_entire_docstring: If True, the entire docstring will be used as the tool's
                description. Otherwise, only the first section is used (i.e. no Args).
            annotations: Additional context about the tool, such as validation information
                or examples of how to use it.
        """

        def decorator(fn: Callable):
            tool = tools.get_tool(
                fn,
                tools.ToolOptions(
                    name=name,
                    description=description,
                    input_schema=input_schema,
                    use_entire_docstring=use_entire_docstring,
                    annotations=annotations,
                ),
            )
            self.add_tool(tool)
            return fn

        return decorator

    def add_tool(self, tool: tools.Tool):
        """Registers a tool with the MCP instance.

        This method allows for adding a tool programmatically, serving as an
        alternative to the `@mcp.tool` decorator. The provided tool should
        be a dictionary conforming to the `frappe_mcp.Tool` `TypedDict` structure.

        Args:
            tool: The tool to register. It must be a dictionary with keys
                'name', 'description', 'input_schema', and 'fn'.
        """
        self._tool_registry[tool['name']] = tool

    def add_remote_server(self, config: RemoteServerConfig) -> None:
        """Register a remote MCP server with this host.

        The remote server is registered but not started yet. Call start_remote_servers()
        to start all registered remote servers.

        Args:
            config: Configuration for the remote server.
        """
        self._remote_servers[config.name] = RemoteMCPServer(config)

    def start_remote_servers(self) -> None:
        """Idempotently start all registered remote servers and sync their tools.

        This method is safe to call multiple times. On first call, it starts
        all remote servers and synchronizes their tools. Subsequent calls do nothing.
        """
        if self._remote_started:
            return

        for server in self._remote_servers.values():
            try:
                server.start()
                self._sync_remote_tools(server)
            except RemoteServerError as e:
                logger.error(f'Failed to start remote server: {e}')

        self._remote_started = True

    def _sync_remote_tools(self, server: RemoteMCPServer) -> None:
        """Query tools from a remote server and populate the remote tools registry.

        Tool names are namespaced using the server's namespace (or name if no
        namespace is set), e.g., "memory.create_entities".

        Args:
            server: The remote server to sync tools from.
        """
        ns = server.config.namespace or server.config.name
        try:
            tools_list = server.list_tools()
            for t in tools_list:
                raw_name = t['name']
                host_name = f'{ns}.{raw_name}'
                self._remote_tools[host_name] = server.config.name
        except RemoteServerError as e:
            logger.error(f'Failed to sync tools from remote server {ns}: {e}')

    def list_all_tools(self) -> list[dict[str, Any]]:
        """Combine local tools and remote tools into a single MCP tools list.

        Local tool names stay as-is. Remote tool names are namespaced
        (e.g., "memory.create_entities").

        Returns:
            A list of tool descriptors for both local and remote tools.
        """
        # Local tools - use existing serialization
        local_tools: list[dict[str, Any]] = []
        for tool_info in self._tool_registry.values():
            if tool := tools.handlers.get_validated_tool(tool_info):
                local_tools.append(tool.model_dump(exclude_none=True, by_alias=True))

        # Remote tools - query remote servers and rename tools
        remote_tools: list[dict[str, Any]] = []
        for host_name, server_name in self._remote_tools.items():
            server = self._remote_servers.get(server_name)
            if server is None:
                continue

            ns = server.config.namespace or server_name
            raw_name = host_name.split('.', 1)[1]

            try:
                for t in server.list_tools():
                    if t['name'] == raw_name:
                        t_copy = dict(t)
                        t_copy['name'] = host_name
                        remote_tools.append(t_copy)
                        break
            except RemoteServerError as e:
                logger.error(f'Failed to list tools from remote server {ns}: {e}')

        return local_tools + remote_tools

    def _call_remote_tool(
        self, host_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Route a tools/call to the appropriate RemoteMCPServer.

        Args:
            host_name: The namespaced tool name (e.g., "memory.create_entities").
            arguments: Arguments to pass to the tool.

        Returns:
            The tool call result.

        Raises:
            RemoteServerError: If the tool call fails.
        """
        server_name = self._remote_tools[host_name]
        server = self._remote_servers[server_name]
        raw_name = host_name.split('.', 1)[1]
        return server.call_tool(raw_name, arguments)

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/list request, combining local and remote tools.

        Args:
            params: The request parameters.

        Returns:
            A dict with 'tools' list and 'nextCursor'.
        """
        types.ListToolsRequestParams.model_validate(params)

        # Start remote servers if not already started
        self.start_remote_servers()

        all_tools = self.list_all_tools()
        result = types.ListToolsResult(tools=all_tools, nextCursor=None)
        return result.model_dump(exclude_none=True, by_alias=True)

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call request, routing to local or remote tools.

        Args:
            params: The request parameters including 'name' and 'arguments'.

        Returns:
            The tool call result.
        """
        call_params = types.CallToolRequestParams.model_validate(params)
        tool_name = call_params.name
        arguments = call_params.arguments or {}

        # Start remote servers if not already started
        self.start_remote_servers()

        # Check if it's a remote tool
        if tool_name in self._remote_tools:
            try:
                return self._call_remote_tool(tool_name, arguments)
            except RemoteServerError as e:
                error_content = types.TextContent(
                    text=f"Remote server error: {e}"
                )
                result = types.CallToolResult(content=[error_content], isError=True)
                return result.model_dump(exclude_none=True, by_alias=True)

        # Otherwise, use local tool handler
        return tools.handle_call_tool(params, self._tool_registry)

    def _handle_request(
        self,
        request_id: types.RequestId,
        data: dict,
        response: Response,
    ) -> Response:
        # Request
        try:
            rpc_request = types.JSONRPCRequest.model_validate(data)
        except ValidationError as e:
            return handle_invalid(
                request_id,
                response,
                types.INVALID_PARAMS,
                f'Invalid params: {e}',
            )

        method = rpc_request.method
        params = rpc_request.params or {}

        result = None

        match method:
            case 'initialize':
                result = handlers.handle_initialize(params, self._name or 'frappe-mcp')
            case 'ping':
                result = handlers.handle_ping(params)
            case 'completion/complete':
                result = handlers.handle_complete(params)
            case 'logging/setLevel':
                result = handlers.handle_set_level(params)
            case 'prompts/get':
                result = handlers.handle_get_prompt(params)
            case 'prompts/list':
                result = handlers.handle_list_prompts(params)
            case 'resources/list':
                result = handlers.handle_list_resources(params)
            case 'resources/templates/list':
                result = handlers.handle_list_resource_templates(params)
            case 'resources/read':
                result = handlers.handle_read_resource(params)
            case 'resources/subscribe':
                result = handlers.handle_subscribe(params)
            case 'resources/unsubscribe':
                result = handlers.handle_unsubscribe(params)
            case 'tools/call':
                result = self._handle_tools_call(params)
            case 'tools/list':
                result = self._handle_tools_list(params)
            case _:
                return handle_invalid(
                    request_id,
                    response,
                    types.METHOD_NOT_FOUND,
                    'Method not found',
                )

        result = {} if result is None else result
        success_response = types.JSONRPCSuccessResponse(id=request_id, result=result)
        response.data = get_response_data(success_response)
        response.mimetype = 'application/json'
        response.status_code = 200
        return response


def handle_notification(data: dict, response: Response) -> Response:
    # Notification
    try:
        rpc_notification = types.JSONRPCNotification.model_validate(data)
    except ValidationError:
        # Notifications with invalid params are ignored
        pass
    else:
        method = rpc_notification.method
        params = rpc_notification.params or {}
        match method:
            case 'notifications/cancelled':
                handlers.handle_cancelled(params)
            case 'notifications/progress':
                handlers.handle_progress(params)
            case 'notifications/initialized':
                handlers.handle_initialized(params)
            case 'notifications/roots/list_changed':
                handlers.handle_roots_list_changed(params)

    response.status_code = 202  # Accepted
    return response


def handle_invalid(
    request_id: types.RequestId,
    response: Response,
    code: int,
    message: str,
) -> Response:
    error_response = types.JSONRPCErrorResponse(
        id=request_id if request_id is not None else None,
        error=types.Error(code=code, message=message),
    )
    response.data = get_response_data(error_response)
    response.mimetype = 'application/json'
    response.status_code = 400
    return response


def get_response_data(model: BaseModel):
    return model.model_dump_json(exclude_none=True, by_alias=True)


def get_is_notification(data: dict) -> bool:
    method = data.get('method', '')
    return isinstance(method, str) and method.startswith('notifications/')
