from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from mcp.types import Tool, TextContent, Resource, Prompt
from typing import List, Dict, Any, Optional
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionError(Exception):
    """Raised when connection to the server fails."""
    pass

class McpClient:
    def __init__(self, url: str, auth_token: str = None, timeout: float = 10.0):
        self.url = url
        self.session = None
        # Enhanced headers with proper Authorization format
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'User-Agent': 'MCP-Client/1.0',
            'Connection': 'keep-alive'
        }
        
        # Add Authorization header if token is provided
        if auth_token:
            self.headers['Authorization'] = f'Bearer {auth_token}'
            
        self.stream_context = None
        self.read_stream = None
        self.write_stream = None
        self.timeout = timeout

    async def init(self):
        try:
            async with asyncio.timeout(self.timeout):
                logger.info(f"Connecting to {self.url}")
                logger.info(f"Using headers: {self.headers}")
                self.stream_context = streamablehttp_client(
                    self.url,
                    headers=self.headers
                )
                self.read_stream, self.write_stream, _ = await self.stream_context.__aenter__()

                logger.info("Initializing session")
                self.session = ClientSession(self.read_stream, self.write_stream)
                await self.session.__aenter__()
                await self.session.initialize()

                logger.info("Connection established successfully")
                return self

        except asyncio.TimeoutError:
            logger.error(f"Connection timed out after {self.timeout} seconds")
            await self.cleanup()
            raise ConnectionError(f"Connection timed out after {self.timeout} seconds")
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            await self.cleanup()
            raise

    async def cleanup(self):
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if self.stream_context:
                await self.stream_context.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def get_tools(self) -> List[Tool]:
        try:
            async with asyncio.timeout(self.timeout):
                response = await self.session.list_tools()
                return response.tools
        except asyncio.TimeoutError:
            logger.error(f"Get tools operation timed out after {self.timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"Error getting tools list: {e}")
            raise

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> str:
        try:
            async with asyncio.timeout(self.timeout):
                logger.info(f"Calling tool: {tool_name} with params: {params}")
                result = await self.session.call_tool(tool_name, params)
                logger.info(f"Raw tool call result: {result}")

                if hasattr(result, 'content') and result.content:
                    for content in result.content:
                        if isinstance(content, TextContent):
                            return content.text
                return str(result)
        except asyncio.TimeoutError:
            logger.error(f"Tool call operation timed out after {self.timeout} seconds")
            # Return a friendly error instead of raising exception
            return f"Operation timed out after {self.timeout} seconds"
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            # Return a friendly error instead of raising exception
            return f"Error calling tool {tool_name}: {str(e)}"

    async def get_resources(self) -> List[Resource]:
        try:
            async with asyncio.timeout(self.timeout):
                response = await self.session.list_resources()
                logger.info(f"Raw resources response: {response}")
                if isinstance(response, list):
                    return [Resource(**r) if isinstance(r, dict) else r for r in response]
                elif hasattr(response, 'resources'):
                    return response.resources
                else:
                    raise ValueError("Unexpected response format for resources")
        except asyncio.TimeoutError:
            logger.error(f"Get resources operation timed out after {self.timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"Error getting resources list: {e}")
            raise

    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        try:
            async with asyncio.timeout(self.timeout):
                resource = await self.session.read_resource(resource_id)
                logger.info(f"Raw resource response: {resource}")
                return Resource(**resource) if isinstance(resource, dict) else resource
        except asyncio.TimeoutError:
            logger.error(f"Get resource operation timed out after {self.timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"Error getting resource {resource_id}: {e}")
            raise

    async def get_prompts(self) -> List[Prompt]:
        try:
            async with asyncio.timeout(self.timeout):
                response = await self.session.list_prompts()
                logger.info(f"Raw prompts response: {response}")
                if isinstance(response, list):
                    return [Prompt(**p) if isinstance(p, dict) else p for p in response]
                elif hasattr(response, 'prompts'):
                    return response.prompts
                else:
                    raise ValueError("Unexpected response format for prompts")
        except asyncio.TimeoutError:
            logger.error(f"Get prompts operation timed out after {self.timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"Error getting prompts list: {e}")
            raise

    async def get_prompt(self, prompt_id: str) -> Optional[Prompt]:
        try:
            async with asyncio.timeout(self.timeout):
                prompt = await self.session.get_prompt(prompt_id)
                logger.info(f"Raw prompt response: {prompt}")
                return Prompt(**prompt) if isinstance(prompt, dict) else prompt
        except asyncio.TimeoutError:
            logger.error(f"Get prompt operation timed out after {self.timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"Error getting prompt {prompt_id}: {e}")
            raise