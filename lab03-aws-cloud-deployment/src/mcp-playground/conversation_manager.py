"""
Manages the conversation context for Bedrock conversations with tool usage.
Implements a state machine for more predictable conversation flow.
"""
from typing import Dict, Any, List, Set, Optional
import logging
import json
import time
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

class ConversationState(Enum):
    """Enum defining the possible states of the conversation manager."""
    IDLE = "idle"                             # No active processing
    WAITING_FOR_RESPONSE = "waiting"          # Waiting for Bedrock response
    PROCESSING_TOOLS = "processing_tools"     # Processing tool calls
    CONTINUING = "continuing"                 # Continuing conversation after tools
    ERROR = "error"                           # Error state

class ConversationManager:
    """
    Manages the conversation context for Bedrock conversations with tool usage.
    Implements a state machine for more predictable processing flow.
    """
    
    def __init__(self):
        """Initialize the conversation manager with empty state"""
        # Conversation content
        self.messages = []                         # All conversation messages
        self.tool_calls = {}                       # Map of tool_use_id to tool call details
        
        # State tracking
        self.state = ConversationState.IDLE        # Current state
        self.pending_tool_uses = set()             # Set of tool_use_ids that need results
        self.used_tool_results = set()             # Track which tool results have been used
        self.current_tool_use_id = None            # Currently processing tool ID
        
        # Error handling
        self.max_retries = 3                       # Maximum number of retries for failed tool calls
        self.error_counts = {}                     # Track errors per tool to avoid infinite loops
        self.last_error = None                     # Last error message
        
        # Performance monitoring
        self.state_transition_time = None          # Time of last state transition
        
        logger.info("ConversationManager initialized in IDLE state")
    
    def transition_to(self, new_state: ConversationState) -> None:
        """
        Transition to a new state with logging and time tracking.
        
        Args:
            new_state: The state to transition to
        """
        old_state = self.state
        self.state = new_state
        self.state_transition_time = time.time()
        
        logger.info(f"State transition: {old_state.value} -> {new_state.value}")
        
        # Perform state entry actions
        if new_state == ConversationState.IDLE:
            # Clear processing state but maintain conversation
            self.pending_tool_uses.clear()
            self.current_tool_use_id = None
            self.last_error = None
        
        # Log the current conversation state for debugging
        logger.info(f"Conversation state: {len(self.messages)} messages, {len(self.pending_tool_uses)} pending tools")
    
    def add_user_message(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Add a user message to the conversation history.
        
        Args:
            content: The message content
            
        Returns:
            The created message object or None if in invalid state
        """
        # Only add new user messages in IDLE state
        if self.state != ConversationState.IDLE:
            logger.warning(f"Cannot add user message in {self.state.value} state")
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
        logger.info(f"Added user message of {len(content)} chars")
        logger.debug(f"User message content: {content[:100]}...")
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
        logger.info(f"Added assistant message of {len(content)} chars")
        logger.debug(f"Assistant message content: {content[:100]}...")
        return message
    
    def process_bedrock_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a response from Bedrock and extract tool uses.
        
        Args:
            response: The full Bedrock API response
            
        Returns:
            A dict containing extracted data including any tool uses
        """
        stop_reason = response.get("stopReason", "unknown")
        logger.info(f"Processing Bedrock response with stop reason: {stop_reason}")
        
        result = {
            "text": "",
            "tool_uses": [],
            "stop_reason": stop_reason
        }
        
        # Get output message
        if "output" in response and "message" in response["output"]:
            message = response["output"]["message"]
            logger.info(f"Found output message with content length: {len(message.get('content', []))}")
            
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
                    
                    logger.info(f"Found toolUse with ID: {tool_use_id}, name: {tool_use.get('name')}")
                    
                    # Track this tool use
                    self.tool_calls[tool_use_id] = tool_use
                    self.pending_tool_uses.add(tool_use_id)
                    tool_use_blocks.append(content)
                    result["tool_uses"].append(tool_use)
                    
                    # Initialize error count for this tool
                    self.error_counts[tool_use_id] = 0
            
            # Add the message with all content (text and toolUse blocks)
            if content_blocks:
                self.messages.append({
                    "role": "assistant",
                    "content": content_blocks
                })
            
            # If we have any tool uses, transition to PROCESSING_TOOLS state
            if tool_use_blocks:
                self.transition_to(ConversationState.PROCESSING_TOOLS)
            else:
                # If no tool uses, go back to IDLE state
                self.transition_to(ConversationState.IDLE)
        
        # Log the overall status
        logger.info(f"Processed Bedrock response. Text: {len(result['text'])} chars, "
                    f"Tool uses: {len(result['tool_uses'])}, "
                    f"Current pending tool uses: {len(self.pending_tool_uses)}")
        
        return result
    
    def add_tool_result(self, tool_use_id: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Add a tool result for a previous tool use.
        
        Args:
            tool_use_id: The tool use ID to match
            result: The result from the tool
            
        Returns:
            The created tool result message or None if invalid
        """
        logger.info(f"Adding tool result for {tool_use_id}")
        
        # Validate tool_use_id exists in pending tools
        if tool_use_id not in self.pending_tool_uses:
            logger.warning(f"Adding result for unknown or already processed tool use ID: {tool_use_id}")
            
            # Verify that the toolUse exists in the message history
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
            logger.info(f"Removed {tool_use_id} from pending tool uses. Remaining: {len(self.pending_tool_uses)}")
        
        # Clear the current tool use ID
        if self.current_tool_use_id == tool_use_id:
            self.current_tool_use_id = None
        
        # If we've processed all pending tool uses, transition to CONTINUING state
        if not self.pending_tool_uses and self.state == ConversationState.PROCESSING_TOOLS:
            logger.info("All tool uses processed, transitioning to CONTINUING state")
            self.transition_to(ConversationState.CONTINUING)
            
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
        
        logger.info(f"Getting Bedrock messages: {len(self.messages)} total "
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
        
        if has_errors:
            logger.warning("Messages contain errors - see logs above")
            # Auto-repair if issues found
            self._repair_message_sequence()
        
        # Clean up any cache points from messages
        self.messages = self.remove_cache_checkpoint(self.messages)
        
        return self.messages
    
    def get_tool_use(self, tool_use_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific tool use by ID.
        
        Args:
            tool_use_id: The tool use ID
            
        Returns:
            The tool use details or None if not found
        """
        tool_use = self.tool_calls.get(tool_use_id)
        if not tool_use:
            logger.warning(f"Tool use not found for ID: {tool_use_id}")
        return tool_use
    
    def get_next_pending_tool_id(self) -> Optional[str]:
        """
        Get the next pending tool ID to process.
        
        Returns:
            The next tool use ID or None if no pending tools
        """
        if not self.pending_tool_uses:
            logger.debug("No pending tool uses to process")
            return None
        
        # Get the next tool from the pending set
        tool_use_id = next(iter(self.pending_tool_uses))
        self.current_tool_use_id = tool_use_id
        logger.info(f"Selected next pending tool: {tool_use_id}")
        return tool_use_id
    
    def has_pending_tool_uses(self) -> bool:
        """
        Check if there are pending tool uses without results.
        
        Returns:
            True if there are pending tool uses, False otherwise
        """
        return len(self.pending_tool_uses) > 0
    
    def is_processing_tools(self) -> bool:
        """
        Check if we're currently in the tool processing state.
        
        Returns:
            True if we're processing tool uses, False otherwise
        """
        return self.state == ConversationState.PROCESSING_TOOLS
    
    def is_continuing(self) -> bool:
        """
        Check if we're in the continuing state.
        
        Returns:
            True if we're continuing after tool processing, False otherwise
        """
        return self.state == ConversationState.CONTINUING
    
    def is_idle(self) -> bool:
        """
        Check if we're in the idle state.
        
        Returns:
            True if we're idle, False otherwise
        """
        return self.state == ConversationState.IDLE
    
    def is_in_error_state(self) -> bool:
        """
        Check if we're in an error state.
        
        Returns:
            True if we're in an error state, False otherwise
        """
        return self.state == ConversationState.ERROR
    
    def _repair_message_sequence(self) -> None:
        """
        Attempt to repair the message sequence if it's broken.
        This is a last resort to make the conversation valid for Bedrock.
        """
        logger.warning("Attempting to repair message sequence")
        
        # For each message, ensure it has a role and content
        for i, msg in enumerate(self.messages):
            if not isinstance(msg, dict):
                logger.error(f"Invalid message at index {i}, removing")
                self.messages[i] = None
                continue
                
            if 'role' not in msg:
                logger.error(f"Message at index {i} has no role, adding default")
                msg['role'] = 'user'
                
            if 'content' not in msg or not isinstance(msg['content'], list):
                logger.error(f"Message at index {i} has invalid content, fixing")
                # If no content, add empty content
                if 'content' not in msg:
                    msg['content'] = []
                # If content is not a list, wrap it
                elif not isinstance(msg['content'], list):
                    msg['content'] = [{"text": str(msg['content'])}]
                    
        # Remove None messages
        self.messages = [msg for msg in self.messages if msg is not None]
        
        # Ensure we don't have user->user or assistant->assistant sequences
        i = 1
        while i < len(self.messages):
            prev_role = self.messages[i-1].get('role')
            curr_role = self.messages[i].get('role')
            
            if prev_role == curr_role:
                logger.warning(f"Found {prev_role}->{curr_role} sequence at index {i}, merging")
                # Merge content from current message into previous
                self.messages[i-1]['content'].extend(self.messages[i].get('content', []))
                # Remove current message
                self.messages.pop(i)
            else:
                i += 1
                
        logger.info(f"Repair complete, now have {len(self.messages)} messages")
    
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
    
    def force_continue(self) -> bool:
        """
        Force conversation to continue by resolving any pending tool uses with error messages.
        This is used as a fallback when tool processing is stuck.
        
        Returns:
            True if action was taken, False otherwise
        """
        logger.warning(f"Forcing conversation to continue from state {self.state.value}")
        
        # If in error state or idle, nothing to do
        if self.state == ConversationState.ERROR or self.state == ConversationState.IDLE:
            logger.info(f"No need to force continue in {self.state.value} state")
            return False
            
        # Handle pending tool uses with error messages
        if self.pending_tool_uses:
            logger.warning(f"Resolving {len(self.pending_tool_uses)} pending tools with error messages")
            
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
        
        # Transition to CONTINUING state to ensure we get a final response
        self.transition_to(ConversationState.CONTINUING)
        return True
    
    def reset(self) -> None:
        """Reset the conversation state completely"""
        self.messages = []
        self.tool_calls = {}
        self.pending_tool_uses = set()
        self.used_tool_results = set()
        self.current_tool_use_id = None
        self.error_counts = {}
        self.last_error = None
        self.state = ConversationState.IDLE
        logger.info("Conversation manager reset to initial state")
    
    def get_state_duration(self) -> float:
        """
        Get the duration in seconds that we've been in the current state.
        
        Returns:
            Duration in seconds or 0 if no transition time
        """
        if not self.state_transition_time:
            return 0
            
        return time.time() - self.state_transition_time
    
    def handle_timeout(self, max_duration: float = 60.0) -> bool:
        """
        Handle timeouts in the current state.
        
        Args:
            max_duration: Maximum allowed duration in a state in seconds
            
        Returns:
            True if a timeout was handled, False otherwise
        """
        if self.get_state_duration() > max_duration:
            logger.warning(f"Timeout detected in state {self.state.value} after {self.get_state_duration():.1f} seconds")
            
            if self.state == ConversationState.PROCESSING_TOOLS:
                # Force continue from a stuck processing state
                return self.force_continue()
                
            elif self.state == ConversationState.WAITING_FOR_RESPONSE:
                # Timeout waiting for response, go to error state
                self.last_error = "Timed out waiting for Bedrock response"
                self.transition_to(ConversationState.ERROR)
                return True
                
            elif self.state == ConversationState.CONTINUING:
                # Timeout in continuing state, go back to idle
                self.transition_to(ConversationState.IDLE)
                return True
                
        return False