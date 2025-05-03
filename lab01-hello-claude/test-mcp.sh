#!/bin/bash
# MCP Server Test Script
# This script tests a minimal MCP server using the MCP Inspector CLI
# Purpose: Demonstrates how to verify MCP server functionality through automated testing

# ANSI color codes for better readability
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
  echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_success() {
  echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
  echo -e "${RED}❌ $1${NC}"
}

print_info() {
  echo -e "${YELLOW}$1${NC}"
}

# We'll always test against a Docker container for consistency
# This ensures the same environment for all tests

# Check if we should run inspector tests
RUN_INSPECTOR=0
if [ "$1" == "--inspector" ] || [ "$1" == "-i" ]; then
  RUN_INSPECTOR=1
fi

# Start the test
print_header "MCP SERVER TEST"
echo -e "${BLUE}Testing MCP server at:${NC} $SERVER_PATH"

# Test 1: List tools
# This test verifies that the server properly exposes its available tools
print_header "TEST 1: List Tools"

# First check if our test container is running
if ! docker ps --filter "name=test-mcp" --format "{{.Names}}" | grep -q "test-mcp"; then
  print_info "Starting test container..."
  docker run -d --name test-mcp hello-claude-server sleep infinity
fi
print_info "Note: First run will download the MCP Inspector package using npx"
print_info "Running: docker exec test-mcp bash -c 'npx @modelcontextprotocol/inspector --cli --method tools/list node index.js'"
TOOLS_RESULT=$(docker exec test-mcp bash -c 'npx @modelcontextprotocol/inspector --cli --method tools/list node index.js')

echo -e "${MAGENTA}Result:${NC}"
echo "$TOOLS_RESULT" | jq . 2>/dev/null || echo "$TOOLS_RESULT"

if [[ $(echo "$TOOLS_RESULT" | jq '.tools | length') -gt 0 ]]; then
  print_success "Found tools in the MCP server"
else
  print_error "No tools found in the MCP server"
fi

# Test 2: List resource templates
# This test verifies that the server properly exposes its resource templates
# Resource templates allow AI models to access dynamic content through URI patterns
print_header "TEST 2: List Resource Templates"

print_info "Running: docker exec test-mcp bash -c 'npx @modelcontextprotocol/inspector --cli --method resources/templates/list node index.js'"
TEMPLATES_RESULT=$(docker exec test-mcp bash -c 'npx @modelcontextprotocol/inspector --cli --method resources/templates/list node index.js')

echo -e "${MAGENTA}Result:${NC}"
echo "$TEMPLATES_RESULT" | jq . 2>/dev/null || echo "$TEMPLATES_RESULT"

if [[ $(echo "$TEMPLATES_RESULT" | jq '.resourceTemplates | length') -gt 0 ]]; then
  print_success "Found resource templates in the MCP server"
else
  print_error "No resource templates found in the MCP server"
fi

# Test 3: Call the hello tool
# This test demonstrates invoking a tool with an optional parameter
# The hello tool accepts an optional 'name' parameter
print_header "TEST 3: Call Hello Tool"

print_info "Running direct JSON-RPC request to call the hello tool (via Docker)"
HELLO_RESULT=$(docker exec -i test-mcp bash -c "echo '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"tools/call\",\"params\":{\"name\":\"hello\",\"arguments\":{\"name\":\"Shell Script\"}}}' | node index.js" | grep -v "Hello World MCP server starting" | grep -v "Server connected to stdio transport")

echo -e "${MAGENTA}Result:${NC}"
echo "$HELLO_RESULT" | jq . 2>/dev/null || echo "$HELLO_RESULT"

if [[ $(echo "$HELLO_RESULT" | jq -r '.result.content[0].text') == *"Hello, Shell Script!"* ]]; then
  print_success "Hello tool responded correctly"
else
  print_error "Hello tool did not respond as expected"
fi

# Test 4: Call the echo tool
# This test demonstrates invoking a tool with a required parameter
# The echo tool requires a 'message' parameter
print_header "TEST 4: Call Echo Tool"

print_info "Running direct JSON-RPC request to call the echo tool (via Docker)"
ECHO_RESULT=$(docker exec -i test-mcp bash -c "echo '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"tools/call\",\"params\":{\"name\":\"echo\",\"arguments\":{\"message\":\"Testing the echo tool\"}}}' | node index.js" | grep -v "Hello World MCP server starting" | grep -v "Server connected to stdio transport")

