import streamlit as st
import boto3
import json
import os
import subprocess
import uuid
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Tuple, Optional
import traceback
import logging
import time

# Import the refactored conversation manager
from conversation_manager import ConversationManager, ConversationState

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Configure page
st.set_page_config(page_title="Remote MCP Demo", layout="wide")

# Get commit ID if available
try:
    commit_id = os.environ.get('COMMIT_ID', None)
    if not commit_id:
        # Try to get it from git if running locally
        try:
            result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  text=True,
                                  timeout=1)
            if result.returncode == 0:
                commit_id = result.stdout.strip()
            else:
                commit_id = 'unknown'
        except Exception:
            commit_id = 'unknown'
except Exception:
    commit_id = 'unknown'

# Set up Bedrock client
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-west-2'
)

# Initialize session state
if 'conversation_manager' not in st.session_state:
    st.session_state.conversation_manager = ConversationManager()

if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []

if 'custom_mcp_servers' not in st.session_state:
    st.session_state.custom_mcp_servers = {}

# Initialize tool mapping if not present
if 'tool_mapping' not in st.session_state:
    st.session_state.tool_mapping = {}

# Initialize form reset state if not present
if 'reset_form' not in st.session_state:
    st.session_state.reset_form = False

# Add auth_token to session state if not present
if 'auth_token' not in st.session_state:
    st.session_state.auth_token = ""

# Helper function to run async code safely in Streamlit
def run_async(coro):
    """Run an async function from sync code safely"""
    executor = ThreadPoolExecutor(max_workers=1)
    
    def wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
            return result
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                if not task.done():
                    logger.warning(f"Cancelling pending task: {task}")
                    task.cancel()
            
            # Wait for tasks to cancel with timeout
            if pending:
                try:
                    loop.run_until_complete(asyncio.wait(pending, timeout=2.0))
                except asyncio.CancelledError:
                    pass

            loop.close()
    
    return executor.submit(wrapper).result()

# Initialize server information
if 'server_info' not in st.session_state:
    st.session_state.server_info = {}
    
    # Get from environment variables
    product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL')
    order_server_url = os.environ.get('ORDER_MCP_SERVER_URL')
    
    if product_server_url:
        st.session_state.server_info['product-server'] = {
            'url': product_server_url,
            'token': None,
            'status': 'registered',
            'tool_count': 0
        }
    
    if order_server_url:
        st.session_state.server_info['order-server'] = {
            'url': order_server_url,
            'token': None,
            'status': 'registered',
            'tool_count': 0
        }

# ------------------------------------------------
# PURE DATA FUNCTIONS - No Streamlit dependencies
# ------------------------------------------------

async def fetch_tools_from_server(url: str, auth_token: str = None, timeout: float = 10.0) -> Tuple[List[Dict], int]:
    """
    Pure data function to fetch tools from an MCP server.
    No Streamlit references here!
    
    Returns:
        Tuple of (list of tool data, count of tools)
    """
    from mcp_client import McpClient  # Import here to avoid module-level dependencies
    
    client = McpClient(url, auth_token, timeout=timeout)
    tools_data = []
    
    try:
        # Initialize the client
        await client.init()
        
        # Get tools
        tools = await client.get_tools()
        logger.info(f"Fetched {len(tools)} tools from {url}")
        
        # Process tools
        tool_count = 0
        for tool in tools:
            # Handle both object and dictionary formats
            if hasattr(tool, 'name'):
                tool_name = tool.name
                schema = getattr(tool, 'inputSchema', {})
                description = getattr(tool, 'description', '')
                logger.info(f"Processing tool (object): {tool_name}")
            elif isinstance(tool, dict):
                tool_name = tool.get('name', '')
                schema = tool.get('inputSchema', {})
                description = tool.get('description', '')
                logger.info(f"Processing tool (dict): {tool_name}")
            else:
                # Try a last resort approach
                try:
                    tool_name = str(tool)
                    schema = {}
                    description = "Unknown tool format"
                    logger.info(f"Processing tool (unknown format): {tool_name}")
                except:
                    logger.warning(f"Could not process tool: {tool}")
                    continue  # Skip this tool
                
            if not tool_name:
                logger.warning("Found tool without a name, skipping")
                continue  # Skip tools without a name
            
            # Add to tools data list
            tools_data.append({
                'name': tool_name,
                'schema': schema,
                'description': description
            })
            
            tool_count += 1
            
        logger.info(f"Successfully processed {tool_count} tools from {url}")
        return tools_data, tool_count
        
    except Exception as e:
        logger.error(f"Error fetching tools from {url}: {e}")
        logger.error(traceback.format_exc())
        return [], 0
    finally:
        # Always cleanup
        await client.cleanup()

