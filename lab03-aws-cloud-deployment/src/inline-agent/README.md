# Inline Agent SDK Implementation for MCP Workshop

This directory contains a proof-of-concept implementation of the Amazon Bedrock Inline Agent SDK for interacting with MCP servers.

## Overview

This implementation demonstrates how to use the Inline Agent SDK to interact with the product and order MCP servers running on ECS Fargate. It provides a more streamlined approach to MCP integration compared to the direct Bedrock Converse API implementation.

## Key Features

- Uses Amazon Bedrock Inline Agent SDK for simplified MCP integration
- Supports both product and order MCP servers
- Provides a Streamlit-based UI similar to the original implementation
- Handles SSE responses from MCP servers automatically
- Includes comprehensive debugging features:
  - Raw request/response logging for MCP server interactions
  - Tool call tracing and inspection
  - Detailed error handling with specific guidance
  - Environment variable validation

## Setup Instructions

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment variables for your MCP server URLs (or they will use the default URLs):

```bash
export PRODUCT_MCP_SERVER_URL="https://your-product-server-url/mcp"
export ORDER_MCP_SERVER_URL="https://your-order-server-url/mcp"
```

3. Run the Streamlit app:

```bash
streamlit run app.py
```

## How It Works

The implementation uses the following components from the Inline Agent SDK:

- `MCPHttp`: Client for making HTTP requests to MCP servers
- `ActionGroup`: Abstraction for organizing and managing tool calls to different MCP servers
- `InlineAgent`: Main class for interacting with the Bedrock model and handling the conversation flow

The app creates two action groups, one for each MCP server, and configures them with the appropriate MCP clients. When a user sends a message, the Inline Agent handles the conversation flow, including making tool calls to the MCP servers when needed.

## Comparison with Original Implementation

This implementation offers several advantages over the original direct Bedrock Converse API implementation:

1. **Simplified MCP Integration**: The SDK abstracts away much of the complexity of making MCP requests and handling responses.
2. **Built-in Support for SSE Responses**: The SDK has native support for MCP servers that use Server-Sent Events (SSE).
3. **Cleaner Tool Call Handling**: The ActionGroup abstraction provides a cleaner way to organize and manage tool calls.
4. **Async Support**: The SDK uses async/await patterns which can be more efficient for handling network requests.
5. **Enhanced Debugging**: Includes comprehensive debugging tools for inspecting raw requests/responses, tracing tool calls, and diagnosing issues.
6. **Improved Error Handling**: Provides more specific guidance based on the type of error encountered, making troubleshooting easier.

## Limitations

- The Inline Agent SDK is still in development and may have limitations or bugs.
- Some customization options available in the direct Bedrock Converse API implementation may not be available in the SDK.
