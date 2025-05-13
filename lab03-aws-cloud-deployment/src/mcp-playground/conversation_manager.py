"""
Manages the conversation context for Bedrock conversations with tool usage.
Tracks messages, tool usage, and ensures proper pairing of tool calls with results.
"""
from typing import Dict, Any, List
import logging
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
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
        self.used_tool_results = set()  # Track which tool results have been used
        logger.debug("ConversationManager initialized")
    
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
        logger.debug(f"Added user message: {content[:50]}...")
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
        logger.debug(f"Added assistant message: {content[:50]}...")
        return message
    
    def process_bedrock_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a response from Bedrock and extract tool uses.
        
        Args:
            response: The full Bedrock API response
            
        Returns:
            A dict containing extracted data including any tool uses
        """
        logger.debug(f"Processing Bedrock response with stop reason: {response.get('stopReason', 'unknown')}")
        
        result = {
            "text": "",
            "tool_uses": [],
            "stop_reason": response.get("stopReason", "")
        }
        
        # Get output message
        if "output" in response and "message" in response["output"]:
            message = response["output"]["message"]
            logger.debug(f"Found output message with content length: {len(message.get('content', []))}")
            
            # Process each content block
            for content in message.get("content", []):
                if "text" in content:
                    result["text"] += content["text"]
                    logger.debug(f"Found text content: {content['text'][:50]}...")
                elif "toolUse" in content:
                    tool_use = content["toolUse"]
                    tool_use_id = tool_use.get("toolUseId")
                    
                    logger.debug(f"Found toolUse with ID: {tool_use_id}, name: {tool_use.get('name')}")
                    
                    # Track this tool use
                    self.tool_calls[tool_use_id] = tool_use
                    self.pending_tool_uses.add(tool_use_id)
                    result["tool_uses"].append(tool_use)
            
            # Create assistant message if there's text content or toolUse
            # This is a critical change: preserve the entire content array, which may include both text and toolUse
            if message.get("content"):
                self.messages.append({
                    "role": "assistant",
                    "content": message.get("content", [])
                })
        
        # Log the overall status
        logger.debug(f"Processed Bedrock response. Text length: {len(result['text'])}, "
                    f"Tool uses: {len(result['tool_uses'])}, "
                    f"Current pending tool uses: {len(self.pending_tool_uses)}")
        
        # Also log the current full message history for debugging
        logger.debug(f"Current message count: {len(self.messages)}")
        for i, msg in enumerate(self.messages):
            logger.debug(f"Message {i}: role={msg.get('role')}, content_items={len(msg.get('content', []))}")
        
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
        # Validate tool_use_id exists in pending tools
        if tool_use_id not in self.pending_tool_uses:
            logger.warning(f"Adding result for unknown or already processed tool use ID: {tool_use_id}")
            logger.warning(f"Pending tool use IDs: {self.pending_tool_uses}")
            logger.warning(f"All tracked tool use IDs: {list(self.tool_calls.keys())}")
            
            # FIX: Verify that the toolUse exists in the message history
            tool_exists_in_history = False
            for msg in self.messages:
                if msg.get("role") == "assistant":
                    for content_item in msg.get("content", []):
                        if isinstance(content_item, dict) and "toolUse" in content_item:
                            if content_item["toolUse"].get("toolUseId") == tool_use_id:
                                tool_exists_in_history = True
                                # If exists in history but not in pending, re-add it
                                self.pending_tool_uses.add(tool_use_id)
                                self.tool_calls[tool_use_id] = content_item["toolUse"]
                                break
            
            if not tool_exists_in_history:
                logger.error(f"Cannot add tool result for {tool_use_id} - not found in conversation history")
                return None
        
        # Check if we've already added a result for this tool
        if tool_use_id in self.used_tool_results:
            logger.warning(f"Tool result for {tool_use_id} has already been added - skipping")
            return None
            
        logger.info(f"Adding tool result for {tool_use_id}: {json.dumps(result)[:100]}...")
        
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
        
        # Track that we've used this tool result
        self.used_tool_results.add(tool_use_id)
        
        if tool_use_id in self.pending_tool_uses:
            self.pending_tool_uses.remove(tool_use_id)
            logger.debug(f"Removed {tool_use_id} from pending tool uses. Remaining: {len(self.pending_tool_uses)}")
        
        return tool_result_message
    
    def get_bedrock_messages(self) -> List[Dict[str, Any]]:
        """
        Get the messages in Bedrock format.
        
        Returns:
            List of messages in the format expected by Bedrock
        """
        # Debug message counts
        assistant_count = sum(1 for m in self.messages if m.get('role') == 'assistant')
        user_count = sum(1 for m in self.messages if m.get('role') == 'user')
        tool_result_count = sum(
            1 for m in self.messages 
            if m.get('role') == 'user' and any('toolResult' in c for c in m.get('content', []))
        )
        
        logger.debug(f"Getting Bedrock messages: {len(self.messages)} total "
                    f"({assistant_count} assistant, {user_count} user, {tool_result_count} toolResult)")
        
        # Validate the structure for debugging
        has_errors = False
        for i, msg in enumerate(self.messages):
            if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                logger.error(f"Invalid message at index {i}: {msg}")
                has_errors = True
            
            if msg.get('role') == 'user' and any('toolResult' in c for c in msg.get('content', [])):
                for content in msg.get('content', []):
                    if 'toolResult' in content:
                        tool_use_id = content['toolResult'].get('toolUseId')
                        logger.debug(f"Message {i} contains toolResult for ID: {tool_use_id}")
                        
                        # Verify that this tool_use_id was from the assistant
                        tool_found = False
                        for prev_msg in self.messages[:i]:
                            if prev_msg.get('role') == 'assistant':
                                for prev_content in prev_msg.get('content', []):
                                    if isinstance(prev_content, dict) and 'toolUse' in prev_content and prev_content['toolUse'].get('toolUseId') == tool_use_id:
                                        tool_found = True
                                        break
                        
                        if not tool_found:
                            logger.warning(f"toolResult with ID {tool_use_id} has no matching toolUse!")
        
        if has_errors:
            logger.warning("Messages contain errors - see logs above")
        
        return self.messages
    
    def get_tool_use(self, tool_use_id: str) -> Dict[str, Any]:
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
    
    def validate_message_flow(self) -> List[str]:
        """
        Validate the message flow for Bedrock compatibility.
        
        Returns:
            List of error messages if any issues are found, empty list if valid
        """
        errors = []
        tool_uses = {}  # Map of tool_use_id to message index
        tool_results = {}  # Map of tool_use_id to message index
        
        # First pass - collect all toolUse and toolResult occurrences
        for i, msg in enumerate(self.messages):
            if msg.get('role') == 'assistant':
                for content_item in msg.get('content', []):
                    if isinstance(content_item, dict) and "toolUse" in content_item:
                        tool_use_id = content_item["toolUse"].get("toolUseId")
                        if tool_use_id:
                            tool_uses[tool_use_id] = i
            elif msg.get('role') == 'user':
                for content_item in msg.get('content', []):
                    if isinstance(content_item, dict) and "toolResult" in content_item:
                        tool_use_id = content_item["toolResult"].get("toolUseId")
                        if tool_use_id:
                            tool_results[tool_use_id] = i
        
        # Second pass - validate toolResult has matching toolUse
        for tool_use_id, result_idx in tool_results.items():
            if tool_use_id not in tool_uses:
                errors.append(f"Message {result_idx} has toolResult for ID {tool_use_id} but no matching toolUse exists")
            else:
                use_idx = tool_uses[tool_use_id]
                if use_idx >= result_idx:
                    errors.append(f"Message {result_idx} has toolResult for ID {tool_use_id} but toolUse appears after it at message {use_idx}")
        
        # Third pass - check if all toolUse have matching toolResult
        for tool_use_id, use_idx in tool_uses.items():
            if tool_use_id not in tool_results:
                # This is actually ok if it's the most recent assistant message
                if use_idx != max(idx for idx, msg in enumerate(self.messages) if msg.get('role') == 'assistant'):
                    errors.append(f"Message {use_idx} has toolUse for ID {tool_use_id} but no matching toolResult exists")
        
        if errors:
            logger.warning(f"Message flow validation failed with {len(errors)} errors")
            for error in errors:
                logger.warning(f"Validation error: {error}")
        else:
            logger.debug("Message flow validation passed")
            
        return errors
    
    def remove_cache_checkpoint(self, messages: list) -> list:
        """
        Remove cachePoint blocks from messages while preserving toolUse blocks.
        
        Args:
            messages (list): A list of message dictionaries.
            
        Returns:
            list: The modified messages list with cachePoint blocks removed but toolUse preserved.
        """
        for message in messages:
            if "content" in message and isinstance(message["content"], list):
                # First, identify any toolUse blocks that need to be preserved
                tool_use_blocks = [item for item in message["content"] 
                                  if isinstance(item, dict) and "toolUse" in item]
                
                # Remove cachePoint blocks but preserve everything else
                message["content"] = [item for item in message["content"] 
                                     if isinstance(item, dict) and "cachePoint" not in item]
                
                # If any toolUse blocks were removed (which shouldn't happen), log and add them back
                current_tool_use_blocks = [item for item in message["content"] 
                                          if isinstance(item, dict) and "toolUse" in item]
                missing_tool_blocks = [block for block in tool_use_blocks 
                                      if block not in current_tool_use_blocks]
                
                if missing_tool_blocks:
                    logger.warning(f"Found {len(missing_tool_blocks)} toolUse blocks that were incorrectly removed - restoring them")
                    message["content"].extend(missing_tool_blocks)
        
        return messages
    
    def reset(self):
        """Reset the conversation state"""
        self.messages = []
        self.tool_calls = {}
        self.pending_tool_uses = set()
        self.used_tool_results = set()
        logger.debug("Conversation manager reset")