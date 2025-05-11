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

# Add model selection in sidebar
st.sidebar.title("Model Settings")
model_id = st.sidebar.selectbox(
    "Select Claude model",
    ["anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0", "anthropic.claude-3-5-sonnet-20240620-v1:0", "anthropic.claude-3-7-sonnet-20250219-v1:0"],
    index=1  # Default to Claude 3 Haiku as requested
)

# Debug information in sidebar
st.sidebar.title("Debug Info")
st.sidebar.write("Environment Variables:")
st.sidebar.write(f"PRODUCT_MCP_SERVER_URL: {os.environ.get('PRODUCT_MCP_SERVER_URL', 'Not set')}")
st.sidebar.write(f"ORDER_MCP_SERVER_URL: {os.environ.get('ORDER_MCP_SERVER_URL', 'Not set')}")

# Get MCP server URLs from environment variables or use defaults
product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL', 'https://mcp-prod-alb-989631483.us-west-2.elb.amazonaws.com/mcp')
order_server_url = os.environ.get('ORDER_MCP_SERVER_URL', 'https://mcp-order-alb-912981373.us-west-2.elb.amazonaws.com/mcp')

# Initialize the BedrockMcpAdapter
mcp_adapter = BedrockMcpAdapter()

# Register MCP servers
st.sidebar.write("### MCP Server Registration")
mcp_adapter.register_server('product-server', product_server_url)
mcp_adapter.register_server('order-server', order_server_url)

# Discover tools from MCP servers
st.sidebar.write("### MCP Tool Discovery")

# Discover tools from the product server
product_tools_count = mcp_adapter.discover_tools('product-server')
if product_tools_count > 0:
    st.sidebar.success(f"✅ Product Server: {product_tools_count} tools discovered")
else:
    st.sidebar.warning("⚠️ Product Server: No tools discovered")
    
# Discover tools from the order server
order_tools_count = mcp_adapter.discover_tools('order-server')
if order_tools_count > 0:
    st.sidebar.success(f"✅ Order Server: {order_tools_count} tools discovered")
else:
    st.sidebar.warning("⚠️ Order Server: No tools discovered")

# Get the Bedrock tool configuration with sanitized names
tool_config = mcp_adapter.get_tool_config()

# Log the tool configuration for debugging
st.sidebar.write("### Bedrock Tool Configuration")
st.sidebar.json(tool_config)

# Set up Streamlit UI
st.title("Retail MCP Demo with Amazon Bedrock")
st.subheader("Ask about products or place an order")

# Session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []
    
# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Mode Switcher ---
mode = st.radio("Select Mode", ["Agentic Bedrock Chat", "Manual MCP Tool Tester"], horizontal=True)

