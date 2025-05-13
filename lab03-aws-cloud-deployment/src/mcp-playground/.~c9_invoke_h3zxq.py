import streamlit as st
import boto3
import json
import os
import subprocess
import uuid
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List
import traceback
import logging

# Import the new MCP client - import from the correct location
from mcp_client import MCPClient

# Import the conversation manager
from conversation_manager import ConversationManager

# Configure logging
logging.basicConfig(level=logging.INFO)
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

if 'custom_mcp_servers' not in st.session_state:
    st.session_state.custom_mcp_servers = {}

# Initialize tool mapping if not present
if 'tool_mapping' not in st.session_state:
    st.session_state.tool_mapping = {}

# Initialize form reset state if not present
if 'reset_form' not in st.session_state:
    st.session_state.reset_form = False

# Helper function to run async code safely in Streamlit
def run_async(coro):
    """Run an async function from sync code safely"""
    executor = ThreadPoolExecutor(max_workers=1)
    
    def wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro)
        loop.close()
        return result
    
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
            'token': None,  # Initially no token for built-in servers
            'status': 'registered',
            'tool_count': 0
        }
    
    if order_server_url:
        st.session_state.server_info['order-server'] = {
            'url': order_server_url,
            'token': None,  # Initially no token for built-in servers
            'status': 'registered',
            'tool_count': 0
        }

# Async functions using the new MCP client

async def discover_server_tools(server_name, server_url, auth_token=None):
    """Discover tools from a server using the MCP client with new API"""
    # Create client with timeout
    client = MCPClient(server_url, auth_token, timeout=10.0)
    
    try:
        # Initialize client - this replaces the old connect() call
        await client.init()
        
        # Get tools
        tools = await client.get_tools()
        
        # Store tools in session state
        tool_count = 0
        for tool in tools:
            # Handle both object and dictionary formats
            if hasattr(tool, 'name'):
                tool_name = tool.name
                schema = getattr(tool, 'inputSchema', {})
                description = getattr(tool, 'description', '')
            elif isinstance(tool, dict):
                tool_name = tool.get('name', '')
                schema = tool.get('inputSchema', {})
                description = tool.get('description', '')
            else:
                # Try a last resort approach
                try:
                    tool_name = str(tool)
                    schema = {}
                    description = "Unknown tool format"
                except:
                    continue  # Skip this tool
                
            if not tool_name:
                continue  # Skip tools without a name
            
            # Create bedrock-compatible name
            bedrock_name = f"{server_name}_{tool_name.replace('-', '_')}"
            
            # Store tool mapping
            st.session_state.tool_mapping[bedrock_name] = {
                'server': server_name,
                'url': server_url,
                'token': auth_token,  # Store token with the tool mapping
                'method': tool_name,
                'schema': schema,
                'description': description
            }
            
            tool_count += 1
        
        return tool_count
    except Exception as e:
        logger.error(f"Error discovering tools from {server_name}: {e}")
        return 0
    finally:
        # Always cleanup - this replaces the old disconnect() call
        await client.cleanup()

async def call_mcp_tool(server_url, tool_name, params, auth_token=None):
    """Call a tool using the MCP client with new API"""
    # Create client with timeout
    client = MCPClient(server_url, auth_token, timeout=10.0)
    
    try:
        # Initialize client
        await client.init()
        
        # Call tool
        result = await client.call_tool(tool_name, params)
        return result
    except Exception as e:
        logger.error(f"Error calling tool {tool_name}: {e}")
        return {"error": str(e)}
    finally:
        # Always cleanup
        await client.cleanup()

# Sync wrapper functions for Streamlit

def discover_tools(server_name, server_url, auth_token=None):
    """Streamlit-friendly wrapper for tool discovery"""
    try:
        tool_count = run_async(discover_server_tools(server_name, server_url, auth_token))
        
        # Update server status
        if server_name in st.session_state.server_info:
            st.session_state.server_info[server_name]['status'] = 'ready' if tool_count > 0 else 'error'
            st.session_state.server_info[server_name]['tool_count'] = tool_count
        
        return tool_count
    except Exception as e:
        logger.error(f"Error in discover_tools for {server_name}: {e}")
        if server_name in st.session_state.server_info:
            st.session_state.server_info[server_name]['status'] = 'error'
        return 0

def call_tool(bedrock_tool_name, params):
    """Streamlit-friendly wrapper for tool calling"""
    if bedrock_tool_name not in st.session_state.tool_mapping:
        return {"error": f"Unknown tool: {bedrock_tool_name}"}
    
    mapping = st.session_state.tool_mapping[bedrock_tool_name]
    server_url = mapping['url']
    method_name = mapping['method']
    auth_token = mapping.get('token')  # Get token from mapping
    
    try:
        return run_async(call_mcp_tool(server_url, method_name, params, auth_token))
    except Exception as e:
        logger.error(f"Error in call_tool for {bedrock_tool_name}: {e}")
        return {"error": str(e)}

