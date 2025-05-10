import './logging.js';
import log4js from 'log4js';
import express from 'express';
import metadata from './metadata.js';
import transport from './transport.js';

await metadata.init();

const l = log4js.getLogger();
const PORT = process.env.PORT || 3001;

// This function is using Lambda Web Adapter to run express.js on Lambda
// https://github.com/awslabs/aws-lambda-web-adapter
const app = express();
app.use(express.json());

// Add CORS headers for all routes
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Accept, Authorization');
  
  if (req.method === 'OPTIONS') {
    res.sendStatus(204);
    return;
  }
  
  next();
});

// Health check endpoint for ALB
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

// Debug logging middleware
app.use(async (req, res, next) => {
  l.debug(`> ${req.method} ${req.originalUrl}`);
  l.debug(req.body);
  return next();
});

// Bootstrap the MCP transport
await transport.bootstrap(app);

// Start the server when not running in Lambda
if (!process.env.AWS_LAMBDA_FUNCTION_NAME) {
  app.listen(PORT, () => {
    l.debug(metadata.all);
    l.debug(`Order MCP Server running on port ${PORT}`);
    l.debug(`Health check endpoint: http://localhost:${PORT}/health`);
    l.debug(`MCP endpoint: http://localhost:${PORT}/mcp`);
  });
}

// For Lambda, export the app
export default app;