async def execute_mcp_tool(url: str, tool_name: str, params: Dict, auth_token: str = None, timeout: float = 10.0) -> Tuple[Dict, str]:
    """
    Pure data function to execute a tool on an MCP server.
    No Streamlit references here!
    
    Returns:
        Tuple of (result dict or None, error string or None)
    """
    from mcp_client import McpClient  # Import here to avoid module-level dependencies
    
    client = McpClient(url, auth_token, timeout=timeout)
    
    try:
        # Initialize the client
        await client.init()
        logger.info(f"Executing tool {tool_name} on {url} with params: {json.dumps(params)}")
        
        # Call tool
        result_text = await client.call_tool(tool_name, params)
        logger.info(f"Tool {tool_name} execution result: {result_text}")
        
        # Check if result contains an error message
        if isinstance(result_text, str) and (result_text.startswith("Error") or "error" in result_text.lower()):
            error_msg = result_text
            return {"content": f"Error executing {tool_name}: {error_msg}"}, error_msg
        
        # Return success
        return {"content": result_text}, None
        
    except Exception as e:
        error_msg = f"Error calling tool {tool_name}: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return {"content": f"Error: {error_msg}"}, error_msg
    finally:
        # Always cleanup
        try:
            await client.cleanup()
        except Exception as e:
            logger.warning(f"Error during client cleanup: {e}")

# ------------------------------------------------
# STREAMLIT INTERFACE FUNCTIONS
# ------------------------------------------------

def discover_tools(server_name: str, server_url: str, auth_token: str = None) -> int:
    """
    Streamlit-friendly wrapper for tool discovery.
    All Streamlit operations happen here in the main thread.
    """
    try:
        logger.info(f"Discovering tools from {server_name} at {server_url}")
        
        # Call the pure data function
        start_time = time.time()
        tools_data, tool_count = run_async(fetch_tools_from_server(server_url, auth_token))
        duration = time.time() - start_time
        
        logger.info(f"Tool discovery took {duration:.2f} seconds, found {tool_count} tools")
        
        # Update server status in session state
        if server_name in st.session_state.server_info:
            st.session_state.server_info[server_name]['status'] = 'ready' if tool_count > 0 else 'error'
            st.session_state.server_info[server_name]['tool_count'] = tool_count
        
        # Update tool mapping in session state
        for tool_data in tools_data:
            tool_name = tool_data['name']
            # Create Bedrock-compatible name
            bedrock_name = f"{server_name}_{tool_name.replace('-', '_')}"
            
            st.session_state.tool_mapping[bedrock_name] = {
                'server': server_name,
                'url': server_url,
                'token': auth_token,
                'method': tool_name,
                'schema': tool_data['schema'],
                'description': tool_data['description']
            }
            logger.info(f"Added tool mapping: {bedrock_name} -> {server_name}.{tool_name}")
        
        return tool_count
    except Exception as e:
        logger.error(f"Error in discover_tools for {server_name}: {e}")
        logger.error(traceback.format_exc())
        if server_name in st.session_state.server_info:
            st.session_state.server_info[server_name]['status'] = 'error'
        return 0

