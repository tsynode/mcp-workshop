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
        
        // Create new instances of MCP Server and Transport for each incoming request
        const server = mcpServer.create();
        l.debug(`Created MCP server for product-server`);
        
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
        
        // Log the method being called if available
        if (req.body && req.body.method) {
            l.debug(`Processing method: ${req.body.method}`);
        }
        
        // Handle the request
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
