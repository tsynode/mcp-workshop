# Model Context Protocol (MCP) Labs

This repository contains a series of labs for learning how to build and use Model Context Protocol (MCP) servers. Each lab builds on the previous one to help you understand how to create MCP-compatible tools and resources for AI models.

## Lab Structure

- **Lab 01: Hello World MCP Server** - A minimal MCP server implementation with basic tools and resources
- *(More labs will be added in the future)*

## What is MCP?

The Model Context Protocol (MCP) is a standardized way for AI models to interact with external tools and data sources. MCP enables AI models like Claude to:

- Access data through resources
- Perform actions through tools
- Get contextual prompts

### MCP Architecture

The diagram below illustrates the basic architecture of an MCP server and how it interacts with AI models:

```mermaid
graph TD
    A[AI Model] <-->|MCP Protocol| B[MCP Server]
    B -->|Tools| C[Tool: hello]
    B -->|Tools| D[Tool: echo]
    B -->|Resources| E["Resource: greeting://name"]
    
    subgraph "MCP Server Components"
        B
        C
        D
        E
    end
    
    subgraph "Transport Layer"
        F[stdio Transport]
    end
    
    B <--> F
```

In this architecture:
- The AI model communicates with the MCP server using the standardized protocol
- The server exposes tools that can perform actions
- The server provides resources that can be accessed via URI templates
- Communication happens through a transport layer (e.g., stdio for CLI tools)

## Getting Started

Each lab directory contains its own README with specific instructions. Start with Lab 01 to learn the basics of MCP server implementation.

```bash
cd lab01-hello-world-server
# Be sure to read the README.md in this directory for detailed instructions
cat README.md
```

The lab01 README contains comprehensive instructions for building, running, and testing your MCP server, along with explanations of each component.

## Requirements

- Node.js (v16+)
- Docker
- npm or yarn

## Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Anthropic Claude Documentation](https://docs.anthropic.com/en/docs/agents-and-tools/mcp)