def call_tool(bedrock_tool_name: str, params: Dict) -> Dict:
    """
    Streamlit-friendly wrapper for tool calling.
    All Streamlit operations happen here in the main thread.
    """
    if bedrock_tool_name not in st.session_state.tool_mapping:
        logger.warning(f"Unknown tool requested: {bedrock_tool_name}")
        return {"content": f"Error: Unknown tool: {bedrock_tool_name}"}
    
    mapping = st.session_state.tool_mapping[bedrock_tool_name]
    server_url = mapping['url']
    method_name = mapping['method']
    auth_token = mapping.get('token') or st.session_state.auth_token  # Use global token if not provided in mapping
    
    logger.info(f"Call_tool - Bedrock tool: {bedrock_tool_name}, MCP method: {method_name}, Server: {server_url}")
    
    try:
        # Record start time for performance tracking
        start_time = time.time()
        
        # Call the pure data function
        result, error = run_async(execute_mcp_tool(server_url, method_name, params, auth_token))
        
        # Calculate duration
        duration = time.time() - start_time
        logger.info(f"Tool execution took {duration:.2f} seconds")
        
        # Add to processing history
        st.session_state.processing_history.append({
            'tool': bedrock_tool_name,
            'duration': duration,
            'timestamp': time.time(),
            'status': 'error' if error else 'success'
        })
        
        if error:
            logger.error(f"Tool execution error: {error}")
            return {"content": f"Error executing {method_name}: {error}"}
            
        logger.info(f"Tool execution successful - Result: {json.dumps(result)[:200]}...")
        return result
    except Exception as e:
        logger.error(f"Error in call_tool for {bedrock_tool_name}: {e}")
        logger.error(traceback.format_exc())
        # Return friendly error instead of raising exception
        return {"content": f"Error executing {method_name}: {str(e)}"}

def get_bedrock_tool_config() -> Dict:
    """Get tool configuration for Bedrock"""
    tool_specs = []
    
    for bedrock_name, mapping in st.session_state.tool_mapping.items():
        server_name = mapping['server']
        method_name = mapping['method']
        description = mapping.get('description', '')
        input_schema = mapping.get('schema', {})
        
        # Create tool spec for Bedrock
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
    
    logger.info(f"Generated Bedrock tool config with {len(tool_specs)} tools")
    return {"tools": tool_specs}

# ------------------------------------------------
# STATE MACHINE IMPLEMENTATION
# ------------------------------------------------

def process_conversation_state():
    """
    Process the current conversation state and take appropriate actions.
    This is the main state machine function that drives the conversation flow.
    """
    conversation_manager = st.session_state.conversation_manager
    current_state = conversation_manager.state
    
    logger.info(f"Processing conversation in state: {current_state.value}")
    
    # Handle timeouts in all states
    conversation_manager.handle_timeout(max_duration=120.0)
    
    # Process state-specific actions
    if current_state == ConversationState.PROCESSING_TOOLS:
        process_tool_use()
    elif current_state == ConversationState.CONTINUING:
        continue_conversation()
    elif current_state == ConversationState.ERROR:
        # Just display error state, user will need to reset
        pass
    elif current_state == ConversationState.WAITING_FOR_RESPONSE:
        # Nothing to do, waiting for async response
        pass
    
    # Check state again in case it changed
    if conversation_manager.state != current_state:
        logger.info(f"State changed during processing from {current_state.value} to {conversation_manager.state.value}")
        # If state changed, process the new state
        st.rerun()

