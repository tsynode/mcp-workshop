#!/bin/bash

# Set up environment variables
export NODE_PATH=$LAMBDA_TASK_ROOT/node_modules:$NODE_PATH
export PATH=$PATH:$LAMBDA_TASK_ROOT/node_modules/.bin

# Log the environment for debugging
echo "Starting product server Lambda function"
echo "PORT=$PORT"
echo "AWS_LWA_PORT=$AWS_LWA_PORT"
echo "Current directory: $(pwd)"

# Execute the Node.js application in the background
node index.js &

# Store the PID of the Node.js process
NODE_PID=$!

# Keep the script running to allow the Lambda Web Adapter to proxy requests
while true; do
  # Check if the Node.js process is still running
  if ! kill -0 $NODE_PID 2>/dev/null; then
    echo "Node.js process exited unexpectedly"
    exit 1
  fi
  
  # Sleep to reduce CPU usage
  sleep 1
done
