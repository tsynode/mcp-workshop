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