def process_tool_use():
    """
    Process a single tool use from the pending queue.
    Part of the state machine implementation.
    """
    conversation_manager = st.session_state.conversation_manager
    
    # Get the next tool to process
    tool_use_id = conversation_manager.get_next_pending_tool_id()
    
    if not tool_use_id:
        logger.info("No more pending tools to process")
        # No more tools to process, transition to continuing state
        conversation_manager.transition_to(ConversationState.CONTINUING)
        # Process continuing state immediately
        continue_conversation()
        return
    
    # Get the tool use details
    tool_use = conversation_manager.get_tool_use(tool_use_id)
    
    if not tool_use:
        logger.error(f"Failed to get tool use details for {tool_use_id}")
        # Force continue to recover
        conversation_manager.force_continue()
        return
    
    tool_name = tool_use.get("name", "unknown")
    tool_input = tool_use.get("input", {})
    
    logger.info(f"Processing tool: {tool_name} (ID: {tool_use_id})")
    st.session_state.processing_history.append({
        'tool': tool_name,
        'start_time': time.time(),
        'status': 'processing'
    })
    
    with st.status(f"Executing tool {tool_name}...", expanded=False) as status:
        try:
            # Execute the tool
            tool_result = call_tool(tool_name, tool_input)
            
            # Add the result to the conversation
            result_message = conversation_manager.add_tool_result(tool_use_id, tool_result)
            
            if result_message is None:
                logger.error(f"Failed to add tool result for {tool_use_id}")
                status.update(label=f"Error with {tool_name}", state="error")
            else:
                status.update(label=f"Completed {tool_name}", state="complete")
                logger.info(f"Successfully processed tool {tool_name}")
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            logger.error(traceback.format_exc())
            status.update(label=f"Error with {tool_name}: {str(e)}", state="error")
            
            # Create error result to allow conversation to continue
            error_result = {"content": f"Error executing {tool_name}: {str(e)}"}
            conversation_manager.add_tool_result(tool_use_id, error_result)

def continue_conversation():
    """
    Continue the conversation after processing tools.
    Part of the state machine implementation.
    """
    conversation_manager = st.session_state.conversation_manager
    
    if conversation_manager.state != ConversationState.CONTINUING:
        logger.warning(f"continue_conversation called in wrong state: {conversation_manager.state.value}")
        return
    
    logger.info("Continuing conversation after tool processing")
    
    with st.spinner("Generating response..."):
        try:
            # Get messages for Bedrock
            messages = conversation_manager.get_bedrock_messages()
            
            # Create system prompt
            system_prompt = [
                {"text": "You are a helpful assistant with access to MCP servers for retail operations. "
                        "You can get product information and manage orders using the available tools. "
                        "Use the tools when appropriate to help the user."}
            ]
            
            # Set inference parameters
            max_tokens = 4096
            temperature = 0.7
            
            # Get tool configuration
            tool_config = get_bedrock_tool_config()
            
            # Call Bedrock
            logger.info(f"Calling Bedrock converse with {len(messages)} messages")
            
            # Log first few messages for debugging
            for i, msg in enumerate(messages[-3:] if len(messages) > 3 else messages):
                logger.info(f"Message {len(messages)-3+i}: role={msg.get('role')}, content={json.dumps(msg.get('content'))[:200]}...")
            
            # Switch to waiting state before making API call
            conversation_manager.transition_to(ConversationState.WAITING_FOR_RESPONSE)
            
            # Make API call
            start_time = time.time()
            response = bedrock_runtime.converse(
                modelId=st.session_state.model_id,
                messages=messages,
                system=system_prompt,
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature
                },
                toolConfig=tool_config
            )
            duration = time.time() - start_time
            
            logger.info(f"Bedrock API call completed in {duration:.2f} seconds")
            logger.info(f"Bedrock response: {json.dumps(response, default=str)[:500]}...")
            
            # Process the response
            result = conversation_manager.process_bedrock_response(response)
            logger.info(f"Processed response: {json.dumps(result, default=str)[:500]}...")
            
            # If there's text content, show it
            if result["text"]:
                with st.chat_message("assistant"):
                    st.markdown(result["text"])
            
            # If there are new tool uses, process them in the next update
            if result["tool_uses"]:
                # State is already set to PROCESSING_TOOLS by process_bedrock_response
                logger.info(f"Response contains {len(result['tool_uses'])} new tool uses")
                st.rerun()  # Trigger rerun to process tools
            else:
                # No tool uses, go back to idle
                conversation_manager.transition_to(ConversationState.IDLE)
                
        except Exception as e:
            logger.error(f"Error continuing conversation: {e}")
            logger.error(traceback.format_exc())
            st.error(f"Error: {str(e)}")
            # Set error state
            conversation_manager.last_error = str(e)
            conversation_manager.transition_to(ConversationState.ERROR)

