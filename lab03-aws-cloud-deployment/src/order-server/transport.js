import log4js from "log4js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import mcpServer from "./mcp-server.js";
import mcpErrors from "./mcp-errors.js";

const MCP_PATH = "/order-mcp";  // CHANGED FROM "/mcp" to "/order-mcp"

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
        
        // Create new instances of MCP Server and Transport for each incoming request
        const server = mcpServer.create();
        l.debug(`Created MCP server for order-server`);
        
        // Create a transport for this request
        const transport = new StreamableHTTPServerTransport({
            sessionIdGenerator: undefined,  // Stateless server
            enableJsonResponse: true        // Use JSON format for responses
        });
        
        // Set up cleanup when the request is complete
        res.on("close", () => {
            l.debug("Request processing complete");
            transport.close();
            server.close();
        });
        
        // Connect the server to the transport
        await server.connect(transport);
        
        // Check if we need to transform the request to MCP format
        let requestBody = req.body;
        
        // If the method is a direct tool name (not tools/call), transform it to proper MCP format
        if (req.body && req.body.method && req.body.method !== 'tools/call' && req.body.method !== 'tools/list') {
            const toolName = req.body.method;
            l.debug(`Transforming direct method call '${toolName}' to MCP format`);
            
            requestBody = {
                jsonrpc: req.body.jsonrpc || '2.0',
                id: req.body.id,
                method: 'tools/call',
                params: {
                    name: toolName,
                    arguments: req.body.params || {}
                }
            };
            
            l.debug(`Transformed request: ${JSON.stringify(requestBody)}`);
        } else {
            l.debug(`Processing standard method: ${req.body.method}`);
        }
        
        // Handle the request with potentially transformed body
        await transport.handleRequest(req, res, requestBody);
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
