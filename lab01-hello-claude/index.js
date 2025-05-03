// Import the core MCP server components from the SDK
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
// Import the stdio transport for terminal-based communication
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
// Import zod for schema validation of tool parameters
import { z } from "zod";

// Create an MCP server with configuration parameters
const server = new McpServer({
  name: "Hello Claude",     // Name of the server displayed to Claude Desktop
  version: "1.0.0",         // Version of this server implementation
  protocolVersion: "2024-03-01"  // MCP protocol version being implemented
});

// Add a simple hello world tool with an optional parameter
server.tool(
  "hello",                        // Tool name - used for invocation
  "Say hello to someone",         // Tool description - helps users understand the purpose
  { name: z.string().optional() }, // Parameter schema - 'name' is optional and must be a string
  async ({ name = "World" }) => ({  // Handler function with default parameter value
    content: [{ type: "text", text: `Hello, ${name}!` }]  // Response format with text content
  })
);

// Add a simple echo tool with a required parameter
server.tool(
  "echo",                     // Tool name
  "Echo back a message",      // Tool description
  { message: z.string() },     // Parameter schema - 'message' is required and must be a string
  async ({ message }) => ({    // Handler function with no default (parameter is required)
    content: [{ type: "text", text: `You said: ${message}` }]  // Response format
  })
);

// Add a dynamic greeting resource with a URI template
server.resource(
  "greeting",                                      // Resource name
  new ResourceTemplate("greeting://{name}",         // URI template with a variable part {name}
                      { list: undefined }),         // No list method provided (undefined)
  async (uri, { name }) => ({                       // Handler function that receives URI and extracted parameters
    contents: [{
      uri: uri.href,                                 // Include the full URI in the response
      text: `Greetings, ${name}!`                    // Generate dynamic content based on the {name} parameter
    }]
  })
);

// Log startup
console.error('Hello Claude MCP server starting...');

// Initialize the transport layer for communication
const transport = new StdioServerTransport();  // Use stdin/stdout for communication (works with CLI tools)

// Connect the server to the transport and handle connection states
await server.connect(transport)
  .then(() => {
    // Success handler - server is now listening for requests
    console.error('Server connected to stdio transport. Waiting for requests...');
  })
  .catch(error => {
    // Error handler - log the error and exit with non-zero code
    console.error('Error connecting to transport:', error);
    process.exit(1);
  });
