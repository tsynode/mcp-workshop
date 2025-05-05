import streamlit as st
import boto3
import json
import os
import asyncio
import subprocess
import requests
import datetime
from dotenv import load_dotenv

# Import Inline Agent SDK components
from InlineAgent.tools.mcp import MCPHttp
from InlineAgent.action_group import ActionGroup
from InlineAgent.agent import InlineAgent
from InlineAgent import AgentAppConfig

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(page_title="Retail MCP Demo with Inline Agent", layout="wide")

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

# Get MCP server URLs from environment variables
# These will be set by the ECS task definition in the deployment workflow
product_server_url = os.environ.get('PRODUCT_MCP_SERVER_URL', '')
order_server_url = os.environ.get('ORDER_MCP_SERVER_URL', '')

# Validate MCP server URLs
if not product_server_url or not order_server_url:
    st.error("⚠️ MCP server URLs are not set. Please check your environment variables.")
    st.info("The application expects PRODUCT_MCP_SERVER_URL and ORDER_MCP_SERVER_URL environment variables to be set.")
    st.code("Current values:\nPRODUCT_MCP_SERVER_URL: " + (product_server_url or "Not set") + "\nORDER_MCP_SERVER_URL: " + (order_server_url or "Not set"))

# Add model selection in sidebar
st.sidebar.title("Model Settings")
model_id = st.sidebar.selectbox(
    "Select Claude model",
    ["anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-haiku-20240307-v1:0", "anthropic.claude-3-5-sonnet-20240620-v1:0", "anthropic.claude-3-7-sonnet-20250219-v1:0"],
    index=1  # Default to Claude 3 Haiku
)

# Debug information in sidebar
st.sidebar.title("Debug Info")
st.sidebar.write("Environment Variables:")
st.sidebar.write(f"PRODUCT_MCP_SERVER_URL: {os.environ.get('PRODUCT_MCP_SERVER_URL', 'Not set')}")
st.sidebar.write(f"ORDER_MCP_SERVER_URL: {os.environ.get('ORDER_MCP_SERVER_URL', 'Not set')}")
st.sidebar.write(f"COMMIT_ID: {commit_id}")

# Add a debug panel with expandable sections
with st.sidebar.expander("🔍 Advanced Debugging", expanded=False):
    debug_tabs = st.tabs(["Requests", "Responses", "Tool Calls"])
    
    # Raw Requests Tab
    with debug_tabs[0]:
        st.write("Recent MCP Server Requests:")
        if "debug_info" in st.session_state and "raw_requests" in st.session_state.debug_info:
            for i, req in enumerate(st.session_state.debug_info["raw_requests"]):
                with st.expander(f"Request #{i+1} - {req.get('timestamp', 'Unknown time')}"):
                    st.write(f"URL: {req.get('url', 'Unknown')}")
                    st.write(f"Method: {req.get('method', 'Unknown')}")
                    st.write("Headers:")
                    st.json(req.get('headers', {}))
                    st.write("Body:")
                    st.code(req.get('body', 'No body'), language="json")
        else:
            st.info("No requests logged yet")
    
    # Raw Responses Tab
    with debug_tabs[1]:
        st.write("Recent MCP Server Responses:")
        if "debug_info" in st.session_state and "raw_responses" in st.session_state.debug_info:
            for i, resp in enumerate(st.session_state.debug_info["raw_responses"]):
                with st.expander(f"Response #{i+1} - {resp.get('timestamp', 'Unknown time')}"):
                    st.write(f"Status: {resp.get('status', 'Unknown')}")
                    st.write("Headers:")
                    st.json(resp.get('headers', {}))
                    st.write("Body:")
                    st.code(resp.get('body', 'No body'), language="json")
        else:
            st.info("No responses logged yet")
    
    # Tool Calls Tab
    with debug_tabs[2]:
        st.write("Recent Tool Calls:")
        if "debug_info" in st.session_state and "last_response" in st.session_state.debug_info:
            response = st.session_state.debug_info["last_response"]
            tool_calls = response.get('tool_calls', [])
            
            if tool_calls:
                for i, tool_call in enumerate(tool_calls):
                    with st.expander(f"Tool Call #{i+1} - {tool_call.get('tool_name', 'Unknown tool')}"):
                        st.write("Input:")
                        st.json(tool_call.get('tool_input', {}))
                        st.write("Output:")
                        st.json(tool_call.get('tool_output', {}))
            else:
                st.info("No tool calls in the last response")
        else:
            st.info("No tool calls logged yet")

