"""Tests for remote MCP server functionality."""

from __future__ import annotations

import io
import json
import unittest

from werkzeug.wrappers import Request, Response

from frappe_mcp.server.remote import (
    RemoteMCPServer,
    RemoteServerConfig,
)
from frappe_mcp.server.server import MCP


class TestRemoteServerConfig(unittest.TestCase):
    """Test RemoteServerConfig dataclass."""

    def test_config_creation(self):
        """Test creating a remote server config."""
        config = RemoteServerConfig(
            name='memory',
            command='npx',
            args=['-y', '@modelcontextprotocol/server-memory'],
            env={'MEMORY_FILE': '/tmp/memory.json'},
            cwd='/tmp',
            namespace='mem',
        )

        self.assertEqual(config.name, 'memory')
        self.assertEqual(config.command, 'npx')
        self.assertEqual(config.args, ['-y', '@modelcontextprotocol/server-memory'])
        self.assertEqual(config.env, {'MEMORY_FILE': '/tmp/memory.json'})
        self.assertEqual(config.cwd, '/tmp')
        self.assertEqual(config.namespace, 'mem')

    def test_config_defaults(self):
        """Test that optional fields default to None."""
        config = RemoteServerConfig(
            name='test',
            command='echo',
            args=['hello'],
        )

        self.assertIsNone(config.env)
        self.assertIsNone(config.cwd)
        self.assertIsNone(config.namespace)


class TestRemoteMCPServer(unittest.TestCase):
    """Test RemoteMCPServer class."""

    def test_server_creation(self):
        """Test creating a remote MCP server."""
        config = RemoteServerConfig(name='test', command='echo', args=['hello'])
        server = RemoteMCPServer(config)

        self.assertEqual(server.config, config)
        self.assertIsNone(server.process)
        self.assertFalse(server.is_running())

    def test_is_running_false_when_no_process(self):
        """Test is_running returns False when no process."""
        config = RemoteServerConfig(name='test', command='echo', args=['hello'])
        server = RemoteMCPServer(config)

        self.assertFalse(server.is_running())


class TestMCPWithRemoteServers(unittest.TestCase):
    """Test MCP class with remote server support."""

    def test_add_remote_server(self):
        """Test adding a remote server to MCP."""
        mcp = MCP(name='test')
        config = RemoteServerConfig(name='memory', command='echo', args=['hello'])

        mcp.add_remote_server(config)

        self.assertIn('memory', mcp._remote_servers)
        self.assertIsInstance(mcp._remote_servers['memory'], RemoteMCPServer)

    def test_remote_started_flag(self):
        """Test that _remote_started flag is initially False."""
        mcp = MCP(name='test')
        self.assertFalse(mcp._remote_started)

    def test_start_remote_servers_without_servers(self):
        """Test that start_remote_servers works with no servers."""
        mcp = MCP(name='test')

        # Should not raise
        mcp.start_remote_servers()

        self.assertTrue(mcp._remote_started)

    def test_start_remote_servers_idempotent(self):
        """Test that start_remote_servers is idempotent."""
        mcp = MCP(name='test')

        mcp.start_remote_servers()
        first_started = mcp._remote_started

        mcp.start_remote_servers()
        second_started = mcp._remote_started

        self.assertTrue(first_started)
        self.assertTrue(second_started)

    def test_list_all_tools_empty(self):
        """Test list_all_tools with no tools."""
        mcp = MCP(name='test')

        tools = mcp.list_all_tools()

        self.assertEqual(tools, [])

    def test_list_all_tools_with_local_tools(self):
        """Test list_all_tools with only local tools."""
        mcp = MCP(name='test')

        @mcp.tool()
        def adder(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        tools = mcp.list_all_tools()

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]['name'], 'adder')

    def test_tools_list_handler(self):
        """Test tools/list request handler."""
        mcp = MCP(name='test')

        @mcp.tool()
        def calculator(x: int) -> int:
            """A simple calculator."""
            return x * 2

        request_data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/list',
            'params': {},
        }
        request = Request.from_values(
            method='POST',
            content_type='application/json',
            input_stream=io.BytesIO(json.dumps(request_data).encode('utf-8')),
        )

        response = mcp.handle(request, Response())

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['id'], 1)
        self.assertIn('result', response_data)
        self.assertIn('tools', response_data['result'])

        tools = response_data['result']['tools']
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]['name'], 'calculator')

    def test_tools_call_handler_local_tool(self):
        """Test tools/call request for a local tool."""
        mcp = MCP(name='test')

        @mcp.tool()
        def double(x: int) -> int:
            """Double a number."""
            return x * 2

        request_data = {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/call',
            'params': {'name': 'double', 'arguments': {'x': 5}},
        }
        request = Request.from_values(
            method='POST',
            content_type='application/json',
            input_stream=io.BytesIO(json.dumps(request_data).encode('utf-8')),
        )

        response = mcp.handle(request, Response())

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['id'], 2)
        self.assertIn('result', response_data)
        self.assertIn('content', response_data['result'])


class TestRemoteToolsIntegration(unittest.TestCase):
    """Test integration of remote tools with MCP."""

    def test_remote_tool_name_in_registry(self):
        """Test that remote tool names are stored in the registry."""
        mcp = MCP(name='test')
        config = RemoteServerConfig(
            name='memory', command='echo', args=['hello'], namespace='mem'
        )
        mcp.add_remote_server(config)

        # Manually add a remote tool
        mcp._remote_tools['mem.create_entities'] = 'memory'

        self.assertIn('mem.create_entities', mcp._remote_tools)
        self.assertEqual(mcp._remote_tools['mem.create_entities'], 'memory')

    def test_call_remote_tool_raises_when_not_in_registry(self):
        """Test that calling a non-existent remote tool raises KeyError."""
        mcp = MCP(name='test')

        with self.assertRaises(KeyError):
            mcp._call_remote_tool('nonexistent.tool', {})


if __name__ == '__main__':
    unittest.main()
