#!/bin/bash

# Set up environment variables
export NODE_PATH=$LAMBDA_TASK_ROOT/node_modules:$NODE_PATH
export PATH=$PATH:$LAMBDA_TASK_ROOT/node_modules/.bin

# Log the environment for debugging
echo "Starting product server Lambda function"
echo "NODE_PATH=$NODE_PATH"
echo "Current directory: $(pwd)"
echo "Directory contents: $(ls -la)"

# Execute the Node.js application with the Lambda Web Adapter
exec node index.js
