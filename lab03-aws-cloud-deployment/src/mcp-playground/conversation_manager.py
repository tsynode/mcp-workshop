from typing import List, Dict, Any, Optional
import logging
import uuid

logger = logging.getLogger(__name__)

class ConversationManager:
    """
    Manages the conversation context for Bedrock conversations with tool usage.
    Tracks messages, tool usage, and ensures proper pairing of tool calls with results.
    """
    
    def __init__(self):
        """Initialize the conversation manager with empty state"""
        self.messages = []
        self.tool_calls = {}  # Map of tool_use_id to tool call details
        self.pending_tool_uses = set()  # Set of tool_use_ids that need results
    
    def add_user_message(self, content: str) -> Dict[str, Any]:
        """
        Add a user message to the conversation history.
        
        Args:
            content: The message content
            
        Returns:
            The created message object
        """
        message = {
            "role": "user",
            "content": [
                {
                    "text": content
                }
            ]
        }
        
        self.messages.append(message)
        return message
    
    def add_assistant_message(self, content: str) -> Dict[str, Any]:
        """
        Add an assistant message to the conversation history.
        
        Args:
            content: The message content
            
        Returns:
            The created message object
        """
        message = {
            "role": "assistant",
            "content": [
                {
                    "text": content
                }
            ]
        }
        
        self.messages.append(message)
        return message
    
    def process_bedrock_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a response from Bedrock and extract tool uses.
        
        Args:
            response: The full Bedrock API response
            
        Returns:
            A dict containing extracted data including any tool uses
        """
        result = {
            "text": "",
            "tool_uses": [],
            "stop_reason": response.get("stopReason", "")
        }
        
        # Get output message
        if "output" in response and "message" in response["output"]:
            message = response["output"]["message"]
            
            # Process each content block
            for content in message.get("content", []):
                if "text" in content:
                    result["text"] += content["text"]
                elif "toolUse" in content:
                    tool_use = content["toolUse"]
                    tool_use_id = tool_use.get("toolUseId")
                    
                    # Track this tool use
                    self.tool_calls[tool_use_id] = tool_use
                    self.pending_tool_uses.add(tool_use_id)
                    result["tool_uses"].append(tool_use)
            
            # Create assistant message if there's text content
            if result["text"]:
                self.add_assistant_message(result["text"])
        
        return result
    
    def add_tool_result(self, tool_use_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a tool result for a previous tool use.
        
        Args:
            tool_use_id: The tool use ID to match
            result: The result from the tool
            
        Returns:
            The created tool result message
        """
        if tool_use_id not in self.pending_tool_uses:
            logger.warning(f"Adding result for unknown tool use ID: {tool_use_id}")
        
        # Format content for the tool result
        content_value = result.get("content", "")
        if isinstance(content_value, str):
            result_content = {"text": content_value}
        else:
            result_content = {"json": content_value}
        
        # Create the toolResult message
        tool_result_message = {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [result_content]
                    }
                }
            ]
        }
        
        # Add to conversation and remove from pending
        self.messages.append(tool_result_message)
        if tool_use_id in self.pending_tool_uses:
            self.pending_tool_uses.remove(tool_use_id)
        
        return tool_result_message
    
    def get_bedrock_messages(self) -> List[Dict[str, Any]]:
        """
        Get the messages in Bedrock format.
        
        Returns:
            List of messages in the format expected by Bedrock
        """
        return self.messages
    
    def get_tool_use(self, tool_use_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific tool use by ID.
        
        Args:
            tool_use_id: The tool use ID
            
        Returns:
            The tool use details or None if not found
        """
        return self.tool_calls.get(tool_use_id)
    
    def has_pending_tool_uses(self) -> bool:
        """
        Check if there are pending tool uses without results.
        
        Returns:
            True if there are pending tool uses, False otherwise
        """
        return len(self.pending_tool_uses) > 0
    
    def reset(self):
        """Reset the conversation state"""
        self.messages = []
        self.tool_calls = {}
        self.pending_tool_uses = set()