import streamlit as st
import boto3
import json
import os
import subprocess
import uuid
import requests

# Import our BedrockMcpAdapter
from bedrock_mcp_adapter import BedrockMcpAdapter

# Configure page
st.set_page_config(page_title="Retail MCP Demo", layout="wide")

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

# Initialize session state for custom MCP servers
if 'custom_mcp_servers' not in st.session_state:
    st.session_state.custom_mcp_servers = {}

# Initialize the BedrockMcpAdapter
if 'mcp_adapter' not in st.session_state:
    st.session_state.mcp_adapter = BedrockMcpAdapter()
    # Get MCP server URLs from environment variables or use defaults
    product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL', 'https://mcp-prod-alb-989631483.us-west-2.elb.amazonaws.com/mcp')
    order_server_url = os.environ.get('ORDER_MCP_SERVER_URL', 'https://mcp-order-alb-912981373.us-west-2.elb.amazonaws.com/mcp')
    
    # Register built-in MCP servers
    st.session_state.mcp_adapter.register_server('product-server', product_server_url)
    st.session_state.mcp_adapter.register_server('order-server', order_server_url)

# Add model selection in sidebar
st.sidebar.title("Model Settings")
model_id = st.sidebar.selectbox(
    "Select Claude model",
    ["anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0", "anthropic.claude-3-5-sonnet-20240620-v1:0", "anthropic.claude-3-7-sonnet-20250219-v1:0"],
    index=1  # Default to Claude 3 Haiku as requested
)

# Debug information in sidebar
st.sidebar.title("Built-in MCP Servers")
product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL', 'https://mcp-prod-alb-989631483.us-west-2.elb.amazonaws.com/mcp')
order_server_url = os.environ.get('ORDER_MCP_SERVER_URL', 'https://mcp-order-alb-912981373.us-west-2.elb.amazonaws.com/mcp')

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
            # Register with the adapter
            st.session_state.mcp_adapter.register_server(new_server_name, new_server_url)
            st.success(f"✅ Added MCP server: {new_server_name}")
            # Clear input fields
            st.session_state.new_server_name = ""
            st.session_state.new_server_url = ""
        else:
            st.warning("⚠️ Both name and URL are required")

# Display and manage existing custom servers
if st.session_state.custom_mcp_servers:
    st.sidebar.write("### Custom MCP Servers")
    for server_name, server_url in st.session_state.custom_mcp_servers.items():
        with st.sidebar.expander(f"{server_name}", expanded=False):
            st.code(server_url)
            if st.button("Remove", key=f"remove_{server_name}"):
                # Remove from session state
                del st.session_state.custom_mcp_servers[server_name]
                # Recreate adapter to remove the server
                temp_adapter = BedrockMcpAdapter()
                # Re-register built-in servers
                temp_adapter.register_server('product-server', product_server_url)
                temp_adapter.register_server('order-server', order_server_url)
                # Re-register remaining custom servers
                for name, url in st.session_state.custom_mcp_servers.items():
                    temp_adapter.register_server(name, url)
                st.session_state.mcp_adapter = temp_adapter
                st.rerun()

# Discover tools from MCP servers
st.sidebar.title("MCP Tool Discovery")

# Function to discover tools from all servers
def discover_all_tools():
    tool_counts = {}
    
    # Discover tools from built-in servers
    product_tools = st.session_state.mcp_adapter.discover_tools('product-server')
    order_tools = st.session_state.mcp_adapter.discover_tools('order-server')
    tool_counts['product-server'] = product_tools
    tool_counts['order-server'] = order_tools
    
    # Discover tools from custom servers
    for server_name in st.session_state.custom_mcp_servers.keys():
        tools = st.session_state.mcp_adapter.discover_tools(server_name)
        tool_counts[server_name] = tools
    
    return tool_counts

# Discover tools button
if st.sidebar.button("Discover Tools"):
    with st.sidebar.status("Discovering tools...", expanded=True) as status:
        tool_counts = discover_all_tools()
        status.update(label="Tool discovery complete!", state="complete", expanded=True)
else:
    # Initial discovery
    tool_counts = discover_all_tools()

# Display tool discovery results
for server_name, count in tool_counts.items():
    if count > 0:
        st.sidebar.success(f"✅ {server_name}: {count} tools discovered")
    else:
        st.sidebar.warning(f"⚠️ {server_name}: No tools discovered")

# Get the Bedrock tool configuration with all discovered tools
tool_config = st.session_state.mcp_adapter.get_tool_config()

# Debug tool configuration
with st.sidebar.expander("Bedrock Tool Configuration", expanded=False):
    st.json(tool_config)

# Set up Streamlit UI
st.title("MCP Demo with Amazon Bedrock")
st.subheader("Ask about products or place an order")

# Add mode selection
mode = st.radio("Select Mode", ["Manual MCP Tool Tester", "Agentic Bedrock Chat"])

# Session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []
    
# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if mode == "Manual MCP Tool Tester":
    st.subheader("MCP Tool Tester (Bypass Bedrock)")
    
    # Get all server names (built-in + custom)
    all_servers = ['product-server', 'order-server'] + list(st.session_state.custom_mcp_servers.keys())
    
    # Let user choose MCP server
    tool_server = st.selectbox("Select MCP Server", all_servers)
    
    # Get server URL based on selection
    if tool_server == 'product-server':
        mcp_url = product_server_url
    elif tool_server == 'order-server':
        mcp_url = order_server_url
    else:
        mcp_url = st.session_state.custom_mcp_servers.get(tool_server, "")
    
    # Get available tools for the selected server
    try:
        # Helper function to get tools for a server
        def get_tools_for_server(server_name):
            tools = []
            for name, mapping in st.session_state.mcp_adapter._name_mapping.items():
                if mapping['server'] == server_name:
                    tools.append({'name': mapping['method']})
            return tools
        
        available_tools = get_tools_for_server(tool_server)
    except Exception as e:
        st.error(f"Error getting tools: {str(e)}")
        available_tools = []

    # Let user select a tool
    if available_tools:
        tool_names = [tool["name"] for tool in available_tools]
        selected_tool = st.selectbox("Select Tool", tool_names)
        # Show tool schema for reference
        tool_schema = next((tool for tool in available_tools if tool["name"] == selected_tool), {})
        st.write("Tool Schema:")
        st.json(tool_schema)
        # Tool input as JSON
        tool_input_str = st.text_area("Tool Input (JSON)", value="{}", height=100)
        if st.button("Call MCP Tool"):
            try:
                tool_input = json.loads(tool_input_str)
                # Prepare JSON-RPC request
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": selected_tool,
                    "params": tool_input,
                    "id": str(uuid.uuid4())
                }
                st.write("Request Payload:")
                st.json(mcp_request)
                with st.spinner("Calling MCP tool..."):
                    resp = requests.post(
                        mcp_url,
                        json=mcp_request,
                        headers={
                            'Content-Type': 'application/json',
                            'Accept': 'application/json, text/event-stream'
                        },
                        verify=False
                    )
                    st.write(f"Status Code: {resp.status_code}")
                    try:
                        st.json(resp.json())
                    except Exception:
                        st.write(resp.text)
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("No tools discovered for the selected MCP server.")

