import log4js from "log4js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import mcpServer from "./mcp-server.js";
import mcpErrors from "./mcp-errors.js";

const MCP_PATH = "/mcp";

const l = log4js.getLogger();

const bootstrap = async (app) => {
    app.post(MCP_PATH, postRequestHandler);
    app.get(MCP_PATH, sessionRequestHandler);
    app.delete(MCP_PATH, sessionRequestHandler);
}

const postRequestHandler = async (req, res) => {
    try {
        // Log detailed request information
        l.debug(`Received MCP request at ${MCP_PATH}`);
        l.debug(`Request headers: ${JSON.stringify(req.headers)}`);
        l.debug(`Request body: ${JSON.stringify(req.body)}`);
        
        // Check if this is a direct method call (not using tools/call format)
        if (req.body && req.body.method && req.body.method !== 'tools/call' && 
            req.body.method !== 'resources/list' && req.body.method !== 'resources/retrieve') {
            
            l.debug(`Detected direct method call: ${req.body.method}`);
            
            // Transform the request to use the tools/call format
            const toolName = req.body.method;
            const toolParams = req.body.params || {};
            const requestId = req.body.id;
            
            // Create a properly formatted MCP request
            const mcpRequest = {
                jsonrpc: '2.0',
                id: requestId,
                method: 'tools/call',
                params: {
                    name: toolName,
                    arguments: toolParams
                }
            };
            
            l.debug(`Transformed request to: ${JSON.stringify(mcpRequest)}`);
            
            // Replace the original request body with the transformed one
            req.body = mcpRequest;
        }
        
        // Create new instances of MCP Server and Transport for each incoming request
        const newMcpServer = mcpServer.create();
        
        // Add onRequest handler to log the parsed request
        newMcpServer.onRequest((request) => {
            l.debug(`MCP Server received parsed request: ${JSON.stringify(request)}`);
        });
        
        const transport = new StreamableHTTPServerTransport({
            // This is a stateless MCP server, so we don't need to keep track of sessions
            sessionIdGenerator: undefined,

            // Using JSON format for responses to match the reference implementation
            enableJsonResponse: true,
            
            // Add debug logging for transport
            debug: true
        });

        res.on("close", () => {
            l.debug("Request processing complete");
            transport.close();
            newMcpServer.close();
        });
        
        await newMcpServer.connect(transport);
        
        // Log the available tools before handling the request
        l.debug(`Available tools: ${JSON.stringify(Object.keys(newMcpServer.getTools()))}`);
        
        await transport.handleRequest(req, res, req.body);
    } catch (err) {
        l.error(`Error handling MCP request: ${err}`);
        l.error(`Error stack: ${err.stack}`);
        if (!res.headersSent) {
            res.status(500).json(mcpErrors.internalServerError);
        }
    }
}

const sessionRequestHandler = async (req, res) => {
    res.status(405).set("Allow", "POST").json(mcpErrors.methodNotAllowed);
}

export default {
    bootstrap
}