# Form reset callback
def reset_form():
    st.session_state.reset_form = True
    st.rerun()

# ------------------------------------------------
# UI IMPLEMENTATION
# ------------------------------------------------

# Add model selection in sidebar
st.sidebar.title("Model Settings")
model_id = st.sidebar.selectbox(
    "Select Claude model",
    ["anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0", "anthropic.claude-3-5-sonnet-20240620-v1:0", "anthropic.claude-3-7-sonnet-20250219-v1:0"],
    index=1  # Default to Claude 3 Haiku
)

# Store the model ID in session state
st.session_state.model_id = model_id

# Authentication Section
with st.sidebar.expander("Authentication Settings", expanded=False):
    auth_token = st.text_input("JWT Bearer Token", 
                               value=st.session_state.auth_token,
                               type="password", 
                               help="Enter your JWT bearer token for authenticating MCP requests")
    if st.button("Save Auth Token"):
        st.session_state.auth_token = auth_token
        st.success("Authentication token saved!")
        
        # Update all server infos with the global token
        for server_name in st.session_state.server_info:
            if not st.session_state.server_info[server_name].get('token'):
                st.session_state.server_info[server_name]['token'] = auth_token

# Display built-in MCP servers
st.sidebar.title("Built-in MCP Servers")

# Get server URLs from environment variables
product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL', 'Not configured')
order_server_url = os.environ.get('ORDER_MCP_SERVER_URL', 'Not configured')

st.sidebar.write("Product Server URL:")
st.sidebar.code(product_server_url)
st.sidebar.write("Order Server URL:")
st.sidebar.code(order_server_url)

# MCP Server Management UI
st.sidebar.title("MCP Server Manager")

# Add new MCP server form
with st.sidebar.expander("Add New MCP Server", expanded=False):
    # Use a form with key based on reset_form state to allow proper resetting
    form_key = f"server_form_{st.session_state.reset_form}"
    
    with st.form(key=form_key):
        new_server_name = st.text_input("Server Name", key=f"name_{form_key}")
        new_server_url = st.text_input("Server URL", key=f"url_{form_key}")
        new_server_token = st.text_input("Auth Token (Optional)", 
                                         value=st.session_state.auth_token,
                                         type="password", 
                                         key=f"token_{form_key}")
        
        col1, col2 = st.columns(2)
        test_submitted = col1.form_submit_button("Test Connection")
        add_submitted = col2.form_submit_button("Add Server")
    
    # Handle form submission outside the form
    if test_submitted:
        if new_server_name and new_server_url:
            with st.spinner("Testing connection..."):
                try:
                    # Use global token if server-specific one not provided
                    token_to_use = new_server_token if new_server_token else st.session_state.auth_token
                    
                    # Test connection using MCP client
                    result = discover_tools(
                        new_server_name, 
                        new_server_url, 
                        token_to_use
                    )
                    if result > 0:
                        st.success(f"✅ Connection successful! Found {result} tools.")
                    else:
                        st.warning("⚠️ Connected but no tools found.")
                except Exception as e:
                    st.error(f"❌ Failed to connect: {str(e)}")
        else:
            st.warning("⚠️ Both name and URL are required")
    
    if add_submitted:
        if new_server_name and new_server_url:
            # Add to session state
            st.session_state.custom_mcp_servers[new_server_name] = new_server_url
            
            # Use global token if server-specific one not provided
            token_to_use = new_server_token if new_server_token else st.session_state.auth_token
            
            # Add to server info with token if provided
            st.session_state.server_info[new_server_name] = {
                'url': new_server_url,
                'token': token_to_use,
                'status': 'registered',
                'tool_count': 0
            }
            
            st.success(f"✅ Added MCP server: {new_server_name}")
            
            # Reset the form by triggering a rerun with a new form key
            reset_form()
        else:
            st.warning("⚠️ Both name and URL are required")