echo -e "${MAGENTA}Result:${NC}"
echo "$ECHO_RESULT" | jq . 2>/dev/null || echo "$ECHO_RESULT"

if [[ $(echo "$ECHO_RESULT" | jq -r '.result.content[0].text') == *"You said: Testing the echo tool"* ]]; then
  print_success "Echo tool responded correctly"
else
  print_error "Echo tool did not respond as expected"
fi

# Test 5: Access a resource using the template
# This test demonstrates accessing a dynamic resource through its URI template
# The 'greeting://{name}' template extracts the name parameter from the URI
print_header "TEST 5: Access Resource Using Template"

print_info "Running direct JSON-RPC request to access a resource (via Docker)"
RESOURCE_RESULT=$(docker exec -i test-mcp bash -c "echo '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"resources/retrieve\",\"params\":{\"uri\":\"greeting://World\"}}' | node index.js" | grep -v "Hello World MCP server starting" | grep -v "Server connected to stdio transport")

# If that fails with method not found, try resources/resolve (older spec)
if [[ $(echo "$RESOURCE_RESULT" | grep -c "Method not found") -gt 0 ]]; then
  print_info "Method 'resources/retrieve' not found, trying 'resources/resolve'..."
  RESOURCE_RESULT=$(docker exec -i test-mcp bash -c "echo '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"resources/resolve\",\"params\":{\"uri\":\"greeting://World\"}}' | node index.js" | grep -v "Hello World MCP server starting" | grep -v "Server connected to stdio transport")
fi

echo -e "${MAGENTA}Result:${NC}"
echo "$RESOURCE_RESULT" | jq . 2>/dev/null || echo "$RESOURCE_RESULT"

if [[ $(echo "$RESOURCE_RESULT" | jq -r '.result.contents[0].text' 2>/dev/null) == *"Greetings, World!"* ]]; then
  print_success "Resource accessed correctly"
else
  print_error "Resource could not be accessed as expected"
  print_info "This might be normal if the resource method name is different"
fi

# Cleanup
print_header "CLEANUP"

print_info "Cleaning up Docker test container..."
docker rm -f test-mcp >/dev/null 2>&1 || true
print_success "Docker test container removed"

# If we're running inspector tests, do that and exit
if [ $RUN_INSPECTOR -eq 1 ]; then
  print_header "MCP INSPECTOR TESTS"
  
  # Create a test container if it doesn't exist
  if ! docker ps --filter "name=test-mcp" --format "{{.Names}}" | grep -q "test-mcp"; then
    print_info "Starting test container for inspector tests..."
    docker run -d --name test-mcp hello-claude-server sleep infinity
  fi
  
  print_header "TESTING WITH INSPECTOR CLI"
  print_info "Running MCP Inspector CLI in Docker container..."
  print_info "Note: First run will download the MCP Inspector package using npx"
  
  print_info "\n--- Testing tools/list ---"
  docker exec test-mcp npx @modelcontextprotocol/inspector --cli --method tools/list node index.js
  
  print_info "\n--- Testing resources/templates/list ---"
  docker exec test-mcp npx @modelcontextprotocol/inspector --cli --method resources/templates/list node index.js
  
  print_info "\n--- Testing tools/call (hello) ---"
  docker exec -i test-mcp bash -c "echo '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"tools/call\",\"params\":{\"name\":\"hello\",\"arguments\":{\"name\":\"World\"}}}' | node index.js"
  
  print_info "\n--- Testing tools/call (echo) ---"
  docker exec -i test-mcp bash -c "echo '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"tools/call\",\"params\":{\"name\":\"echo\",\"arguments\":{\"message\":\"Hello from Inspector CLI\"}}}' | node index.js"
  
  print_info "Cleaning up test container..."
  docker rm -f test-mcp >/dev/null 2>&1 || true
  
  exit 0
fi

# Summary
print_header "TEST SUMMARY"
echo -e "${BLUE}The MCP server has been tested for:${NC}"
echo -e "1. Tool discovery (tools/list)"
echo -e "2. Resource template discovery (resources/templates/list)"
echo -e "3. Tool invocation - hello tool (tools/call)"
echo -e "4. Tool invocation - echo tool (tools/call)"
echo -e "5. Resource access (resources/get)"

print_header "TEST COMPLETE"
echo -e "${GREEN}To run the MCP server interactively, use:${NC}"
echo -e "docker run -i --rm hello-claude-server"
