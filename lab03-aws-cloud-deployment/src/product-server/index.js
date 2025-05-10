import './logging.js';
import log4js from 'log4js';
import express from 'express';
import metadata from './metadata.js';
import transport from './transport.js';

await metadata.init();

const l = log4js.getLogger();
const PORT = process.env.PORT || 3000;

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
    l.debug(`Product MCP Server running on port ${PORT}`);
    l.debug(`Health check endpoint: http://localhost:${PORT}/health`);
    l.debug(`MCP endpoint: http://localhost:${PORT}/mcp`);
  });
}

// For Lambda, export the handler function
export const handler = async (event, context) => {
  // Log the incoming event and context to help with debugging
  console.log('Lambda function invoked with event:', JSON.stringify(event, null, 2));
  console.log('Lambda function context:', JSON.stringify({
    functionName: context.functionName,
    functionVersion: context.functionVersion,
    awsRequestId: context.awsRequestId,
    logGroupName: context.logGroupName,
    logStreamName: context.logStreamName,
  }, null, 2));
  
  try {
    // The AWS Lambda Web Adapter will handle the event and route the request to the Express app
    // This logging will help us understand if the handler is being called correctly
    l.info(`Lambda handler invoked for ${event.path || 'unknown path'}`);
    
    // Return a response that will be overridden by the Lambda Web Adapter
    return { statusCode: 200, body: 'Lambda Web Adapter will handle the request' };
  } catch (error) {
    // Log any errors that occur
    console.error('Error in Lambda handler:', error);
    l.error(`Lambda handler error: ${error.message}`);
    return { 
      statusCode: 500, 
      body: JSON.stringify({ error: 'Internal Server Error', message: error.message }) 
    };
  }
};

// Also export the app for local development
export default app;
