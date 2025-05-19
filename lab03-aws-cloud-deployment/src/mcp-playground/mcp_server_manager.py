"""
MCP Server Manager - Handles registration, discovery, and management of MCP servers
using the standard MCP protocol.
"""

from typing import Dict, Any, List, Optional
import logging
import uuid
import asyncio
import json
from mcp_client import MCPClient

logger = logging.getLogger(__name__)

class MCPServerManager:
    """
    Manages multiple MCP servers, handles registration, discovery of tools,
    and routing of tool calls to appropriate servers.
    """
    
    def __init__(self):
        """Initialize the server manager with empty state"""
        self.servers = {}  # Map of server_name to server details
        self.tool_mapping = {}  # Map of bedrock_name to server and tool details
        self.clients = {}  # Map of server_name to MCPClient instances
        self.event_loop = None
    
    def _ensure_event_loop(self):
        """Ensure we have an event loop for async operations"""
        try:
            self.event_loop = asyncio.get_event_loop()
        except RuntimeError:
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
    
    def register_server(self, server_name: str, server_url: str, auth_token: Optional[str] = None) -> bool:
        """
        Register a new MCP server.
        
        Args:
            server_name: A unique name for this server
            server_url: The URL of the MCP server
            auth_token: Optional auth token for the server
            
        Returns:
            True if registration succeeded, False otherwise
        """
        # Create server entry
        self.servers[server_name] = {
            'url': server_url,
            'auth_token': auth_token,
            'tools': {},
            'status': 'registered'
        }
        
        # Create client for this server
        try:
            client = MCPClient(server_url, auth_token)
            self.clients[server_name] = client
            return True
        except Exception as e:
            logger.error(f"Error creating client for {server_name}: {e}")
            self.servers[server_name]['status'] = 'error'
            return False
    
    def remove_server(self, server_name: str) -> bool:
        """
        Remove a registered server.
        
        Args:
            server_name: The name of the server to remove
            
        Returns:
            True if server was removed, False otherwise
        """
        if server_name not in self.servers:
            return False
        
        # Remove tool mappings for this server
        to_remove = []
        for tool_name, mapping in self.tool_mapping.items():
            if mapping['server'] == server_name:
                to_remove.append(tool_name)
        
        for tool_name in to_remove:
            del self.tool_mapping[tool_name]
        
        # Close client if it exists
        client = self.clients.pop(server_name, None)
        if client:
            self._ensure_event_loop()
            asyncio.run_coroutine_threadsafe(client.disconnect(), self.event_loop)
        
        # Remove server entry
        del self.servers[server_name]
        return True
    
    def discover_tools(self, server_name: str) -> int:
        """
        Discover tools from a registered server.
        
        Args:
            server_name: The name of the server
            
        Returns:
            Number of tools discovered
        """
        if server_name not in self.servers:
            return 0
        
        client = self.clients.get(server_name)
        if not client:
            return 0
        
        self._ensure_event_loop()
        
        try:
            # Connect to the server
            connected = asyncio.run_coroutine_threadsafe(
                client.connect(), self.event_loop).result()
            
            if not connected:
                logger.error(f"Failed to connect to {server_name}")
                self.servers[server_name]['status'] = 'connection_error'
                return 0
            
            # List tools from the server
            tools = asyncio.run_coroutine_threadsafe(
                client.list_tools(), self.event_loop).result()
            
            # Register each tool
            tool_count = 0
            for tool in tools:
                self._register_tool(server_name, tool)
                tool_count += 1
            
            # Update server status
            self.servers[server_name]['status'] = 'ready'
            
            return tool_count
        except Exception as e:
            logger.error(f"Error discovering tools from {server_name}: {e}")
            self.servers[server_name]['status'] = 'error'
            return 0
    
    def _register_tool(self, server_name: str, tool: Dict[str, Any]):
        """Register a tool with name translation for Bedrock compatibility"""
        tool_name = getattr(tool, 'name', tool.get('name', ''))
        if not tool_name:
            return
        
        # For Bedrock compatibility, replace hyphens with underscores
        bedrock_name = f"{server_name}_{tool_name.replace('-', '_')}"
        
        # Store the mapping
        self.tool_mapping[bedrock_name] = {
            'server': server_name,
            'method': tool_name
        }
        
        # Store the tool details in the server
        self.servers[server_name]['tools'][tool_name] = tool
    
    def get_bedrock_tool_config(self) -> Dict[str, Any]:
        """
        Get tool configuration for Bedrock.
        
        Returns:
            Tool configuration compatible with Bedrock API
        """
        tool_specs = []
        
        for bedrock_name, mapping in self.tool_mapping.items():
            server_name = mapping['server']
            method_name = mapping['method']
            
            # Get tool details
            server = self.servers.get(server_name, {})
            tools = server.get('tools', {})
            tool = tools.get(method_name, {})
            
            # Skip if we don't have tool details
            if not tool:
                continue
            
            # Get description and schema
            description = getattr(tool, 'description', tool.get('description', ''))
            input_schema = getattr(tool, 'inputSchema', tool.get('inputSchema', {}))
            
            if not isinstance(input_schema, dict):
                input_schema = json.loads(json.dumps(input_schema))
            
            # Create tool spec
            tool_spec = {
                "toolSpec": {
                    "name": bedrock_name,
                    "description": f"{server_name}: {description}",
                    "inputSchema": {
                        "json": input_schema
                    }
                }
            }
            
            tool_specs.append(tool_spec)
        
        return {"tools": tool_specs}
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool by its Bedrock name.
        
        Args:
            tool_name: The Bedrock-compatible tool name
            params: Tool parameters
            
        Returns:
            Tool result
        """
        # Find the mapping for this tool
        mapping = self.tool_mapping.get(tool_name)
        if not mapping:
            return {"error": f"Unknown tool: {tool_name}"}
        
        server_name = mapping['server']
        method_name = mapping['method']
        
        # Get client for this server
        client = self.clients.get(server_name)
        if not client:
            return {"error": f"No client for server: {server_name}"}
        
        # Ensure we're connected
        connected = await client.connect()
        if not connected:
            return {"error": f"Failed to connect to server: {server_name}"}
        
        try:
            # Call the tool
            result = await client.call_tool(method_name, params)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {method_name} on {server_name}: {e}")
            return {"error": str(e)}
        finally:
            # Don't disconnect - we'll maintain the connection for future calls
            pass
    
    def close_all(self):
        """Close all client connections"""
        for server_name, client in self.clients.items():
            try:
                self._ensure_event_loop()
                asyncio.run_coroutine_threadsafe(client.disconnect(), self.event_loop)
            except Exception as e:
                logger.error(f"Error closing client for {server_name}: {e}")