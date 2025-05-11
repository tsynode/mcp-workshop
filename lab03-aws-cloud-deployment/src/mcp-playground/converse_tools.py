from typing import Dict, Any, List
import requests
import json

class ConverseToolManager:
    def __init__(self):
        self._mcp_servers = {}
        self._name_mapping = {}  # Maps Bedrock names to MCP names
    
    def register_server(self, server_name: str, server_url: str, tools: List[Dict]):
        """Register an MCP server and its tools"""
        self._mcp_servers[server_name] = {
            'url': server_url,
            'tools': {}
        }
        
        # Register each tool with name translation
        for tool in tools:
            mcp_name = tool.get('name')  # Original hyphenated name (e.g., 'get-product')
            bedrock_name = mcp_name.replace('-', '_')  # Sanitized name (e.g., 'get_product')
            
            # Store the mapping
            self._name_mapping[bedrock_name] = {
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
    
    def translate_tool_call(self, tool_name: str, tool_input: Dict) -> Dict:
        """Translate a Bedrock tool call to an MCP request"""
        if tool_name not in self._name_mapping:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        mapping = self._name_mapping[tool_name]
        server_name = mapping['server']
        method_name = mapping['method']
        
        return {
            'server_url': self._mcp_servers[server_name]['url'],
            'method': method_name,
            'params': tool_input
        }
    
    def get_server_names(self) -> List[str]:
        """Get list of registered server names"""
        return list(self._mcp_servers.keys())
    
    def discover_mcp_tools(self, server_name: str, server_url: str):
        """Discover tools from an MCP server using tools/list"""
        try:
            # Create a tools/list request according to MCP specification
            list_request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": "discovery"
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
                    self.register_server(server_name, server_url, tools)
                    return len(tools)
            
            # Return 0 if discovery fails
            return 0
        except Exception as e:
            print(f"Error discovering tools: {str(e)}")
            return 0
