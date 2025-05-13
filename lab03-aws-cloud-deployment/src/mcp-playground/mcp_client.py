import asyncio
import logging
from typing import Dict, Any, List, Optional
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPClient:
    """
    A client for the Model Context Protocol (MCP) using the streamable HTTP transport.
    This provides a robust, standards-compliant implementation for connecting to
    remote MCP servers.
    """
    
    def __init__(self, url: str, auth_token: str = None):
        """
        Initialize the MCP client with a server URL and optional auth token.
        
        Args:
            url: The URL of the MCP server
            auth_token: Optional authentication token
        """
        self.url = url
        self.session = None
        self.stream_context = None
        self.read_stream = None
        self.write_stream = None
        self.headers = {}
        
        if auth_token:
            self.headers['Authorization'] = f'Bearer {auth_token}'
        
        # Required headers for MCP protocol
        self.headers['Accept'] = 'application/json, text/event-stream'

    async def connect(self):
        """Connect to the MCP server and initialize the session"""
        try:
            self.stream_context = streamablehttp_client(
                self.url,
                headers=self.headers
            )
            self.read_stream, self.write_stream, _ = await self.stream_context.__aenter__()
            self.session = ClientSession(self.read_stream, self.write_stream)
            await self.session.__aenter__()
            await self.session.initialize()
            return True
        except Exception as e:
            logger.error(f"Error connecting to MCP server at {self.url}: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the MCP server and clean up resources"""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing MCP session: {e}")
        
        if self.stream_context:
            try:
                await self.stream_context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing stream context: {e}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of available tools from the MCP server.
        
        Returns:
            A list of tool definitions
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")
            
        try:
            response = await self.session.list_tools()
            return response.tools if response and hasattr(response, 'tools') else []
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name: The name of the tool to call
            params: Parameters to pass to the tool
            
        Returns:
            The tool call result
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")
            
        try:
            logger.info(f"Calling tool: {tool_name} with params: {params}")
            result = await self.session.call_tool(tool_name, params)
            
            # Process the result based on content type
            if hasattr(result, 'content') and result.content:
                content_texts = []
                for content in result.content:
                    if hasattr(content, 'text') and content.text:
                        content_texts.append(content.text)
                
                response = "\n".join(content_texts)
                return {"content": response}
            else:
                return {"content": str(result)}
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": str(e)}

async def test_mcp_client(url: str):
    """Test function to verify the MCP client works correctly"""
    client = MCPClient(url)
    try:
        connected = await client.connect()
        if not connected:
            print(f"Failed to connect to {url}")
            return
            
        tools = await client.list_tools()
        print(f"Available tools: {[tool.name for tool in tools]}")
        
        if tools:
            result = await client.call_tool(
                tools[0].name,
                {}  # Empty params for test
            )
            print(f"Tool call result: {result}")
            
    finally:
        await client.disconnect()

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python mcp_client.py <server_url>")
        sys.exit(1)
        
    asyncio.run(test_mcp_client(sys.argv[1]))