import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import log4js from "log4js";

const l = log4js.getLogger();

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

const create = () => {
  // Create a new MCP server instance for each request
  const mcpServer = new McpServer({
    name: "Retail Product Server (AWS)",
    version: "1.0.0"
  }, {
    capabilities: {
      tools: {}
    }
  });

  // Define the get-product tool
  mcpServer.tool("get-product", async ({ productId }) => {
    l.debug(`Getting product with ID: ${productId}`);
    
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
  });

  // Define the search-products tool
  mcpServer.tool("search-products", async ({ category, maxPrice, inStockOnly }) => {
    l.debug(`Searching products with filters: category=${category}, maxPrice=${maxPrice}, inStockOnly=${inStockOnly}`);
    
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
  });

  return mcpServer;
};

export default { create };
