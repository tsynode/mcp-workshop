"""
Bedrock MCP Adapter - Handles the translation between Bedrock's tool format and MCP's JSON-RPC format.
Based on the AWS example: https://github.com/mikegc-aws/amazon-bedrock-mcp
"""

from typing import Dict, Any, List
import requests
import json
import uuid

class BedrockMcpAdapter:
    """
    Adapter class that handles the translation between Bedrock's tool format and MCP's JSON-RPC format.
    Implements name sanitization (hyphen to underscore) and proper mapping between the two formats.
    """
    
    def __init__(self):
        self._mcp_servers = {}
        self._name_mapping = {}  # Maps Bedrock names (with underscores) to MCP names (with hyphens)
    
    def register_server(self, server_name: str, server_url: str):
        """Register an MCP server"""
        self._mcp_servers[server_name] = {
            'url': server_url,
            'tools': {}
        }
    
    def discover_tools(self, server_name: str) -> int:
        """
        Discover tools from an MCP server using the tools/list method
        Returns the number of tools discovered
        """
        if server_name not in self._mcp_servers:
            raise ValueError(f"Server {server_name} not registered")
            
        server_url = self._mcp_servers[server_name]['url']
        
        try:
            # Create a tools/list request according to MCP specification
            list_request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": str(uuid.uuid4())
            }
            
            # Send the request to the MCP server
            response = requests.post(
                server_url,
                json=list_request,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                verify=False  # For development only
            )
            
            # Parse the response
            if response.status_code == 200:
                result = response.json()
                if "result" in result and "tools" in result["result"]:
                    tools = result["result"]["tools"]
                    
                    # Register each tool with name translation
                    for tool in tools:
                        self._register_tool(server_name, tool)
                    
                    return len(tools)
            
            # Return 0 if discovery fails
            return 0
        except Exception as e:
            print(f"Error discovering tools: {str(e)}")
            return 0
    
    def _register_tool(self, server_name: str, tool: Dict):
        """Register a tool with name translation"""
        mcp_name = tool.get('name')  # Original hyphenated name (e.g., 'get-product')
        bedrock_name = mcp_name.replace('-', '_')  # Sanitized name (e.g., 'get_product')
        
        # Create a fully qualified name with server prefix to avoid collisions
        qualified_bedrock_name = f"{server_name.replace('-', '_')}_{bedrock_name}"
        
        # Store the mapping
        self._name_mapping[qualified_bedrock_name] = {
            'server': server_name,
            'method': mcp_name
        }
        
        # Store the tool details
        self._mcp_servers[server_name]['tools'][mcp_name] = tool
    
    def get_tool_config(self) -> Dict:
        """Generate Bedrock tool configuration with sanitized names"""
        tool_specs = []
        
        # Create tool specs for each registered tool
        for bedrock_name, mapping in self._name_mapping.items():
            server_name = mapping['server']
            mcp_name = mapping['method']
            
            # Get the original tool details
            tool_details = self._mcp_servers[server_name]['tools'][mcp_name]
            
            # Create a tool spec with the sanitized name
            tool_spec = {
                "toolSpec": {
                    "name": bedrock_name,  # Use sanitized name for Bedrock
                    "description": f"{server_name}: {tool_details.get('description', '')}",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": tool_details.get('inputSchema', {}).get('properties', {}),
                            "x-mcp": {
                                "url": self._mcp_servers[server_name]['url'],
                                "insecureTls": True  # Allow self-signed certificates
                            }
                        }
                    }
                }
            }
            
            tool_specs.append(tool_spec)
        
        return {"tools": tool_specs}
    
    def translate_tool_call(self, bedrock_tool_name: str, tool_input: Dict) -> Dict:
        """Translate a Bedrock tool call to an MCP request"""
        if bedrock_tool_name not in self._name_mapping:
            raise ValueError(f"Unknown tool: {bedrock_tool_name}")
        
        mapping = self._name_mapping[bedrock_tool_name]
        server_name = mapping['server']
        method_name = mapping['method']
        
        return {
            'server_url': self._mcp_servers[server_name]['url'],
            'method': method_name,
            'params': tool_input
        }
    
    def execute_tool(self, bedrock_tool_name: str, tool_input: Dict) -> Dict:
        """Execute a tool call and return the result"""
        # Translate the tool call
        mcp_info = self.translate_tool_call(bedrock_tool_name, tool_input)
        
        # Extract the translated information
        mcp_url = mcp_info['server_url']
        method_name = mcp_info['method']
        params = mcp_info['params']
        
        # Create a standard JSON-RPC 2.0 request
        mcp_request = {
            "jsonrpc": "2.0",
            "method": method_name,
            "params": params,
            "id": str(uuid.uuid4())
        }
        
        # Send the request to the MCP server
        response = requests.post(
            mcp_url,
            json=mcp_request,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            },
            verify=False  # For development only
        )
        
        # Parse the response
        return self._parse_mcp_response(response)
    
    def _parse_mcp_response(self, response):
        """Parse an MCP response (handles both JSON and SSE formats)"""
        response_text = response.text
        
        # Check if the response is in SSE format
        if response_text.startswith('event:') or '\ndata:' in response_text:
            # Extract the JSON from the SSE format
            data_lines = [line for line in response_text.split('\n') if line.startswith('data:')]
            if data_lines:
                json_str = data_lines[0][5:]  # Remove 'data:' prefix
                return json.loads(json_str)
            else:
                return {"error": {"message": "Could not parse SSE response"}}
        else:
            # Regular JSON response
            return response.json()