# Display and manage custom servers
if st.session_state.custom_mcp_servers:
    st.sidebar.write("### Custom MCP Servers")
    for server_name, server_url in st.session_state.custom_mcp_servers.items():
        with st.sidebar.expander(f"{server_name}", expanded=False):
            st.code(server_url)
            
            # Show if token is present
            token = st.session_state.server_info[server_name].get('token')
            if token:
                st.info("Auth token provided ✓")
            else:
                st.info("No auth token")
                
            if st.button("Remove", key=f"remove_{server_name}"):
                # Remove from session state
                del st.session_state.custom_mcp_servers[server_name]
                
                # Remove from server info
                if server_name in st.session_state.server_info:
                    del st.session_state.server_info[server_name]
                
                # Remove tools from tool mapping
                to_remove = []
                for tool_name, mapping in st.session_state.tool_mapping.items():
                    if mapping['server'] == server_name:
                        to_remove.append(tool_name)
                
                for tool_name in to_remove:
                    del st.session_state.tool_mapping[tool_name]
                
                st.rerun()

# MCP Tool Discovery
st.sidebar.title("MCP Tool Discovery")

# Discover tools button
if st.sidebar.button("Discover All Tools"):
    with st.sidebar.status("Discovering tools...", expanded=True) as status:
        # Discover tools from all servers
        for server_name, info in st.session_state.server_info.items():
            status.update(label=f"Discovering tools from {server_name}...", state="running")
            server_url = info['url']
            server_token = info.get('token') or st.session_state.auth_token  # Use global token if not server-specific
            
            # Run discovery with token if available
            tool_count = discover_tools(server_name, server_url, server_token)
            status.update(label=f"Found {tool_count} tools in {server_name}", state="running")
        
        status.update(label="Tool discovery complete!", state="complete")

# Display server status
for server_name, info in st.session_state.server_info.items():
    status = info.get('status', 'registered')
    tool_count = info.get('tool_count', 0)
    
    if status == 'ready' and tool_count > 0:
        st.sidebar.success(f"✅ {server_name}: {tool_count} tools available")
    elif status == 'error':
        st.sidebar.error(f"❌ {server_name}: Connection error")
    else:
        st.sidebar.warning(f"⚠️ {server_name}: Tools not yet discovered")

# Get tool configuration for Bedrock
tool_config = get_bedrock_tool_config()

# Debug tool configuration
with st.sidebar.expander("Bedrock Tool Configuration", expanded=False):
    st.json(tool_config)

# Debug conversation state
with st.sidebar.expander("Conversation State (Debug)", expanded=False):
    st.write(f"Current state: {st.session_state.conversation_manager.state.value}")
    st.write(f"Pending tools: {len(st.session_state.conversation_manager.pending_tool_uses)}")
    st.write(f"Messages: {len(st.session_state.conversation_manager.messages)}")
    st.write(f"Error count: {len(st.session_state.conversation_manager.error_counts)}")
    st.write(f"Current tool: {st.session_state.conversation_manager.current_tool_use_id}")
    
    # Show recent processing history
    if st.session_state.processing_history:
        st.write("Recent tool executions:")
        for i, item in enumerate(st.session_state.processing_history[-5:]):
            st.write(f"{i+1}. {item.get('tool')} - {item.get('status')} - {item.get('duration', 0):.1f}s")

# Main UI
st.title("Remote MCP Integration Demo")
st.subheader("Interact with Remote MCP Servers through Claude")

# Pre-filled server suggestion
st.info("""
💡 **Tip:** Try adding this known-working MCP server:
- **Name:** mcp-demo
- **URL:** http://infras-mcpse-3tf1shydmuay-2131978296.us-east-1.elb.amazonaws.com/mcp
- **Auth Token:** (Enter your JWT token in the sidebar authentication settings)
""")

# Application modes
mode = st.radio("Select Mode", ["Manual MCP Tool Tester", "Agentic Bedrock Chat"])

# Reset conversation when mode changes
if 'previous_mode' not in st.session_state:
    st.session_state.previous_mode = mode
if st.session_state.previous_mode != mode:
    st.session_state.conversation_manager.reset()
    st.session_state.previous_mode = mode

