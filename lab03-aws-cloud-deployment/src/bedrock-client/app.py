import streamlit as st
import boto3
import json
import os
import subprocess

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
    ["anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0", "anthropic.claude-3-5-sonnet-20240620-v1:0", "anthropic.claude-3-7-sonnet-20240620-v1:0"],
    index=3  # Default to Claude 3.7 Sonnet
)

# Debug information in sidebar
st.sidebar.title("Debug Info")
st.sidebar.write("Environment Variables:")
st.sidebar.write(f"PRODUCT_MCP_SERVER_URL: {os.environ.get('PRODUCT_MCP_SERVER_URL', 'Not set')}")
st.sidebar.write(f"ORDER_MCP_SERVER_URL: {os.environ.get('ORDER_MCP_SERVER_URL', 'Not set')}")

# Get MCP server URLs from environment variables or use defaults
product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL', 'https://mcp-prod-alb-989631483.us-west-2.elb.amazonaws.com/mcp')
order_server_url = os.environ.get('ORDER_MCP_SERVER_URL', 'https://mcp-order-alb-912981373.us-west-2.elb.amazonaws.com/mcp')

# Define your MCP tools for Bedrock Converse API
tool_config = {
    "tools": [
        {
            "toolSpec": {
                "name": "product-server",
                "description": "Get product information from the retail catalog",
                "inputSchema": {
                    "mcp": {
                        "url": product_server_url
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "order-server",
                "description": "Place and manage orders for products",
                "inputSchema": {
                    "mcp": {
                        "url": order_server_url
                    }
                }
            }
        }
    ]
}

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
                            "type": "text",
                            "text": msg["content"]
                        }
                    ]
                })
            
            # Set inference parameters based on model
            max_tokens = 4096
            temperature = 0.7
            
            # Call the converse API with the selected model
            response = bedrock_runtime.converse(
                modelId=model_id,  # Use the selected model from sidebar
                messages=messages_for_model,
                system=[{"text": "You are a retail assistant that can help customers find products and place orders."}],
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature
                },
                toolConfig=tool_config
            )
            
            # Process the response from the Bedrock Converse API
            assistant_response = ""
            tool_usage = ""
            
            # Extract the content from the response
            output = response.get('output', {})
            message = output.get('message', {})
            contents = message.get('content', [])
            
            for content in contents:
                if content.get('type') == 'text':
                    assistant_response += content.get('text', '')
                elif content.get('type') == 'tool_use':
                    tool_name = content.get('name', 'unknown')
                    tool_input = json.dumps(content.get('input', {}), indent=2)
                    tool_usage += f"\n\n**Tool Used: {tool_name}**\n```json\n{tool_input}\n```\n"
                elif content.get('type') == 'tool_result':
                    tool_result = json.dumps(content.get('content', {}), indent=2)
                    tool_usage += f"\n**Tool Result:**\n```json\n{tool_result}\n```\n"
            
            # Add tool usage information if any tools were used
            if tool_usage:
                assistant_response += "\n\n---\n" + tool_usage
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            with st.chat_message("assistant"):
                st.markdown(assistant_response)
                
        except Exception as e:
            error_message = f"Error: {str(e)}"
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})

# Display commit ID in bottom right corner
st.markdown(f"<div style='position: fixed; right: 10px; bottom: 10px; font-size: 12px; color: gray;'>Version: {commit_id}</div>", unsafe_allow_html=True)
