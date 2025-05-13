import streamlit as st
import boto3
import json
import os
import subprocess
import uuid
import asyncio
import requests
from typing import Dict, Any, List
import traceback
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

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
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'tools' not in st.session_state:
    st.session_state.tools = []

if 'custom_mcp_servers' not in st.session_state:
    st.session_state.custom_mcp_servers = {}

# Simplified MCP tool discovery and calling functions
def discover_tools(server_name, server_url):
    """
    Discover tools from a MCP server using the tools/list method
    Returns the number of tools discovered
    """
    try:
        # Create a tools/list request according to MCP specification
        list_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": str(uuid.uuid4())
        }
        
        # Send the request to the MCP server
        response = requests.post(
            server_url,
            json=list_request,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            },
            verify=False,  # For development only
            timeout=10     # Add timeout to prevent hanging
        )
        
        # Parse the response
        if response.status_code == 200:
            result = response.json()
            if "result" in result and "tools" in result["result"]:
                tools = result["result"]["tools"]
                
                # Store tools with a prefix to avoid name collisions
                for tool in tools:
                    tool_name = tool.get('name', '')
                    # Add server name as prefix for Bedrock
                    bedrock_name = f"{server_name}_{tool_name.replace('-', '_')}"
                    
                    # Store mapping in session state
                    if 'tool_mapping' not in st.session_state:
                        st.session_state.tool_mapping = {}
                        
                    st.session_state.tool_mapping[bedrock_name] = {
                        'server': server_name,
                        'url': server_url,
                        'method': tool_name,
                        'schema': tool.get('inputSchema', {}),
                        'description': tool.get('description', '')
                    }
                
                return len(tools)
        
        return 0
    except Exception as e:
        logger.error(f"Error discovering tools: {str(e)}")
        return 0

def call_tool(tool_name, params):
    """Call a tool by its Bedrock name"""
    if 'tool_mapping' not in st.session_state:
        return {"error": "No tools registered"}
        
    if tool_name not in st.session_state.tool_mapping:
        return {"error": f"Unknown tool: {tool_name}"}
        
    mapping = st.session_state.tool_mapping[tool_name]
    server_url = mapping['url']
    method_name = mapping['method']
    
    try:
        # Create a standard JSON-RPC 2.0 request
        mcp_request = {
            "jsonrpc": "2.0",
            "method": method_name,
            "params": params,
            "id": str(uuid.uuid4())
        }
        
        # Send the request to the MCP server
        response = requests.post(
            server_url,
            json=mcp_request,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            },
            verify=False,  # For development only
            timeout=10     # Add timeout to prevent hanging
        )
        
        # Parse the response
        if response.status_code == 200:
            result = response.json()
            
            # Extract tool result
            if "result" in result and "content" in result["result"]:
                content = result["result"]["content"]
                text_content = []
                
                for item in content:
                    if item.get("type") == "text" and "text" in item:
                        text_content.append(item["text"])
                
                if text_content:
                    return {"content": "\n".join(text_content)}
                else:
                    return {"content": json.dumps(result["result"])}
            else:
                return result
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
            
    except Exception as e:
        logger.error(f"Error calling tool {method_name}: {e}")
        return {"error": str(e)}

def get_bedrock_tool_config():
    """Get tool configuration for Bedrock"""
    if 'tool_mapping' not in st.session_state:
        return {"tools": []}
        
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

# Initialize built-in MCP servers without blocking the UI
if 'servers_initialized' not in st.session_state:
    st.session_state.servers_initialized = False
    
    # Register built-in servers
    if 'server_info' not in st.session_state:
        st.session_state.server_info = {}
    
    # Get from environment
    product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL')
    order_server_url = os.environ.get('ORDER_MCP_SERVER_URL')
    
    if product_server_url:
        st.session_state.server_info['product-server'] = {
            'url': product_server_url,
            'status': 'pending'
        }
    
    if order_server_url:
        st.session_state.server_info['order-server'] = {
            'url': order_server_url,
            'status': 'pending'
        }
    
    # Mark as initialized
    st.session_state.servers_initialized = True

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
            try:
                # Test the MCP server with a tools/list request
                response = requests.post(
                    new_server_url,
                    json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": "test"},
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json, text/event-stream'
                    },
                    verify=False,
                    timeout=5
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and "tools" in result["result"]:
                        tools = result["result"]["tools"]
                        st.success(f"✅ Connection successful! Found {len(tools)} tools.")
                    else:
                        st.warning("⚠️ Connected but no tools found in response.")
                else:
                    st.error(f"❌ Connection failed: HTTP {response.status_code}")
            except Exception as e:
                st.error(f"❌ Connection error: {str(e)}")
    
    # Add server button
    if st.button("Add Server"):
        if new_server_name and new_server_url:
            # Add to session state
            st.session_state.custom_mcp_servers[new_server_name] = new_server_url
            
            # Add to server info
            st.session_state.server_info[new_server_name] = {
                'url': new_server_url,
                'status': 'pending'
            }
            
            st.success(f"✅ Added MCP server: {new_server_name}")
            
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
                
                # Remove from server info
                if server_name in st.session_state.server_info:
                    del st.session_state.server_info[server_name]
                
                # Remove tools from tool mapping
                if 'tool_mapping' in st.session_state:
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
            status.update(f"Discovering tools from {server_name}...", state="running")
            server_url = info['url']
            tool_count = discover_tools(server_name, server_url)
            
            # Update server status
            st.session_state.server_info[server_name]['status'] = 'ready' if tool_count > 0 else 'error'
            st.session_state.server_info[server_name]['tool_count'] = tool_count
            
            status.update(f"Found {tool_count} tools in {server_name}", state="running")
        
        status.update(label="Tool discovery complete!", state="complete")

