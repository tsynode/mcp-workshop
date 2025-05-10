import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import log4js from "log4js";

const l = log4js.getLogger();

// In-memory order storage (in a real application, this would be in a database)
const orders = [];

// Generate a unique order ID
function generateOrderId() {
  return `ord-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

const create = () => {
  // Create a new MCP server instance for each request
  const mcpServer = new McpServer({
    name: "Retail Order Server (AWS)",
    version: "1.0.0"
  }, {
    capabilities: {
      tools: {}
    }
  });

  // Define the create-order tool
  mcpServer.tool("create-order", async ({ productId, quantity }) => {
    l.debug(`Creating order for product ID: ${productId}, quantity: ${quantity}`);
    
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
  });

  // Define the check-order-status tool
  mcpServer.tool("check-order-status", async ({ orderId }) => {
    l.debug(`Checking status for order ID: ${orderId || 'all'}`);
    
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
  });

  return mcpServer;
};

export default { create };