def get_bedrock_tool_config():
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
    
    return {"tools": tool_specs}

# Form reset callback
def reset_form():
    st.session_state.reset_form = True
    st.rerun()

# Add model selection in sidebar
st.sidebar.title("Model Settings")
model_id = st.sidebar.selectbox(
    "Select Claude model",
    ["anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0", "anthropic.claude-3-5-sonnet-20240620-v1:0", "anthropic.claude-3-7-sonnet-20250219-v1:0"],
    index=1  # Default to Claude 3 Haiku
)

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
        new_server_token = st.text_input("Auth Token (Optional)", type="password", key=f"token_{form_key}")
        
        col1, col2 = st.columns(2)
        test_submitted = col1.form_submit_button("Test Connection")
        add_submitted = col2.form_submit_button("Add Server")
    
    # Handle form submission outside the form
    if test_submitted:
        if new_server_name and new_server_url:
            with st.spinner("Testing connection..."):
                try:
                    # Test connection using MCP client
                    result = run_async(discover_server_tools(
                        new_server_name, 
                        new_server_url, 
                        new_server_token if new_server_token else None
                    ))
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
            
            # Add to server info with token if provided
            st.session_state.server_info[new_server_name] = {
                'url': new_server_url,
                'token': new_server_token if new_server_token else None,
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
            server_token = info.get('token')  # Get token for this server
            
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

# Main UI
st.title("Remote MCP Integration Demo")
st.subheader("Interact with Remote MCP Servers through Claude")

# Pre-filled server suggestion
st.info("""
💡 **Tip:** Try adding this known-working MCP server:
- **Name:** mcp-demo
- **URL:** http://infras-mcpse-3tf1shydmuay-2131978296.us-east-1.elb.amazonaws.com/mcp
- **Auth Token:** (Request from your team)
""")

# Application modes
mode = st.radio("Select Mode", ["Manual MCP Tool Tester", "Agentic Bedrock Chat"])

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
        2. Click the "Discover All Tools" button
        3. Ensure MCP servers are running and accessible
        4. Make sure you've provided authentication tokens if required
        """)
    else:
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
                        content += f"[Tool Result: {tool_result.get('toolUseId', 'unknown')}]"
            
            # Show in chat UI
            if content and role in ["user", "assistant"]:
                with st.chat_message(role):
                    st.markdown(content)
        
        # Chat input
        user_input = st.chat_input("Type your message here...")
        if user_input:
            # Add to conversation history
            st.session_state.conversation_manager.add_user_message(user_input)
            
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
                    
                    # Call Bedrock
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
                    
                    # Process the response
                    result = st.session_state.conversation_manager.process_bedrock_response(response)
                    
                    # If there's text content, show it
                    if result["text"]:
                        with st.chat_message("assistant"):
                            st.markdown(result["text"])
                    
                    # If there are tool uses, process them
                    if result["tool_uses"]:
                        with st.status("Executing tools...", expanded=False) as status:
                            for tool_use in result["tool_uses"]:
                                tool_use_id = tool_use.get("toolUseId")
                                tool_name = tool_use.get("name")
                                tool_input = tool_use.get("input", {})
                                
                                status.update(label=f"Executing {tool_name}...", state="running")
                                
                                # Call the tool
                                tool_result = call_tool(tool_name, tool_input)
                                
                                # Add result to conversation
                                st.session_state.conversation_manager.add_tool_result(tool_use_id, tool_result)
                                
                                status.update(label=f"Tool {tool_name} executed", state="running")
                            
                            status.update(label="All tools executed", state="complete")
                        
                        # Continue the conversation with tool results
                        with st.spinner("Processing tool results..."):
                            messages = st.session_state.conversation_manager.get_bedrock_messages()
                            
                            # Call Bedrock again
                            response2 = bedrock_runtime.converse(
                                modelId=model_id,
                                messages=messages,
                                system=system_prompt,
                                inferenceConfig={
                                    "maxTokens": max_tokens,
                                    "temperature": temperature
                                },
                                toolConfig=tool_config
                            )
                            
                            # Process the response
                            result2 = st.session_state.conversation_manager.process_bedrock_response(response2)
                            
                            # Show the final response
                            if result2["text"]:
                                with st.chat_message("assistant"):
                                    st.markdown(result2["text"])
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.sidebar.error(f"Detailed error: {str(e)}")
                    
                    import traceback
                    st.sidebar.code(traceback.format_exc())

# Display commit ID
st.markdown(f"<div style='position: fixed; right: 10px; bottom: 10px; font-size: 12px; color: gray;'>Version: {commit_id}</div>", unsafe_allow_html=True)