# Set up Streamlit UI
st.title("Retail MCP Demo with Amazon Bedrock Inline Agent")
st.subheader("Ask about products or place an order")

# Session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Session state for debugging info
if "debug_info" not in st.session_state:
    st.session_state.debug_info = {}
    
# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
user_input = st.chat_input("Type your message here...")

# Function to test MCP server connectivity
def test_mcp_connectivity(url):
    try:
        # Simple JSONRPC ping request
        test_request = {
            "jsonrpc": "2.0",
            "method": "ping",
            "params": {},
            "id": "connectivity-test"
        }
        
        response = requests.post(
            url,
            json=test_request,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            verify=False,  # Ignore SSL certificate validation
            timeout=5
        )
        
        return {
            "status": "success" if response.status_code == 200 else "error",
            "status_code": response.status_code,
            "response": response.text
        }
    except Exception as e:
        error_msg = f"Error running conversation: {str(e)}"
        st.error(error_msg)
        
        # Log the error for debugging
        st.session_state.debug_info["last_error"] = {
            "message": error_msg,
            "exception": str(e),
            "exception_type": type(e).__name__,
            "timestamp": str(datetime.datetime.now())
        }
        
        # Provide more helpful error messages based on the exception type
        if "Connection refused" in str(e):
            return "Error: Could not connect to the MCP servers. Please check if they are running and accessible."
        elif "SSL" in str(e) or "certificate" in str(e).lower():
            return "Error: SSL certificate verification failed. This might be due to self-signed certificates on the MCP servers."
        elif "timeout" in str(e).lower():
            return "Error: The request to the MCP servers timed out. Please try again or check your network connection."
        elif "unauthorized" in str(e).lower() or "403" in str(e):
            return "Error: Unauthorized access to the MCP servers. Please check your credentials."
        else:
            return f"Error: {str(e)}"

# Function to process response and extract content
def process_response(response):
    """Process the response from the Inline Agent and extract content."""
    # For debugging
    st.sidebar.write("Raw Response:")
    st.sidebar.json(response)
    
    # Store in session state for debugging
    st.session_state.debug_info["last_response"] = response
    
    # Extract the content from the response
    assistant_response = response.get('answer', '')
    
    # Extract tool usage information if available
    tool_usage = ""
    tool_calls = response.get('tool_calls', [])
    
    if tool_calls:
        st.sidebar.write(f"Tool Calls: {len(tool_calls)}")
    
    for i, tool_call in enumerate(tool_calls):
        tool_name = tool_call.get('tool_name', 'unknown')
        tool_input = json.dumps(tool_call.get('tool_input', {}), indent=2)
        tool_output = json.dumps(tool_call.get('tool_output', {}), indent=2)
        
        st.sidebar.write(f"Tool Call #{i+1}: {tool_name}")
        st.sidebar.write("Input:")
        st.sidebar.json(tool_call.get('tool_input', {}))
        st.sidebar.write("Output:")
        st.sidebar.json(tool_call.get('tool_output', {}))
        
        tool_usage += f"\n\n**Tool Used: {tool_name}**\n```json\n{tool_input}\n```\n"
        tool_usage += f"\n**Tool Result:**\n```json\n{tool_output}\n```\n"
    
    # Add tool usage information if any tools were used
    if tool_usage:
        assistant_response += "\n\n---\n" + tool_usage
    
    return assistant_response