elif mode == "Agentic Bedrock Chat":
    # Check if any tools were discovered
    total_tools = sum(tool_counts.values())
    
    if total_tools == 0:
        st.error("No MCP tools were discovered. Bedrock requires at least one tool to be configured.")
        st.info("""
        Troubleshooting steps:
        1. Check MCP server URLs in the sidebar
        2. Make sure your MCP servers are running and accessible
        3. Click the "Discover Tools" button to retry
        """)
    else:
        st.subheader("Agentic Bedrock Chat (Claude + MCP)")
        # Rest of the chat interface remains the same...
        # Session state for conversation history
        if "messages" not in st.session_state:
            st.session_state.messages = []
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        # User input
        user_input = st.chat_input("Type your message here...")
        if user_input:
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            # Call Bedrock with Claude model and MCP tools
            with st.spinner("Claude is thinking..."):
                try:
                    # Convert previous messages to the format expected by Bedrock
                    messages_for_model = []
                    for msg in st.session_state.messages:
                        messages_for_model.append({
                            "role": msg["role"],
                            "content": [
                                {
                                    "text": msg["content"]
                                }
                            ]
                        })
                    # Set inference parameters based on model
                    max_tokens = 4096
                    temperature = 0.7
                    # Create a more MCP-aligned system prompt that focuses on tool discovery
                    system_prompt = [
                        {"text": "You are a retail assistant that can help customers with their shopping needs. "
                                "You have access to MCP servers that provide various retail capabilities. "
                                "Use the available tools to help customers with their requests. "
                                "You can discover what tools are available and what they can do through their schemas. "
                                "Respond to customer queries by using the most appropriate tool for each task."}
                    ]
                    
                    # Additional debug info
                    st.sidebar.write("### Bedrock API Request")
                    st.sidebar.write("Model ID:", model_id)
                    st.sidebar.write("Message Count:", len(messages_for_model))
                    st.sidebar.write("Tool Count:", len(tool_config.get("tools", [])))
                    
                    # Call the converse API with the selected model
                    response = bedrock_runtime.converse(
                        modelId=model_id,  
                        messages=messages_for_model,
                        system=system_prompt,
                        inferenceConfig={
                            "maxTokens": max_tokens,
                            "temperature": temperature
                        },
                        toolConfig=tool_config
                    )
                    
                    # Rest of the existing Bedrock handling code remains the same...
                    # Log the raw response for debugging
                    st.sidebar.write("Initial Response:")
                    st.sidebar.json(response)
                    # Check if the model is requesting to use a tool
                    stop_reason = response.get('stopReason', '')
                    if stop_reason == 'tool_use':
                        st.sidebar.write("### Tool Use Detected")
                        # Extract the tool use details
                        output = response.get('output', {})
                        message = output.get('message', {})
                        contents = message.get('content', [])
                        # Find the toolUse content
                        tool_use = None
                        for content in contents:
                            if 'toolUse' in content:
                                tool_use = content.get('toolUse', {})
                                break
                        if tool_use:
                            # Extract the tool call details
                            tool_call = tool_use
                            tool_use_id = tool_call.get('toolUseId')
                            tool_name = tool_call.get('name')  # This is the name as it appears in Bedrock's response
                            tool_input = tool_call.get('input', {})
                            # Log the tool call details
                            st.sidebar.write(f"Executing tool: {tool_name}")
                            st.sidebar.write(f"Tool input: {json.dumps(tool_input)}")
                            st.sidebar.write(f"Tool input type: {type(tool_input)}")
                            st.sidebar.write(f"Tool input keys: {list(tool_input.keys())}")
                            st.sidebar.write(f"Raw tool use object:\n{json.dumps(tool_call, indent=2)}")
                            # IMPORTANT: Store the original tool name exactly as it appears in Bedrock's response
                            bedrock_tool_name = tool_name  # Store the original Bedrock tool name without modification
                            try:
                                # Use the BedrockMcpAdapter to execute the tool call
                                st.sidebar.write("### Executing MCP Tool Call")
                                mcp_result = st.session_state.mcp_adapter.execute_tool(bedrock_tool_name, tool_input)
                                # Log the response for debugging
                                st.sidebar.write("### MCP Response:")
                                st.sidebar.json(mcp_result)
                                # Extract the result content from the MCP response
                                if "error" in mcp_result:
                                    st.sidebar.error(f"MCP server returned an error: {json.dumps(mcp_result['error'], indent=2)}")
                                    result_content = {"error": mcp_result.get('error', {}).get('message', 'Unknown error')}
                                else:
                                    result_content = mcp_result.get('result', mcp_result)
                            except Exception as e:
                                st.sidebar.error(f"Error executing MCP tool: {e}")
                                result_content = {"error": str(e)}
                            # Compose the tool result message for Bedrock
                            tool_result_message = {
                                "role": "user",
                                "content": [
                                    {"toolResult": {
                                        "toolUseId": tool_use_id,
                                        "content": [{"json": result_content}]
                                    }}
                                ]
                            }
                            # Continue the conversation with the tool result
                            messages_for_model.append(tool_result_message)
                            # Call Bedrock again with the updated conversation
                            response2 = bedrock_runtime.converse(
                                modelId=model_id,
                                messages=messages_for_model,
                                system=system_prompt,
                                inferenceConfig={
                                    "maxTokens": max_tokens,
                                    "temperature": temperature
                                },
                                toolConfig=tool_config
                            )
                            st.sidebar.write("Follow-up Response:")
                            st.sidebar.json(response2)
                            # Show Claude's answer in chat
                            output2 = response2.get('output', {})
                            message2 = output2.get('message', {})
                            final_text = ""
                            for content in message2.get('content', []):
                                if 'text' in content:
                                    final_text += content['text']
                            if final_text:
                                st.session_state.messages.append({"role": "assistant", "content": final_text})
                                with st.chat_message("assistant"):
                                    st.markdown(final_text)
                        else:
                            st.warning("No toolUse block found in Bedrock response.")
                    else:
                        # If Claude just responds with text, show it
                        output = response.get('output', {})
                        message = output.get('message', {})
                        final_text = ""
                        for content in message.get('content', []):
                            if 'text' in content:
                                final_text += content['text']
                        if final_text:
                            st.session_state.messages.append({"role": "assistant", "content": final_text})
                            with st.chat_message("assistant"):
                                st.markdown(final_text)
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    
                    # Create a more detailed error message
                    error_message = f"Error: {str(e)}"
                    st.error(error_message)
                    
                    # Log detailed error information in the sidebar for debugging
                    st.sidebar.write("Error Details:")
                    st.sidebar.code(error_details)
                    
                    # Try to extract more information about the error
                    if "SSL" in str(e) or "certificate" in str(e):
                        st.sidebar.warning("SSL Certificate Error: The Bedrock service is having trouble with the MCP server's SSL certificate.")
                        st.sidebar.info("Possible solutions: Use properly signed certificates for your MCP servers or configure Bedrock to accept self-signed certificates.")
                    elif "timeout" in str(e).lower():
                        st.sidebar.warning("Timeout Error: The request to the MCP server timed out.")
                        st.sidebar.info("Possible solutions: Check network connectivity, increase timeout settings, or verify the MCP server is responding quickly enough.")
                    elif "connect" in str(e).lower():
                        st.sidebar.warning("Connection Error: Could not connect to the MCP server.")
                        st.sidebar.info("Possible solutions: Verify the MCP server URL is correct and the server is running. Check network connectivity and security group settings.")
                    
                    # Add the error message to the chat history
                    st.session_state.messages.append({"role": "assistant", "content": error_message})

# Display commit ID in bottom right corner
st.markdown(f"<div style='position: fixed; right: 10px; bottom: 10px; font-size: 12px; color: gray;'>Version: {commit_id}</div>", unsafe_allow_html=True)