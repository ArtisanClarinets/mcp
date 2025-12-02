"""Remote MCP server support for hosting multiple MCP servers as subprocesses."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any


class RemoteServerError(Exception):
    """Exception raised when a remote MCP server operation fails."""

    pass


@dataclass
class RemoteServerConfig:
    """Configuration for a remote MCP server subprocess.

    Attributes:
        name: Internal ID for the server, e.g. "memory"
        command: Command to run, e.g. "npx"
        args: Arguments for the command, e.g. ["-y", "@modelcontextprotocol/server-memory"]
        env: Additional environment variables to set
        cwd: Working directory for the subprocess
        namespace: Namespace prefix for tool names, defaults to name
    """

    name: str
    command: str
    args: list[str]
    env: dict[str, str] | None = None
    cwd: str | None = None
    namespace: str | None = None


@dataclass
class RemoteMCPServer:
    """Wraps a stdio MCP subprocess and provides JSON-RPC communication.

    This class manages a remote MCP server process, handling startup,
    JSON-RPC communication over stdin/stdout, and tool invocation.
    """

    config: RemoteServerConfig
    process: subprocess.Popen[bytes] | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _next_id: int = 0

    def start(self) -> None:
        """Start the remote MCP server process if not already started.

        Merges config.env into the current environment and spawns the subprocess.
        After spawning, calls initialize() to complete the MCP handshake.

        Raises:
            RemoteServerError: If the subprocess fails to start.
        """
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                return  # Already running

            # Build environment
            env = os.environ.copy()
            if self.config.env:
                env.update(self.config.env)

            try:
                cmd = [self.config.command, *self.config.args]
                self.process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=self.config.cwd,
                )
            except (OSError, subprocess.SubprocessError) as e:
                raise RemoteServerError(
                    f"Failed to start remote server '{self.config.name}': {e}"
                ) from e

        # Initialize outside the lock to allow other operations
        self.initialize()

    def _send_request(self, method: str, params: dict[str, Any] | None = None) -> dict:
        """Send a JSON-RPC 2.0 request and return the response.

        Args:
            method: The RPC method name
            params: Optional parameters for the method

        Returns:
            The parsed JSON response as a dict

        Raises:
            RemoteServerError: If the process is not running or communication fails.
        """
        with self._lock:
            if self.process is None or self.process.poll() is not None:
                raise RemoteServerError(
                    f"Remote server '{self.config.name}' is not running"
                )

            if self.process.stdin is None or self.process.stdout is None:
                raise RemoteServerError(
                    f"Remote server '{self.config.name}' has no stdin/stdout"
                )

            self._next_id += 1
            request_id = self._next_id

            request: dict[str, Any] = {
                'jsonrpc': '2.0',
                'id': request_id,
                'method': method,
            }
            if params is not None:
                request['params'] = params

            try:
                request_line = json.dumps(request) + '\n'
                self.process.stdin.write(request_line.encode('utf-8'))
                self.process.stdin.flush()

                response_line = self.process.stdout.readline()
                if not response_line:
                    raise RemoteServerError(
                        f"Remote server '{self.config.name}' closed connection"
                    )

                response = json.loads(response_line.decode('utf-8'))
                return response

            except (OSError, json.JSONDecodeError) as e:
                raise RemoteServerError(
                    f"Communication error with remote server '{self.config.name}': {e}"
                ) from e

    def initialize(self) -> dict:
        """Call the remote server's initialize method.

        Returns:
            The parsed result containing protocolVersion, serverInfo, etc.

        Raises:
            RemoteServerError: If initialization fails.
        """
        params = {
            'protocolVersion': '2025-03-26',
            'capabilities': {},
            'clientInfo': {'name': 'frappe-mcp-host', 'version': '0.1.0'},
        }
        response = self._send_request('initialize', params)

        if 'error' in response:
            raise RemoteServerError(
                f"Remote server '{self.config.name}' initialization failed: "
                f"{response['error']}"
            )

        # Send initialized notification
        self._send_notification('notifications/initialized', {})

        return response.get('result', {})

    def _send_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        """Send a JSON-RPC 2.0 notification (no response expected).

        Args:
            method: The notification method name
            params: Optional parameters for the notification
        """
        with self._lock:
            if self.process is None or self.process.poll() is not None:
                return

            if self.process.stdin is None:
                return

            notification: dict[str, Any] = {
                'jsonrpc': '2.0',
                'method': method,
            }
            if params is not None:
                notification['params'] = params

            try:
                notification_line = json.dumps(notification) + '\n'
                self.process.stdin.write(notification_line.encode('utf-8'))
                self.process.stdin.flush()
            except OSError:
                pass  # Ignore errors for notifications

    def list_tools(self) -> list[dict]:
        """Query the remote server for available tools.

        Returns:
            A list of tool descriptors from the remote server.

        Raises:
            RemoteServerError: If the request fails.
        """
        response = self._send_request('tools/list', {})

        if 'error' in response:
            raise RemoteServerError(
                f"Remote server '{self.config.name}' tools/list failed: "
                f"{response['error']}"
            )

        result = response.get('result', {})
        return result.get('tools', [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool on the remote server.

        Args:
            name: The tool name (raw, not namespaced)
            arguments: Arguments to pass to the tool

        Returns:
            The tool call result.

        Raises:
            RemoteServerError: If the tool call fails.
        """
        params = {'name': name, 'arguments': arguments}
        response = self._send_request('tools/call', params)

        if 'error' in response:
            raise RemoteServerError(
                f"Remote server '{self.config.name}' tool call '{name}' failed: "
                f"{response['error']}"
            )

        return response.get('result', {})

    def stop(self) -> None:
        """Stop the remote server subprocess if running."""
        with self._lock:
            if self.process is not None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                finally:
                    self.process = None

    def is_running(self) -> bool:
        """Check if the remote server process is running.

        Returns:
            True if the process is running, False otherwise.
        """
        with self._lock:
            return self.process is not None and self.process.poll() is None
