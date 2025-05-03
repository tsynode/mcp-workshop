// Import the core MCP server components from the SDK
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
// Import the stdio transport for terminal-based communication
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
// Import zod for schema validation of tool parameters
import { z } from "zod";

// Create an MCP server with configuration parameters
const server = new McpServer({
  name: "Retail Order Server",
  version: "1.0.0",
  protocolVersion: "2024-03-01"  // MCP protocol version being implemented
});

// Simulated order storage
const orders = [];

// Generate order ID
function generateOrderId() {
  return `ord-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
}

// Create order
server.tool(
  "create-order",
  "Create a new order for products",
  {
    productId: z.string(),
    quantity: z.number().min(1)
  },
  async ({ productId, quantity }) => {
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

// Check order status
server.tool(
  "check-order-status",
  "Check the status of an existing order",
  { orderId: z.string() },
  async ({ orderId }) => {
    const order = orders.find(o => o.orderId === orderId);
    
    if (!order) {
      return {
        content: [{
          type: "text",
          text: `Order ${orderId} not found`
        }]
      };
    }
    
    // Simulate order processing
    if (order.status === "pending" && 
        Date.now() - new Date(order.createdAt).getTime() > 30000) {
      order.status = "processing";
    }
    
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          orderId: order.orderId,
          status: order.status,
          lastUpdated: new Date().toISOString()
        }, null, 2)
      }]
    };
  }
);

console.error('Retail Order Server starting...');

const transport = new StdioServerTransport();
await server.connect(transport);

console.error('Server connected to stdio transport. Waiting for requests...');