# Display server status
for server_name, info in st.session_state.server_info.items():
    status = info.get('status', 'pending')
    tool_count = info.get('tool_count', 0)
    
    if status == 'ready' and tool_count > 0:
        st.sidebar.success(f"✅ {server_name}: {tool_count} tools available")
    elif status == 'error':
        st.sidebar.error(f"❌ {server_name}: Connection error")
    else:
        st.sidebar.warning(f"⚠️ {server_name}: Discovery pending")

# Get tool configuration for Bedrock
tool_config = get_bedrock_tool_config()

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
    server_names = list(st.session_state.server_info.keys())
    
    if not server_names:
        st.warning("No MCP servers registered. Add servers in the sidebar.")
    else:
        # Let user choose server
        selected_server = st.selectbox("Select MCP Server", server_names)
        
        # Get tools for this server from tool mapping
        server_tools = {}
        if 'tool_mapping' in st.session_state:
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
        """)
    else:
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        user_input = st.chat_input("Type your message here...")
        if user_input:
            # Add to chat history
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # Show in chat UI
            with st.chat_message("user"):
                st.markdown(user_input)
            
            # Prepare messages for Bedrock
            bedrock_messages = []
            for msg in st.session_state.messages:
                bedrock_messages.append({
                    "role": msg["role"],
                    "content": [{"text": msg["content"]}]
                })
            
            # Process with Bedrock
            with st.spinner("Claude is thinking..."):
                try:
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
                        messages=bedrock_messages,
                        system=system_prompt,
                        inferenceConfig={
                            "maxTokens": max_tokens,
                            "temperature": temperature
                        },
                        toolConfig=tool_config
                    )
                    
                    # Extract text from response
                    assistant_text = ""
                    tool_uses = []
                    
                    if "output" in response and "message" in response["output"]:
                        message = response["output"]["message"]
                        for content in message.get("content", []):
                            if "text" in content:
                                assistant_text += content["text"]
                            elif "toolUse" in content:
                                tool_uses.append(content["toolUse"])
                    
                    # If text content, show it
                    if assistant_text:
                        # Add to chat history
                        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
                        with st.chat_message("assistant"):
                            st.markdown(assistant_text)
                    
                    # If tool uses, handle them
                    if tool_uses:
                        with st.status("Executing tools...", expanded=False) as status:
                            tool_results = []
                            
                            for tool_use in tool_uses:
                                tool_use_id = tool_use.get("toolUseId")
                                tool_name = tool_use.get("name")
                                tool_input = tool_use.get("input", {})
                                
                                status.update(f"Executing {tool_name}...", state="running")
                                
                                # Call tool
                                result = call_tool(tool_name, tool_input)
                                
                                # Format tool result for Bedrock
                                if "content" in result:
                                    content_value = result["content"]
                                    result_content = {"text": content_value} if isinstance(content_value, str) else {"json": content_value}
                                else:
                                    result_content = {"json": result}
                                
                                tool_result = {
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
                                
                                tool_results.append(tool_result)
                                status.update(f"Tool {tool_name} executed", state="running")
                            
                            status.update("All tools executed", state="complete")
                        
                        # If we have tool results, continue the conversation
                        if tool_results:
                            # Update messages with assistant response and tool results
                            updated_messages = bedrock_messages.copy()
                            
                            # Add assistant message with tool use
                            updated_messages.append({
                                "role": "assistant",
                                "content": message.get("content", [])
                            })
                            
                            # Add tool results
                            for tool_result in tool_results:
                                updated_messages.append(tool_result)
                            
                            # Call Bedrock again with tool results
                            final_response = bedrock_runtime.converse(
                                modelId=model_id,
                                messages=updated_messages,
                                system=system_prompt,
                                inferenceConfig={
                                    "maxTokens": max_tokens,
                                    "temperature": temperature
                                },
                                toolConfig=tool_config
                            )
                            
                            # Extract final text
                            final_text = ""
                            if "output" in final_response and "message" in final_response["output"]:
                                output_message = final_response["output"]["message"]
                                for content in output_message.get("content", []):
                                    if "text" in content:
                                        final_text += content["text"]
                            
                            # Display final response
                            if final_text:
                                # Add to chat history
                                st.session_state.messages.append({"role": "assistant", "content": final_text})
                                with st.chat_message("assistant"):
                                    st.markdown(final_text)
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    
                    # Add error to chat history
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
                    # Log detailed error
                    st.sidebar.error("Detailed error:")
                    st.sidebar.code(traceback.format_exc())

# Display commit ID
st.markdown(f"<div style='position: fixed; right: 10px; bottom: 10px; font-size: 12px; color: gray;'>Version: {commit_id}</div>", unsafe_allow_html=True)