if mode == "Manual MCP Tool Tester":
    st.subheader("MCP Tool Tester (Bypass Bedrock)")
    # Let user choose MCP server
    tool_server = st.selectbox("Select MCP Server", ["product-server", "order-server"])
    if tool_server == "product-server":
        mcp_url = product_server_url
        available_tools = mcp_adapter.get_tools_for_server("product-server")
    elif tool_server == "order-server":
        mcp_url = order_server_url
        available_tools = mcp_adapter.get_tools_for_server("order-server")
    else:
        mcp_url = product_server_url
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
                            'Accept': 'application/json'
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
    st.subheader("Agentic Bedrock Chat (Claude + MCP)")
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
                # Call the converse API with the selected model
                response = bedrock_runtime.converse(
                    modelId=model_id,  # Use the selected model from sidebar
                    messages=messages_for_model,
                    system=system_prompt,
                    inferenceConfig={
                        "maxTokens": max_tokens,
                        "temperature": temperature
                    },
                    toolConfig=tool_config
                )
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
                            mcp_result = mcp_adapter.execute_tool(bedrock_tool_name, tool_input)
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
                st.error(f"Error in Bedrock agentic chat: {e}")

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
                    # We must use this exact same name when sending the result back
                    bedrock_tool_name = tool_name  # Store the original Bedrock tool name without modification
                    
                    try:
                        # Use the BedrockMcpAdapter to execute the tool call
                        st.sidebar.write("### Executing MCP Tool Call")
                        mcp_result = mcp_adapter.execute_tool(bedrock_tool_name, tool_input)
                        
                        # Log the response for debugging
                        st.sidebar.write("### MCP Response:")
                        st.sidebar.json(mcp_result)
                        
                        # Extract the result content from the MCP response
                        if "error" in mcp_result:
                            st.sidebar.error(f"MCP server returned an error: {json.dumps(mcp_result['error'], indent=2)}")
                            result_content = {"error": mcp_result.get('error', {}).get('message', 'Unknown error')}
                        elif "result" in mcp_result:
                            result_content = mcp_result["result"]
                        else:
                            result_content = {"message": "Unexpected response format from MCP server"}
                        
                        # FINAL SOLUTION: Follow the exact AWS documentation pattern
                        # According to AWS docs, we need to construct a conversation with:
                        # 1. Original user message
                        # 2. Assistant's tool use message (from Bedrock response)
                        # 3. User's tool result message (what we're constructing now)
                        
                        # First, extract the original user message from the conversation history
                        original_user_message = None
                        for msg in messages_for_model:
                            if msg["role"] == "user":
                                original_user_message = msg
                                break
                        
                        if not original_user_message:
                            # Create a default user message if none exists
                            original_user_message = {
                                "role": "user",
                                "content": [{"text": "Show me product information"}]
                            }
                        
                        # Now construct the assistant's message with the tool use exactly as Bedrock sent it
                        assistant_message = {
                            "role": "assistant",
                            "content": [
                                {"toolUse": {
                                    "toolUseId": tool_use_id,
                                    "name": bedrock_tool_name,  # Use the EXACT name from Bedrock
                                    "input": tool_input
                                }}
                            ]
                        }
                        
                        # Finally, construct the user's message with the tool result
                        tool_result_message = {
                            "role": "user",
                            "content": [
                                {"toolResult": {
                                    "toolUseId": tool_use_id,
                                    "content": [{"json": result_content}]
                                }}
                            ]
                        }
                        
                        # Create the conversation with exactly these three messages in order
                        conversation = [
                            original_user_message,
                            assistant_message,
                            tool_result_message
                        ]
                        
                        # Log the conversation for debugging
                        st.sidebar.write("Final conversation structure:")
                        st.sidebar.json(conversation)
                        
                        # Log the conversation for debugging
                        st.sidebar.write("MCP Tool Result Conversation:")
                        st.sidebar.json(conversation)
                        
                        # Continue the conversation with the tool result
                        response = bedrock_runtime.converse(
                            modelId=model_id,
                            messages=conversation,
                            system=system_prompt,
                            inferenceConfig={
                                "maxTokens": max_tokens,
                                "temperature": temperature
                            },
                            toolConfig=tool_config
                        )                      
                        st.sidebar.write("Final Response:")
                        st.sidebar.json(response)
                    except Exception as e:
                        st.sidebar.error(f"Error executing tool call: {str(e)}")
                        import traceback
                        st.sidebar.code(traceback.format_exc())
            
            # Process the response from the Bedrock Converse API
            assistant_response = ""
            tool_usage = ""
            
            # Extract the content from the response
            output = response.get('output', {})
            message = output.get('message', {})
            contents = message.get('content', [])
            
            for content in contents:
                if 'text' in content:
                    assistant_response += content.get('text', '')
                elif 'toolUse' in content:
                    tool_use = content.get('toolUse', {})
                    tool_name = tool_use.get('name', 'unknown')
                    tool_input = json.dumps(tool_use.get('input', {}), indent=2)
                    tool_usage += f"\n\n**Tool Used: {tool_name}**\n```json\n{tool_input}\n```\n"
                elif 'toolResult' in content:
                    tool_result = content.get('toolResult', {})
                    result_content = tool_result.get('content', [])
                    result_text = ''
                    for item in result_content:
                        if 'json' in item:
                            result_text = json.dumps(item.get('json', {}), indent=2)
                        elif 'text' in item:
                            result_text = item.get('text', '')
                    tool_usage += f"\n**Tool Result:**\n```json\n{result_text}\n```\n"
            
            # Add tool usage information if any tools were used
            if tool_usage:
                assistant_response += "\n\n---\n" + tool_usage
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            with st.chat_message("assistant"):
                st.markdown(assistant_response)
                
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
