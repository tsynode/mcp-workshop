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
  mcpServer.tool("create-order", async (params = {}) => {
    // Add comprehensive debugging
    l.debug(`Received create-order request with params: ${JSON.stringify(params)}`);
    
    // Destructure with defaults to handle empty params
    const { productId, quantity } = params || {};
    
    if (!productId || !quantity) {
      l.debug('Missing required parameters: productId or quantity');
      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            error: "Missing required parameters",
            message: "productId and quantity are required"
          }, null, 2)
        }]
      };
    }
    
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
    
    l.debug(`Order created with ID: ${orderId}`);
    
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
  mcpServer.tool("check-order-status", async (params = {}) => {
    // Add comprehensive debugging
    l.debug(`Received check-order-status request with params: ${JSON.stringify(params)}`);
    
    // Destructure with defaults to handle empty params
    const { orderId } = params || {};
    
    l.debug(`Checking status for order ID: ${orderId || 'all'}`);
    
    if (orderId) {
      const order = orders.find(o => o.orderId === orderId);
      
      if (!order) {
        l.debug(`Order with ID ${orderId} not found`);
        return {
          content: [{
            type: "text",
            text: `Order with ID ${orderId} not found`
          }]
        };
      }
      
      l.debug(`Found order: ${JSON.stringify(order)}`);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(order, null, 2)
        }]
      };
    } else {
      // Return all orders if no orderId is provided
      l.debug(`Returning all orders: ${orders.length} found`);
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