if mode == "Manual MCP Tool Tester":
    st.subheader("MCP Tool Tester")
    
    # Get all server names
    server_names = list(st.session_state.server_info.keys())
    
    if not server_names:
        st.warning("No MCP servers registered. Add servers in the sidebar.")
    else:
        # Let user choose server
        selected_server = st.selectbox("Select MCP Server", server_names)
        
        # Get tools for this server from tool mapping
        server_tools = {}
        for bedrock_name, mapping in st.session_state.tool_mapping.items():
            if mapping['server'] == selected_server:
                server_tools[mapping['method']] = mapping
        
        if not server_tools:
            st.warning(f"No tools discovered for {selected_server}. Click 'Discover All Tools' in the sidebar.")
        else:
            # Let user select tool
            tool_names = list(server_tools.keys())
            selected_tool = st.selectbox("Select Tool", tool_names)
            
            # Show tool info
            tool_info = server_tools.get(selected_tool, {})
            st.write("Tool Information:")
            st.json(tool_info)
            
            # Tool input form
            st.write("Tool Parameters:")
            tool_input_str = st.text_area("Input JSON", value="{}", height=100)
            
            if st.button("Execute Tool"):
                try:
                    # Parse input
                    tool_input = json.loads(tool_input_str)
                    
                    # Execute tool
                    bedrock_tool_name = f"{selected_server}_{selected_tool.replace('-', '_')}"
                    
                    with st.spinner("Executing tool..."):
                        result = call_tool(bedrock_tool_name, tool_input)
                        
                        # Display result
                        st.write("Tool Result:")
                        st.json(result)
                        
                except json.JSONDecodeError:
                    st.error("Invalid JSON in tool parameters")
                except Exception as e:
                    st.error(f"Error executing tool: {str(e)}")

