# Hello Claude: Interactive MCP Server

A minimal Model Context Protocol (MCP) server implementation with Claude Desktop integration. This lab demonstrates how to create a simple MCP-compatible server and connect it to Claude for interactive testing.

## Learning Objectives

By the end of this lab, you will:
- Understand the MCP architecture (host, client, server)
- Build and test a simple MCP server with multiple tools
- Connect an MCP server to Claude Desktop
- Understand how MCP enables AI portability across different platforms
- Recognize how this pattern applies to real-world systems

## Understanding MCP Architecture

Before we start coding, let's understand the MCP architecture:

- **Host** (Claude Desktop): The application that needs to perform actions
- **Client**: Part of the host that manages connections to MCP servers  
- **Server** (Your Docker container): Provides tools that the AI can use

This architecture is universal - while we're using Claude Desktop today, the same pattern works with Amazon Bedrock, OpenAI, or any other AI service that supports MCP.

## Requirements

- **Docker**: All code runs in containers, no local dependencies needed
- **Claude Desktop**: For interactive testing with the AI agent
- **Internet Connection**: The first test run will download the MCP Inspector package via npx

## What is MCP?

The Model Context Protocol (MCP) is a standardized way for AI models to interact with external tools and data sources. This implementation serves as a minimal working example that can be used as a foundation for more complex MCP servers.

## Features

- **Tools**: 
  - `hello`: Says hello to someone (demonstrates optional parameters)
  - `echo`: Echoes back a message (demonstrates required parameters)
  - `get-system-info`: Returns system information (demonstrates real-world patterns)
- **Resource Template**: `greeting://{name}` - Dynamically generates greetings
- **Protocol**: MCP 2024-03-01 with stdio transport for compatibility

## Docker Usage

### Build the Docker Image

```bash
# Build the Docker image
docker build -t hello-claude-server .
```

**What this does**: Creates a Docker image containing the MCP server and all its dependencies.

**Expected outcome**: A successful build with output ending in "naming to docker.io/library/hello-mcp-server:latest".

### Run the Docker Container

```bash
# Run the Docker container (in a new terminal window)
docker run -i --rm hello-claude-server
```

**What this does**: Starts the MCP server in a Docker container with interactive mode.

**Expected outcome**: The terminal will display "Hello World MCP server starting..." followed by "Server connected to stdio transport. Waiting for requests..." and then wait for input. 

**Note**: This command will not return control to your terminal as the server continues to run and wait for requests. Open a new terminal window for subsequent commands, or use Ctrl+C to stop the server when you're done.

## Testing

### Using the Test Script

The test script runs all tests against a Docker container for consistency and reliability.

```bash
# First, make the test script executable
chmod +x test-mcp.sh

# Run the basic test suite
./test-mcp.sh

# Run with the MCP Inspector CLI mode
./test-mcp.sh --inspector
```

**What this does**: 
- Basic mode: Runs a comprehensive test suite that verifies all functionality of the MCP server
- Inspector mode: Runs additional CLI-based inspector tests that show detailed results

**Expected outcome**: A series of test results showing successful tool discovery, resource template discovery, and tool invocation.


### Using MCP Inspector

For more detailed testing, the test script includes an inspector mode that runs CLI-based inspector tests:

```bash
# Run the MCP Inspector CLI tests
./test-mcp.sh --inspector
```

The inspector mode:
- Creates a test container
- Runs a series of non-interactive Inspector commands
- Shows detailed results from tools and resources
- Completes automatically
- Cleans up the container when done

**What this does**: The MCP Inspector CLI provides a way to test specific aspects of your server with detailed output.

**Expected outcome**: Detailed test results showing your MCP server's capabilities and responses.

## Interactive Testing with Claude Desktop

The primary focus of this lab is to experience how Claude Desktop interacts with your MCP server in real-time. This provides a practical understanding of how AI agents discover and use MCP tools.

### Setup Process

1. **Build and Start the MCP Server**:

```bash
# Build the Docker image
docker build -t hello-claude-server .

# Start a container that stays running in the background
docker run -d --name hello-claude-server hello-claude-server sleep infinity
```

2. **Configure Claude Desktop**:

   This lab includes a pre-configured `claude_desktop_config.json` file that tells Claude Desktop how to connect to your MCP server.

```bash
# For macOS
cp claude_desktop_config.json "$HOME/Library/Application Support/Claude/"

# For Windows (uncomment if needed)
# cp claude_desktop_config.json "$env:APPDATA\Claude\"

# For Linux (uncomment if needed)
# cp claude_desktop_config.json "$HOME/.config/Claude/"
```

3. **Restart Claude Desktop** to load the new configuration

### Interacting with Your MCP Tools

Once configured, start a new conversation in Claude Desktop and try these examples:

#### Basic Tool Usage
- "Can you use the hello tool to greet me?"
- "Use the echo tool with the message 'Hello from MCP!'"

#### Exploring Tool Capabilities
- "What MCP tools do you have access to?"
- "What parameters does the hello tool accept?"

#### System Information
- "What system information can you get?"
- "Check the current system status"

#### Creative Examples
- "Use the echo tool to repeat this haiku about AI"
- "Use the hello tool to greet me in Spanish"

Claude will connect to your MCP server, discover the available tools, and use them as requested. You'll see the entire interaction flow, including tool discovery, parameter validation, and response handling.

### Reality Check

🌍 **Real-World Context**:
- These simple tools demonstrate the MCP pattern
- In production, tools would connect to databases, APIs, and other services
- This server could run anywhere - your laptop, AWS Lambda, Azure Functions, or your own data center
- The same MCP server can be used by different AI services, not just Claude Desktop

### Cleanup

```bash
# Stop and remove the MCP server container
docker stop hello-claude-server
docker rm hello-claude-server

# Remove the Docker image (optional)
docker rmi hello-claude-server
```

**What this does**: Stops and removes the container used for Claude Desktop integration, and optionally removes the Docker image.

## Project Files

- `index.js` - Server implementation with tool and resource definitions
- `package.json` - Node.js dependencies and project metadata
- `Dockerfile` - Docker configuration for containerization
- `test-mcp.sh` - Comprehensive test script
- `claude_desktop_config.json` - Configuration template for Claude Desktop integration

## What's Next?

This lab introduced the fundamentals of MCP. In upcoming labs, you'll learn:

- **Lab 2**: Build multiple MCP servers that work together (product catalog + order management)
- **Lab 3**: Deploy MCP servers to the cloud (AWS)
- **Lab 4**: Connect MCP servers to production AI services (Amazon Bedrock)

**Key Insight**: The pattern you learned here is universal. Any AI service that supports MCP can connect to any MCP server, making your tools truly portable across different AI platforms.

## Resources

- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) - Official TypeScript implementation
- [Model Context Protocol Specification](https://modelcontextprotocol.io) - Official protocol documentation
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector) - Testing tool for MCP servers
- [Anthropic Claude Documentation](https://docs.anthropic.com/en/docs/agents-and-tools/mcp) - Claude's MCP integration
- [MCP Server Examples](https://github.com/madhukarkumar/anthropic-mcp-servers) - Community examples
