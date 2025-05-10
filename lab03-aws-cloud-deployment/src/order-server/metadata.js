import { readFileSync } from "fs";
import { join } from "path";

const version = "1.0.0";
let logStreamName = "local";

// Initialize metadata with environment information
const init = async () => {
    try {
        // When running in AWS Lambda, we can get the log stream name from the environment
        if (process.env.AWS_LAMBDA_LOG_STREAM_NAME) {
            logStreamName = process.env.AWS_LAMBDA_LOG_STREAM_NAME;
        }
    } catch (error) {
        console.error("Error initializing metadata:", error);
    }
};

// Export all metadata properties
const all = {
    version,
    logStreamName,
    environment: process.env.NODE_ENV || "development"
};

export default {
    init,
    all,
    version,
    logStreamName
};
