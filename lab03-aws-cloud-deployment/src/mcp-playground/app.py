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

# Define your MCP tools for Bedrock Converse API
tool_config = {
    "tools": [
        {
            "toolSpec": {
                "name": "product-server",
                "description": "Get product information from the retail catalog. Use this to find products, check prices, and get product details.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "productId": {
                                "type": "string",
                                "description": "ID of the product to get details for"
                            },
                            "category": {
                                "type": "string",
                                "description": "Category of products to search for"
                            },
                            "maxPrice": {
                                "type": "number",
                                "description": "Maximum price for filtering products"
                            },
                            "inStockOnly": {
                                "type": "boolean",
                                "description": "Whether to only show products that are in stock"
                            }
                        },
                        "x-mcp": {
                            "url": product_server_url,
                            "insecureTls": True  # Allow self-signed certificates
                        }
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "order-server",
                "description": "Place and manage orders for products. Use this to create orders and check order status.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "productId": {
                                "type": "string",
                                "description": "ID of the product to order"
                            },
                            "quantity": {
                                "type": "number",
                                "description": "Quantity of the product to order"
                            },
                            "orderId": {
                                "type": "string",
                                "description": "ID of the order to check status for"
                            }
                        },
                        "x-mcp": {
                            "url": order_server_url,
                            "insecureTls": True  # Allow self-signed certificates
                        }
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
                            "text": msg["content"]
                        }
                    ]
                })
            
            # Set inference parameters based on model
            max_tokens = 4096
            temperature = 0.7
            
            # Log the tool configuration for debugging
            st.sidebar.write("Tool Configuration:")
            st.sidebar.json(tool_config)
            
            # Add more detailed system prompt to guide the model on using MCP tools
            system_prompt = [
                {"text": "You are a retail assistant that can help customers find products and place orders. "
                        "You have access to two MCP tools: \n"
                        "1. product-server: Use this to get product information from the retail catalog\n"
                        "2. order-server: Use this to place and manage orders for products\n\n"
                        "When asked about products, ALWAYS use the product-server tool.\n"
                        "When asked to place orders, ALWAYS use the order-server tool.\n"
                        "Show your work by explaining what tools you're using and why."}
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
                st.sidebar.write("Tool use detected - executing tool call...")
                
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
                    tool_name = tool_use.get('name', '')
                    tool_input = tool_use.get('input', {})
                    tool_use_id = tool_use.get('toolUseId', '')
                    
                    st.sidebar.write(f"Executing tool: {tool_name}")
                    st.sidebar.write(f"Tool input: {json.dumps(tool_input, indent=2)}")
                    st.sidebar.write(f"Tool input type: {type(tool_input)}")
                    st.sidebar.write(f"Tool input keys: {list(tool_input.keys()) if isinstance(tool_input, dict) else 'Not a dict'}")
                    
                    # Debug the raw tool use object
                    st.sidebar.write("Raw tool use object:")
                    st.sidebar.json(tool_use)
                    
                    # Execute the tool call to the appropriate MCP server
                    import requests
                    
                    # Determine which MCP server to call based on the tool name
                    mcp_url = ''
                    if tool_name == 'product-server':
                        mcp_url = product_server_url
                    elif tool_name == 'order-server':
                        mcp_url = order_server_url
                    
                    if mcp_url:
                        try:
                            # Format the request for the MCP server
                            # The tool name in the MCP server is the method name to call
                            # The tool name from Bedrock is the name of the MCP server, not the method
                            
                            # Determine which method to call based on the tool name and parameters
                            st.sidebar.write("Determining method name based on:")
                            st.sidebar.write(f"Tool name: {tool_name}")
                            st.sidebar.write(f"Tool input keys: {list(tool_input.keys())}")
                            
                            # Use direct string comparison for method names
                            method_name = None
                            
                            if tool_name == "product-server":
                                if 'productId' in tool_input and 'quantity' not in tool_input:
                                    method_name = "get-product"
                                    st.sidebar.write("Selected method: get-product (productId present, quantity not present)")
                                else:
                                    method_name = "search-products"
                                    st.sidebar.write("Selected method: search-products")
                            elif tool_name == "order-server":
                                if 'orderId' in tool_input:
                                    method_name = "check-order-status"
                                    st.sidebar.write("Selected method: check-order-status (orderId present)")
                                else:
                                    method_name = "create-order"
                                    st.sidebar.write("Selected method: create-order")
                            else:
                                st.sidebar.error(f"Unknown tool name: {tool_name}")
                                method_name = "unknown"
                                
                            mcp_request = {
                                "jsonrpc": "2.0",
                                "method": method_name,
                                "params": tool_input,
                                "id": "1"
                            }
                            
                            st.sidebar.write(f"Using method: {method_name}")
                            
                            # Make the request to the MCP server
                            st.sidebar.write(f"Sending request to MCP server: {mcp_url}")
                            st.sidebar.json(mcp_request)
                            
                            # Use verify=False to ignore SSL certificate validation
                            mcp_response = requests.post(
                                mcp_url,
                                json=mcp_request,
                                headers={
                                    'Content-Type': 'application/json',
                                    'Accept': 'application/json, text/event-stream'
                                },
                                verify=False  # Ignore SSL certificate validation
                            )
                            
                            # Parse the response - handle both JSON and SSE formats
                            response_text = mcp_response.text
                            st.sidebar.write(f"Raw MCP response: {response_text}")
                            
                            # Check if the response is in SSE format
                            if response_text.startswith('event:') or '\ndata:' in response_text:
                                # Extract the JSON from the SSE format
                                data_lines = [line for line in response_text.split('\n') if line.startswith('data:')]
                                if data_lines:
                                    json_str = data_lines[0][5:]  # Remove 'data:' prefix
                                    mcp_result = json.loads(json_str)
                                else:
                                    mcp_result = {"error": "Could not parse SSE response"}
                            else:
                                # Regular JSON response
                                mcp_result = mcp_response.json()
                                
                            st.sidebar.write(f"Parsed MCP response: {json.dumps(mcp_result, indent=2)}")
                            
                            # Check for error in response
                            if "error" in mcp_result:
                                st.sidebar.error(f"MCP server returned an error: {json.dumps(mcp_result['error'], indent=2)}")
                                # Create an error message for the tool result
                                error_message = mcp_result.get('error', {}).get('message', 'Unknown error')
                                result = {"error": error_message}
                                # Continue with this result
                            
                            # Extract the result from the MCP response
                            if "result" in mcp_result:
                                result = mcp_result["result"]
                                
                                # Create the tool result
                                # If there was an error, include status: error
                                if "error" in result:
                                    tool_result = {
                                        "toolUseId": tool_use_id,
                                        "content": [{"json": result}],
                                        "status": "error"
                                    }
                                else:
                                    tool_result = {
                                        "toolUseId": tool_use_id,
                                        "content": [{"json": result}]
                                    }
                                
                                # Create a tool result message following AWS documentation pattern
                                tool_result_message = {
                                    "role": "user",
                                    "content": [
                                        {
                                            "toolResult": tool_result
                                        }
                                    ]
                                }
                                
                                st.sidebar.write("Tool result message:")
                                st.sidebar.json(tool_result_message)
                                
                                # Add the tool result message to the conversation history
                                messages_for_model.append(tool_result_message)
                                
                                # Continue the conversation with the updated messages
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