# Main async function to handle the conversation
async def run_conversation(user_input):
    """Run a conversation with the Bedrock model using the Inline Agent SDK."""
    try:
        # Initialize debug info if not already done
        if "debug_info" not in st.session_state:
            st.session_state.debug_info = {}
            
        # Log the user input for debugging
        if "user_inputs" not in st.session_state.debug_info:
            st.session_state.debug_info["user_inputs"] = []
        st.session_state.debug_info["user_inputs"].append({
            "text": user_input,
            "timestamp": str(datetime.datetime.now())
        })
        
        # Validate MCP server URLs
        if not product_server_url or not order_server_url:
            error_msg = "MCP server URLs are not configured. Please check your environment variables."
            st.error(error_msg)
            st.session_state.debug_info["last_error"] = {
                "message": error_msg,
                "timestamp": str(datetime.datetime.now())
            }
            return f"Error: {error_msg}"
            
        # Create MCP clients with detailed logging
        st.sidebar.write("Creating MCP clients...")
        
        # Add a dedicated debug section for raw requests/responses
        if "raw_requests" not in st.session_state.debug_info:
            st.session_state.debug_info["raw_requests"] = []
        if "raw_responses" not in st.session_state.debug_info:
            st.session_state.debug_info["raw_responses"] = []
            
        # Custom request/response handlers for logging
        async def on_request(request):
            # Log the request details
            request_info = {
                "url": str(request.url),
                "method": request.method,
                "headers": dict(request.headers),
                "body": await request.text() if request.body else None,
                "timestamp": str(datetime.datetime.now())
            }
            st.session_state.debug_info["raw_requests"].append(request_info)
            # Keep only the last 5 requests to avoid memory issues
            if len(st.session_state.debug_info["raw_requests"]) > 5:
                st.session_state.debug_info["raw_requests"].pop(0)
            return request
            
        async def on_response(response):
            # Log the response details
            response_info = {
                "status": response.status,
                "headers": dict(response.headers),
                "body": await response.text(),
                "timestamp": str(datetime.datetime.now())
            }
            st.session_state.debug_info["raw_responses"].append(response_info)
            # Keep only the last 5 responses to avoid memory issues
            if len(st.session_state.debug_info["raw_responses"]) > 5:
                st.session_state.debug_info["raw_responses"].pop(0)
            return response
            
        product_mcp_client = await MCPHttp.create(
            url=product_server_url, 
            verify_ssl=False,
            debug=True,  # Enable debug logging
            on_request=on_request,
            on_response=on_response
        )
        order_mcp_client = await MCPHttp.create(
            url=order_server_url, 
            verify_ssl=False,
            debug=True,  # Enable debug logging
            on_request=on_request,
            on_response=on_response
        )
        
        st.sidebar.write("MCP clients created successfully")
        
        try:
            # Create action groups for each MCP server with detailed descriptions
            product_action_group = ActionGroup(
                name="ProductActionGroup",
                description="Get product information from the retail catalog. Use this to find products, check prices, and get product details. Methods: get-product (requires productId), search-products (optional filters: category, maxPrice, inStockOnly).",
                mcp_clients=[product_mcp_client],
            )
            
            order_action_group = ActionGroup(
                name="OrderActionGroup",
                description="Place and manage orders for products. Use this to create orders and check order status. Methods: create-order (requires productId, quantity), check-order-status (requires orderId).",
                mcp_clients=[order_mcp_client],
            )
            
            st.sidebar.write("Action groups created successfully")
            
            # Convert previous messages to the format expected by Inline Agent
            messages_for_model = []
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    messages_for_model.append({"role": "user", "content": msg["content"]})
                elif msg["role"] == "assistant":
                    messages_for_model.append({"role": "assistant", "content": msg["content"]})
            
            st.sidebar.write(f"Conversation history: {len(messages_for_model)} messages")
            
            # Create the agent with the action groups and detailed system prompt
            system_prompt = """
You are a retail assistant that can help customers find products and place orders.

You have access to two MCP tools:
1. ProductActionGroup - Use this to get product information, search products, and check prices.
   - get-product: Get details for a specific product by ID
   - search-products: Search for products with optional filters (category, maxPrice, inStockOnly)

2. OrderActionGroup - Use this to place orders and check order status.
   - create-order: Create a new order for a product (requires productId and quantity)
   - check-order-status: Check the status of an existing order (requires orderId)

When a user asks about products, use the ProductActionGroup to find information.
When a user wants to place an order, use the OrderActionGroup.

Always be helpful, concise, and provide accurate information about products and orders.

If you encounter any errors when using the tools, explain the issue to the user and suggest alternatives.
"""
            
            st.sidebar.write("Creating Inline Agent...")
            agent = InlineAgent(
                foundation_model=model_id,
                instruction=system_prompt,
                agent_name="retail_agent",
                action_groups=[product_action_group, order_action_group],
            )
            
            st.sidebar.write("Invoking agent with user input...")
            # Run the conversation
            st.sidebar.write("Running conversation...")
            response = await agent.invoke(
                input_text=user_input,
                enable_trace=True  # Enable tracing for debugging
            )
            
            # Store the response for debugging
            st.session_state.debug_info["last_response"] = response.to_dict()
            
            # Log any tool calls for debugging
            if "tool_calls" not in st.session_state.debug_info:
                st.session_state.debug_info["tool_calls"] = []
                
            # Extract tool calls from the response if available
            if hasattr(response, 'trace') and response.trace:
                for event in response.trace.events:
                    if event.event_type == "tool_call":
                        st.session_state.debug_info["tool_calls"].append({
                            "tool_name": event.tool_name,
                            "tool_input": event.tool_input,
                            "tool_output": event.tool_output,
                            "timestamp": str(datetime.datetime.now())
                        })
            
            st.sidebar.write("Conversation completed successfully")
            
            # Return the response
            return response.output
        finally:
            # Clean up MCP clients
            st.sidebar.write("Cleaning up MCP clients...")
            await product_mcp_client.cleanup()
            await order_mcp_client.cleanup()
            st.sidebar.write("MCP clients cleaned up")
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        # Create a more detailed error message
        error_message = f"Error: {str(e)}"
        st.error(error_message)
        
        # Log detailed error information in the sidebar for debugging
        st.sidebar.write("Error Details:")
        st.sidebar.code(error_details)
        
        # Provide more specific guidance based on the error
        if "SSL" in str(e) or "certificate" in str(e):
            st.sidebar.warning("SSL Certificate Error: The Bedrock service is having trouble with the MCP server's SSL certificate.")
            st.sidebar.info("Possible solutions: Use properly signed certificates for your MCP servers or configure the client to accept self-signed certificates.")
        elif "timeout" in str(e).lower():
            st.sidebar.warning("Timeout Error: The request to the MCP server timed out.")
            st.sidebar.info("Possible solutions: Check network connectivity, increase timeout settings, or verify the MCP server is responding quickly enough.")
        elif "connect" in str(e).lower():
            st.sidebar.warning("Connection Error: Could not connect to the MCP server.")
            st.sidebar.info("Possible solutions: Verify the MCP server URL is correct and the server is running. Check network connectivity and security group settings.")
        
        return error_message

# Handle user input
if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Call the agent with the user input
    with st.spinner("Claude is thinking..."):
        # Run the async function
        assistant_response = asyncio.run(run_conversation(user_input))
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        with st.chat_message("assistant"):
            st.markdown(assistant_response)

# Display commit ID in bottom right corner
st.markdown(f"<div style='position: fixed; right: 10px; bottom: 10px; font-size: 12px; color: gray;'>Version: {commit_id}</div>", unsafe_allow_html=True)
