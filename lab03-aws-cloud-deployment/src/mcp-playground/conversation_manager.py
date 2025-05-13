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
        self.pending_processing = False  # Flag to indicate if we're in the middle of processing tools
        self.max_retries = 3  # Maximum number of retries for failed tool calls
        self.error_counts = {}  # Track errors per tool to avoid infinite loops
        logger.debug("ConversationManager initialized")
    
    def add_user_message(self, content: str) -> Dict[str, Any]:
        """
        Add a user message to the conversation history.
        
        Args:
            content: The message content
            
        Returns:
            The created message object
        """
        # Don't add new user messages if we're still processing tool calls
        if self.pending_processing or self.has_pending_tool_uses():
            logger.warning("Attempted to add user message while tool processing is pending")
            return None
            
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
            
            content_blocks = message.get("content", [])
            tool_use_blocks = []
            text_blocks = []
            
            # First pass - separate text and toolUse blocks
            for content in content_blocks:
                if "text" in content:
                    result["text"] += content["text"]
                    text_blocks.append(content)
                    logger.debug(f"Found text content: {content['text'][:50]}...")
                elif "toolUse" in content:
                    tool_use = content["toolUse"]
                    tool_use_id = tool_use.get("toolUseId")
                    
                    logger.debug(f"Found toolUse with ID: {tool_use_id}, name: {tool_use.get('name')}")
                    
                    # Track this tool use
                    self.tool_calls[tool_use_id] = tool_use
                    self.pending_tool_uses.add(tool_use_id)
                    tool_use_blocks.append(content)
                    result["tool_uses"].append(tool_use)
                    
                    # Initialize error count for this tool
                    self.error_counts[tool_use_id] = 0
            
            # If we have any tool uses, set the processing flag
            if tool_use_blocks:
                self.pending_processing = True
                
            # Add the message with all content (text and toolUse blocks)
            if content_blocks:
                self.messages.append({
                    "role": "assistant",
                    "content": content_blocks
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
        
        # Check if the result indicates an error
        is_error = False
        if "error" in result:
            is_error = True
            logger.warning(f"Tool result contains error: {result.get('error')}")
            
            # Increment error count for this tool
            self.error_counts[tool_use_id] = self.error_counts.get(tool_use_id, 0) + 1
            
            # If we've exceeded max retries, add error result and continue
            if self.error_counts[tool_use_id] > self.max_retries:
                logger.error(f"Exceeded maximum retries ({self.max_retries}) for tool {tool_use_id}")
                # Continue with error result
            else:
                # We'll keep the tool in pending_tool_uses for retry
                logger.info(f"Will retry tool {tool_use_id} (attempt {self.error_counts[tool_use_id]})")
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
        
        # If we've processed all pending tool uses, clear the processing flag
        if not self.pending_tool_uses:
            self.pending_processing = False
            logger.debug("All tool uses processed, clearing pending processing flag")
            
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
        
        # Check if we're sending messages with pending tool uses
        if self.validate_message_flow():
            # If validation detected issues, we need to ensure we have a clean message set
            self._repair_message_sequence()
        
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
    
    def is_processing_tools(self) -> bool:
        """
        Check if we're currently processing tool uses.
        
        Returns:
            True if we're processing tool uses, False otherwise
        """
        return self.pending_processing
    
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
        
        # Third pass - check if all toolUse have matching toolResult except for the most recent assistant message
        latest_assistant_idx = -1
        for i, msg in enumerate(self.messages):
            if msg.get("role") == "assistant":
                latest_assistant_idx = i
        
        for tool_use_id, use_idx in tool_uses.items():
            if tool_use_id not in tool_results:
                # This is actually ok if it's in the most recent assistant message
                if use_idx != latest_assistant_idx:
                    errors.append(f"Message {use_idx} has toolUse for ID {tool_use_id} but no matching toolResult exists")
        
        if errors:
            logger.warning(f"Message flow validation failed with {len(errors)} errors")
            for error in errors:
                logger.warning(f"Validation error: {error}")
        else:
            logger.debug("Message flow validation passed")
            
        return errors
    
    def _repair_message_sequence(self):
        """
        Attempt to repair the message sequence if it's broken.
        This is a last resort to make the conversation valid for Bedrock.
        """
        # If we have a toolUse without a toolResult, we need to clean it up
        # This is used only in extreme cases where we want to make a clean state
        
        tool_uses = {}  # Map of tool_use_id to (message_idx, content_idx)
        
        # Find all tool uses
        for msg_idx, msg in enumerate(self.messages):
            if msg.get('role') == 'assistant':
                for content_idx, content_item in enumerate(msg.get('content', [])):
                    if isinstance(content_item, dict) and "toolUse" in content_item:
                        tool_use_id = content_item["toolUse"].get("toolUseId")
                        if tool_use_id:
                            tool_uses[tool_use_id] = (msg_idx, content_idx)
        
        # Find the most recent assistant message
        latest_assistant_idx = -1
        for i, msg in enumerate(self.messages):
            if msg.get('role') == 'assistant':
                latest_assistant_idx = i
        
        # If we have a most recent assistant message with tool uses, we need to ensure
        # we don't have any other messages after it until the tool uses are handled
        if latest_assistant_idx >= 0:
            # If there are any messages after the latest assistant message that aren't tool results
            has_non_tool_result = False
            for i in range(latest_assistant_idx + 1, len(self.messages)):
                msg = self.messages[i]
                if msg.get('role') == 'user':
                    if not any('toolResult' in c for c in msg.get('content', [])):
                        has_non_tool_result = True
                        break
            
            # If we found a non-tool result after the assistant message, trim the messages to that point
            if has_non_tool_result:
                logger.warning(f"Found non-tool result messages after assistant message with tool uses, truncating at {latest_assistant_idx + 1}")
                self.messages = self.messages[:latest_assistant_idx + 1]
                
                # Update pending tool uses based on the latest assistant message
                self.pending_tool_uses.clear()
                for content_item in self.messages[latest_assistant_idx].get('content', []):
                    if isinstance(content_item, dict) and "toolUse" in content_item:
                        tool_use_id = content_item["toolUse"].get("toolUseId")
                        if tool_use_id:
                            self.pending_tool_uses.add(tool_use_id)
                            self.tool_calls[tool_use_id] = content_item["toolUse"]
                
                # Set the processing flag since we know we have pending tool uses
                self.pending_processing = True
                
                # Log that we performed repair
                logger.info(f"Repaired message sequence, now have {len(self.pending_tool_uses)} pending tool uses")
    
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
    
    def clear_pending_flags(self):
        """Clear the pending flags but keep the message history"""
        self.pending_tool_uses.clear()
        self.pending_processing = False
        self.error_counts.clear()  # Reset error counts
        logger.debug("Cleared pending flags")
    
    def force_continue(self):
        """
        Force conversation to continue by resolving any pending tool uses with error messages.
        This is used as a fallback when tool processing is stuck.
        """
        if not self.pending_tool_uses:
            return False  # Nothing to do
            
        logger.warning(f"Forcing conversation to continue with {len(self.pending_tool_uses)} pending tools")
        
        # Create error results for all pending tools
        for tool_use_id in list(self.pending_tool_uses):
            tool_use = self.get_tool_use(tool_use_id)
            tool_name = tool_use.get("name", "unknown") if tool_use else "unknown"
            
            # Create a friendly error message
            error_result = {
                "content": f"Error: Unable to complete tool {tool_name} due to connectivity issues. Let's continue the conversation."
            }
            
            # Add the error result
            self.add_tool_result(tool_use_id, error_result)
            
        # Ensure all flags are cleared
        self.clear_pending_flags()
        return True  # We took action
    
    def reset(self):
        """Reset the conversation state"""
        self.messages = []
        self.tool_calls = {}
        self.pending_tool_uses = set()
        self.used_tool_results = set()
        self.pending_processing = False
        self.error_counts = {}
        logger.debug("Conversation manager reset")