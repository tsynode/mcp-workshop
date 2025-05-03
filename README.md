# Model Context Protocol (MCP) Labs

This repository contains a series of labs for learning how to build and use Model Context Protocol (MCP) servers and integrate them with AI Agents.

## What is MCP?

The Model Context Protocol (MCP) is a standardized protocol that enables AI models to interact with external tools and data sources. MCP follows a client-server architecture:

- **Host**: The application that needs AI capabilities
- **Client**: Part of the host that manages connections to MCP servers
- **Server**: Provides tools and resources that the AI can use

MCP enables AI models to:

- **Execute Tools**: Perform actions like searching, calculating, or accessing external systems
- **Access Resources**: Retrieve data from structured sources via URI templates
- **Get Contextual Information**: Receive additional context to improve responses

This standardized approach allows AI capabilities to be portable across different platforms and models, creating a consistent interface for AI-powered functionality.

## Lab Structure

- **Lab 01: Hello Claude** - A minimal MCP server with Claude Desktop integration for interactive testing
- **Lab 02: Retail MCP Servers** - Multiple MCP servers working together for a retail use case
- *(More labs will be added in the future)*

## Getting Started

Each lab directory contains its own README with specific instructions:

1. Start with **Lab 01** to learn the basics of MCP server implementation and Claude Desktop integration:
```bash
cd lab01-hello-claude
# Be sure to read the README.md in this directory for detailed instructions
cat README.md
```

2. Continue with **Lab 02** to explore how multiple MCP servers can work together:
```bash
cd lab02-retail-mcp-servers
cat README.md
```

## Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Anthropic Claude Documentation](https://docs.anthropic.com/en/docs/agents-and-tools/mcp)
