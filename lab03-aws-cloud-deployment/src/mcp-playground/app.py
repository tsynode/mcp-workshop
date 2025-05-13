import streamlit as st
import boto3
import json
import os
import subprocess
import uuid
import asyncio
from typing import Dict, Any, List

from mcp_server_manager import MCPServerManager
from conversation_manager import ConversationManager

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

if 'server_manager' not in st.session_state:
    st.session_state.server_manager = MCPServerManager()
    
    # Register built-in MCP servers
    product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL')
    order_server_url = os.environ.get('ORDER_MCP_SERVER_URL')
    
    if product_server_url:
        st.session_state.server_manager.register_server('product-server', product_server_url)
        st.session_state.server_manager.discover_tools('product-server')
    
    if order_server_url:
        st.session_state.server_manager.register_server('order-server', order_server_url)
        st.session_state.server_manager.discover_tools('order-server')

if 'custom_mcp_servers' not in st.session_state:
    st.session_state.custom_mcp_servers = {}

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
    new_server_name = st.text_input("Server Name", key="new_server_name")
    new_server_url = st.text_input("Server URL", key="new_server_url")
    
    # Test server button
    if st.button("Test Server Connection"):
        if new_server_name and new_server_url:
            # Create a temporary server manager for testing
            test_manager = MCPServerManager()
            if test_manager.register_server(new_server_name, new_server_url):
                tool_count = test_manager.discover_tools(new_server_name)
                if tool_count > 0:
                    st.success(f"✅ Connection successful! Found {tool_count} tools.")
                else:
                    st.warning("⚠️ Connected but no tools found.")
            else:
                st.error("❌ Failed to connect to server.")
        else:
            st.warning("⚠️ Both name and URL are required")
    
    # Add server button
    if st.button("Add Server"):
        if new_server_name and new_server_url:
            # Add to session state
            st.session_state.custom_mcp_servers[new_server_name] = new_server_url
            # Register with the server manager
            st.session_state.server_manager.register_server(new_server_name, new_server_url)
            tool_count = st.session_state.server_manager.discover_tools(new_server_name)
            st.success(f"✅ Added MCP server: {new_server_name} with {tool_count} tools")
            # Clear input fields
            st.session_state.new_server_name = ""
            st.session_state.new_server_url = ""
        else:
            st.warning("⚠️ Both name and URL are required")

# Display and manage custom servers
if st.session_state.custom_mcp_servers:
    st.sidebar.write("### Custom MCP Servers")
    for server_name, server_url in st.session_state.custom_mcp_servers.items():
        with st.sidebar.expander(f"{server_name}", expanded=False):
            st.code(server_url)
            if st.button("Remove", key=f"remove_{server_name}"):
                # Remove from session state
                del st.session_state.custom_mcp_servers[server_name]
                # Remove from server manager
                st.session_state.server_manager.remove_server(server_name)
                st.rerun()

# MCP Tool Discovery
st.sidebar.title("MCP Tool Discovery")

# Discover tools button
if st.sidebar.button("Discover All Tools"):
    with st.sidebar.status("Discovering tools...", expanded=True) as status:
        # Discover tools from all servers
        for server_name in st.session_state.server_manager.servers.keys():
            tool_count = st.session_state.server_manager.discover_tools(server_name)
            status.update(f"Found {tool_count} tools in {server_name}", state="running")
        
        status.update(label="Tool discovery complete!", state="complete")

# Display available servers and tools
for server_name, server_info in st.session_state.server_manager.servers.items():
    tool_count = len(server_info.get('tools', {}))
    status = server_info.get('status', 'unknown')
    
    if tool_count > 0:
        st.sidebar.success(f"✅ {server_name}: {tool_count} tools available")
    elif status == 'error' or status == 'connection_error':
        st.sidebar.error(f"❌ {server_name}: Connection error")
    else:
        st.sidebar.warning(f"⚠️ {server_name}: No tools discovered")

# Get tool configuration for Bedrock
tool_config = st.session_state.server_manager.get_bedrock_tool_config()

# Debug tool configuration
with st.sidebar.expander("Bedrock Tool Configuration", expanded=False):
    st.json(tool_config)

# Main UI
st.title("Remote MCP Integration Demo")
st.subheader("Interact with Remote MCP Servers through Claude")

# Application modes
mode = st.radio("Select Mode", ["Manual MCP Tool Tester", "Agentic Bedrock Chat"])

if mode == "Manual MCP Tool Tester":
    st.subheader("MCP Tool Tester")
    
    # Get all server names
    server_names = list(st.session_state.server_manager.servers.keys())
    
    if not server_names:
        st.warning("No MCP servers registered. Add servers in the sidebar.")
    else:
        # Let user choose server
        selected_server = st.selectbox("Select MCP Server", server_names)
        
        # Get tools for this server
        server_info = st.session_state.server_manager.servers.get(selected_server, {})
        tools = server_info.get('tools', {})
        
        if not tools:
            st.warning(f"No tools discovered for {selected_server}. Click 'Discover All Tools' in the sidebar.")
        else:
            # Let user select tool
            tool_names = list(tools.keys())
            selected_tool = st.selectbox("Select Tool", tool_names)
            
            # Show tool info
            tool_info = tools.get(selected_tool, {})
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
                        # Create event loop for async execution
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Call the tool
                        result = loop.run_until_complete(
                            st.session_state.server_manager.call_tool(bedrock_tool_name, tool_input)
                        )
                        
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
                                
                                status.update(f"Executing {tool_name}...", state="running")
                                
                                # Create event loop for async execution
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                
                                # Call the tool
                                tool_result = loop.run_until_complete(
                                    st.session_state.server_manager.call_tool(tool_name, tool_input)
                                )
                                
                                # Add result to conversation
                                st.session_state.conversation_manager.add_tool_result(tool_use_id, tool_result)
                                
                                status.update(f"Tool {tool_name} executed", state="running")
                            
                            status.update("All tools executed", state="complete")
                        
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