elif mode == "Agentic Bedrock Chat":
    st.subheader("Agentic Bedrock Chat")
    
    # Count available tools
    tool_count = len(tool_config.get("tools", []))
    
    if tool_count == 0:
        st.error("No MCP tools available. Please add servers or discover tools.")
        st.info("""
        Troubleshooting steps:
        1. Check server URLs in the sidebar
        2. Ensure your authentication token is set in the sidebar
        3. Click the "Discover All Tools" button
        4. Ensure MCP servers are running and accessible
        """)
    else:
        # Process current conversation state
        process_conversation_state()
        
        # Debug conversation state below the chat
        st.caption(f"Conversation state: {st.session_state.conversation_manager.state.value}")
        
        # Display chat history
        for message in st.session_state.conversation_manager.messages:
            role = message.get("role", "")
            content = ""
            
            # Extract text content
            if "content" in message:
                for item in message["content"]:
                    if isinstance(item, dict) and "text" in item:
                        content += item["text"]
                    elif isinstance(item, dict) and "toolResult" in item:
                        tool_result = item["toolResult"]
                        tool_id = tool_result.get("toolUseId", "unknown")
                        content += f"[Tool Result: {tool_id}]"
            
            # Show in chat UI
            if content and role in ["user", "assistant"]:
                with st.chat_message(role):
                    st.markdown(content)
        
        # Recovery and debugging UI
        st.sidebar.subheader("Conversation Controls")
        
        # Show state-specific controls
        current_state = st.session_state.conversation_manager.state
        
        if current_state == ConversationState.ERROR:
            st.error(f"Error: {st.session_state.conversation_manager.last_error}")
            if st.sidebar.button("🔄 Reset Conversation"):
                st.session_state.conversation_manager.reset()
                st.session_state.processing_history = []
                st.rerun()
                
        elif current_state == ConversationState.PROCESSING_TOOLS:
            # Show tool processing status
            st.info(f"Processing tools... ({len(st.session_state.conversation_manager.pending_tool_uses)} remaining)")
            
            if st.sidebar.button("🔄 Force Continue (if stuck)"):
                st.session_state.conversation_manager.force_continue()
                st.rerun()
                
        elif current_state == ConversationState.WAITING_FOR_RESPONSE:
            # Show waiting status
            st.info("Waiting for Bedrock response...")
            
            if st.sidebar.button("🔄 Cancel and Reset"):
                st.session_state.conversation_manager.reset()
                st.rerun()
                
        elif current_state == ConversationState.CONTINUING:
            # Show continuing status
            st.info("Continuing conversation after tool execution...")
            
            if st.sidebar.button("🔄 Force Reset"):
                st.session_state.conversation_manager.reset()
                st.rerun()
        
        # Chat input - only enable if in IDLE state
        is_input_enabled = st.session_state.conversation_manager.is_idle()
        
        if is_input_enabled:
            user_input = st.chat_input("Type your message here...")
            if user_input:
                # Add to conversation history
                st.session_state.conversation_manager.add_user_message(user_input)
                
                # Debug: List all available tools
                all_tools = list(st.session_state.tool_mapping.keys())
                logger.info(f"Available tools for this conversation: {all_tools}")
                
                # Show in chat UI
                with st.chat_message("user"):
                    st.markdown(user_input)
                
                # Process with Bedrock
                with st.spinner("Claude is thinking..."):
                    try:
                        # Get messages for Bedrock
                        messages = st.session_state.conversation_manager.get_bedrock_messages()
                        
                        # Create system prompt
                        system_prompt = [
                            {"text": "You are a helpful assistant with access to MCP servers for retail operations. "
                                    "You can get product information and manage orders using the available tools. "
                                    "Use the tools when appropriate to help the user."}
                        ]
                        
                        # Set inference parameters
                        max_tokens = 4096
                        temperature = 0.7
                        
                        # Get tool configuration
                        tool_config = get_bedrock_tool_config()
                        
                        # Transition to waiting state
                        st.session_state.conversation_manager.transition_to(ConversationState.WAITING_FOR_RESPONSE)
                        
                        # Log the API call
                        logger.info(f"Calling Bedrock converse with model={model_id} and {len(messages)} messages")
                        for i, msg in enumerate(messages[-3:] if len(messages) > 3 else messages):
                            logger.info(f"Message {len(messages)-3+i}: role={msg.get('role')}, content_count={len(msg.get('content', []))}")
                        
                        # Make API call
                        start_time = time.time()
                        response = bedrock_runtime.converse(
                            modelId=model_id,
                            messages=messages,
                            system=system_prompt,
                            inferenceConfig={
                                "maxTokens": max_tokens,
                                "temperature": temperature
                            },
                            toolConfig=tool_config
                        )
                        duration = time.time() - start_time
                        
                        # Log response
                        logger.info(f"Bedrock API call completed in {duration:.2f} seconds with status {response.get('stopReason', 'unknown')}")
                        logger.info(f"Bedrock response: {json.dumps(response, default=str)[:500]}...")
                        
                        # Process the response
                        result = st.session_state.conversation_manager.process_bedrock_response(response)
                        logger.info(f"Processed Bedrock response: {json.dumps(result, default=str)[:500]}...")
                        
                        # If there's text content, show it
                        if result["text"]:
                            with st.chat_message("assistant"):
                                st.markdown(result["text"])
                        
                        # If there are tool uses, trigger a rerun to start processing
                        if result["tool_uses"]:
                            logger.info(f"Found {len(result['tool_uses'])} tool uses, triggering rerun")
                            st.rerun()
                        
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        logger.error(traceback.format_exc())
                        st.error(f"Error: {str(e)}")
                        
                        # Set error state
                        st.session_state.conversation_manager.last_error = str(e)
                        st.session_state.conversation_manager.transition_to(ConversationState.ERROR)
        else:
            # Input is disabled because we're in a non-idle state
            st.text_input("Type your message here...", disabled=True, 
                         placeholder=f"Please wait... ({st.session_state.conversation_manager.state.value})")

# Display commit ID
st.markdown(f"<div style='position: fixed; right: 10px; bottom: 10px; font-size: 12px; color: gray;'>Version: {commit_id}</div>", unsafe_allow_html=True)