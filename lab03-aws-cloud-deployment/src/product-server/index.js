import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createServer } from "http";
import { z } from "zod";

// Create MCP server instance
const server = new McpServer({
  name: "Retail Product Server (AWS)",
  version: "1.0.0",
  protocolVersion: "2025-03-26"  // Updated protocol version with streaming support
});

// Sample product database (in a real application, this would be in a database)
const products = [
  {
    id: "p001",
    name: "Smartphone X",
    description: "Latest smartphone with advanced camera and long battery life",
    price: 799.99,
    category: "electronics",
    inStock: true,
    imageUrl: "https://example.com/smartphone-x.jpg"
  },
  {
    id: "p002",
    name: "Wireless Headphones",
    description: "Noise-cancelling wireless headphones with 20-hour battery life",
    price: 149.99,
    category: "electronics",
    inStock: true,
    imageUrl: "https://example.com/wireless-headphones.jpg"
  },
  {
    id: "p003",
    name: "Coffee Maker",
    description: "Programmable coffee maker with thermal carafe",
    price: 89.99,
    category: "kitchen",
    inStock: true,
    imageUrl: "https://example.com/coffee-maker.jpg"
  },
  {
    id: "p004",
    name: "Running Shoes",
    description: "Lightweight running shoes with responsive cushioning",
    price: 129.99,
    category: "sports",
    inStock: false,
    imageUrl: "https://example.com/running-shoes.jpg"
  },
  {
    id: "p005",
    name: "Smart Watch",
    description: "Fitness tracker and smartwatch with heart rate monitoring",
    price: 199.99,
    category: "electronics",
    inStock: true,
    imageUrl: "https://example.com/smart-watch.jpg"
  }
];

// Define the get-product tool
server.tool(
  "get-product",
  "Get detailed information about a specific product",
  { productId: z.string() },
  async ({ productId }) => {
    console.log(`Getting product with ID: ${productId}`);
    
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

// Define the search-products tool
server.tool(
  "search-products",
  "Search for products by category, price range, or availability",
  {
    category: z.string().optional(),
    maxPrice: z.number().optional(),
    inStockOnly: z.boolean().optional()
  },
  async ({ category, maxPrice, inStockOnly }) => {
    console.log(`Searching products with filters: category=${category}, maxPrice=${maxPrice}, inStockOnly=${inStockOnly}`);
    
    let filteredProducts = [...products];
    
    if (category) {
      filteredProducts = filteredProducts.filter(p => p.category === category);
    }
    
    if (maxPrice !== undefined) {
      filteredProducts = filteredProducts.filter(p => p.price <= maxPrice);
    }
    
    if (inStockOnly) {
      filteredProducts = filteredProducts.filter(p => p.inStock);
    }
    
    return {
      content: [{
        type: "text",
        text: JSON.stringify(filteredProducts, null, 2)
      }]
    };
  }
);

// Create HTTP server
const PORT = process.env.PORT || 3000;

const httpServer = createServer(async (req, res) => {
  // Set CORS headers to allow Claude Desktop to connect
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Accept');
  
  // Handle preflight OPTIONS request
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }
  
  // Health check endpoint for ALB
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'healthy' }));
    return;
  }
  
  // Handle MCP endpoint
  if (req.url === '/mcp' && req.method === 'POST') {
    // Check if client accepts SSE
    const acceptHeader = req.headers.accept || '';
    const useSSE = acceptHeader.includes('text/event-stream');
    
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
    });
    
    req.on('end', async () => {
      try {
        // Parse the request body
        const requestData = JSON.parse(body);
        
        // Create a transport for handling the request
        const transport = new StreamableHTTPServerTransport({
          enableJsonResponse: !useSSE
        });
        
        // Connect the transport to the server
        await server.connect(transport);
        
        // Let the transport handle all aspects of the response including headers
        await transport.handleRequest(req, res, requestData);
      } catch (error) {
        console.error('Error processing request:', error);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Internal server error' }));
      }
    });
  } else {
    // Not found
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
  }
});

// Start the server
httpServer.listen(PORT, () => {
  console.log(`Product MCP Server running on port ${PORT}`);
  console.log(`Health check endpoint: http://localhost:${PORT}/health`);
  console.log(`MCP endpoint: http://localhost:${PORT}/mcp`);
});
