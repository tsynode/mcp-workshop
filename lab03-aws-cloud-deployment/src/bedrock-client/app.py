import streamlit as st
import boto3
import json
import os

# Configure page
st.set_page_config(page_title="Retail MCP Demo", layout="wide")

# Set up Bedrock client
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-west-2'
)

# Define your existing MCP servers
mcp_tools = {
    "tools": [
        {
            "name": "product-server",
            "url": "https://mcp-prod-alb-989631483.us-west-2.elb.amazonaws.com/mcp"
        },
        {
            "name": "order-server",
            "url": "https://mcp-order-alb-912981373.us-west-2.elb.amazonaws.com/mcp"
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
            response = bedrock_runtime.converse(
                modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text", 
                                "text": user_input
                            }
                        ]
                    }
                ],
                tools=mcp_tools,
                system="You are a retail assistant that can help customers find products and place orders."
            )
            
            # Process the response
            assistant_response = ""
            tool_usage = ""
            
            for message in response.get('messages', []):
                if message.get('role') == 'assistant':
                    for content in message.get('content', []):
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
