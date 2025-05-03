FROM node:18-slim

# Create app directory

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Run the server
CMD ["node", "index.js"]
