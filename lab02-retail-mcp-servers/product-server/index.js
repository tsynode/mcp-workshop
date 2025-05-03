// Import the core MCP server components from the SDK
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
// Import the stdio transport for terminal-based communication
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
// Import zod for schema validation of tool parameters
import { z } from "zod";

// Create an MCP server with configuration parameters
const server = new McpServer({
  name: "Retail Product Server",
  version: "1.0.0",
  protocolVersion: "2024-03-01"  // MCP protocol version being implemented
});

// Simulated product database
const products = [
  {
    id: "p001",
    name: "Wireless Headphones",
    description: "Premium noise-cancelling headphones with 30-hour battery",
    price: 199.99,
    category: "Electronics",
    inStock: true,
    quantity: 50
  },
  {
    id: "p002",
    name: "Smart Watch",
    description: "Fitness tracking watch with heart rate monitor",
    price: 299.99,
    category: "Electronics",
    inStock: true,
    quantity: 30
  },
  {
    id: "p003",
    name: "Running Shoes",
    description: "Lightweight running shoes with advanced cushioning",
    price: 129.99,
    category: "Sports",
    inStock: false,
    quantity: 0
  }
];

// Get product by ID
server.tool(
  "get-product",
  "Get detailed information about a specific product",
  { productId: z.string() },
  async ({ productId }) => {
    const product = products.find(p => p.id === productId);
    
    if (!product) {
      return {
        content: [{
          type: "text",
          text: `Product with ID ${productId} not found`
        }]
      };
    }
    
    return {
      content: [{
        type: "text",
        text: JSON.stringify(product, null, 2)
      }]
    };
  }
);

// Search products
server.tool(
  "search-products",
  "Search for products by name or category",
  {
    query: z.string().optional(),
    category: z.string().optional()
  },
  async ({ query, category }) => {
    let results = products;
    
    if (query) {
      const searchQuery = query.toLowerCase();
      results = results.filter(p => 
        p.name.toLowerCase().includes(searchQuery) ||
        p.description.toLowerCase().includes(searchQuery)
      );
    }
    
    if (category) {
      results = results.filter(p => 
        p.category.toLowerCase() === category.toLowerCase()
      );
    }
    
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          count: results.length,
          products: results
        }, null, 2)
      }]
    };
  }
);

console.error('Retail Product Server starting...');

const transport = new StdioServerTransport();
await server.connect(transport);

console.error('Server connected to stdio transport. Waiting for requests...');