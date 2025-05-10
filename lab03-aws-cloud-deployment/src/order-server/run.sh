#!/bin/bash

# Set up environment variables
export NODE_PATH=$LAMBDA_TASK_ROOT/node_modules:$NODE_PATH
export PATH=$PATH:$LAMBDA_TASK_ROOT/node_modules/.bin

# Log the environment for debugging
echo "Starting order server Lambda function"
echo "PORT=$PORT"
echo "AWS_LWA_PORT=$AWS_LWA_PORT"
echo "Current directory: $(pwd)"

# Execute the Node.js application with the Lambda Web Adapter
node index.js
