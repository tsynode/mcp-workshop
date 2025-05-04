import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createServer } from "http";
import { z } from "zod";

// Create MCP server instance
const server = new McpServer({
  name: "Retail Order Server (AWS)",
  version: "1.0.0",
  protocolVersion: "2025-03-26",  // Updated protocol version with streaming support
  onRequest: (request) => {
    // Log detailed information about each incoming request
    console.log('ORDER-SERVER DEBUG - Received request:', JSON.stringify({
      method: request.method,
      params: request.params,
      id: request.id,
      headers: request.transport?.req?.headers,
      url: request.transport?.req?.url
    }, null, 2));
    return request;
  }
});

// In-memory order storage (in a real application, this would be in a database)
const orders = [];

// Generate a unique order ID
function generateOrderId() {
  return `ord-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

// Define the create-order tool
server.tool(
  "create-order",
  "Create a new order for products",
  {
    productId: z.string(),
    quantity: z.number().min(1)
  },
  async ({ productId, quantity }) => {
    console.log(`Creating order for product ID: ${productId}, quantity: ${quantity}`);
    
    const orderId = generateOrderId();
    
    const order = {
      orderId,
      productId,
      quantity,
      status: "pending",
      createdAt: new Date().toISOString(),
      totalPrice: 0 // In real world, would fetch from product service
    };
    
    orders.push(order);
    
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          message: "Order created successfully",
          order
        }, null, 2)
      }]
    };
  }
);

// Define the check-order-status tool
server.tool(
  "check-order-status",
  "Check the status of an existing order",
  {
    orderId: z.string().optional()
  },
  async ({ orderId }) => {
    console.log(`Checking status for order ID: ${orderId || 'all'}`);
    
    if (orderId) {
      const order = orders.find(o => o.orderId === orderId);
      
      if (!order) {
        return {
          content: [{
            type: "text",
            text: `Order with ID ${orderId} not found`
          }]
        };
      }
      
      return {
        content: [{
          type: "text",
          text: JSON.stringify(order, null, 2)
        }]
      };
    } else {
      // Return all orders if no orderId is provided
      return {
        content: [{
          type: "text",
          text: JSON.stringify(orders, null, 2)
        }]
      };
    }
  }
);

// Create HTTP server
const PORT = process.env.PORT || 3001;

const httpServer = createServer(async (req, res) => {
  // Log raw HTTP request details
  console.log('ORDER-SERVER RAW HTTP REQUEST:', JSON.stringify({
    method: req.method,
    url: req.url,
    headers: req.headers,
    timestamp: new Date().toISOString()
  }, null, 2));

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
        // Log the raw request body
        console.log('ORDER-SERVER REQUEST BODY:', body);
        
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
  console.log(`Order MCP Server running on port ${PORT}`);
  console.log(`Health check endpoint: http://localhost:${PORT}/health`);
  console.log(`MCP endpoint: http://localhost:${PORT}/mcp`);
});
