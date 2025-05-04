# Use the same Node.js version as Lab 01 and Lab 02
FROM node:18-slim

# Create app directory
WORKDIR /usr/src/app

# Install app dependencies
# A wildcard is used to ensure both package.json AND package-lock.json are copied
COPY package*.json ./

# Install dependencies
RUN npm install

# Bundle app source
COPY . .

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && apt-get clean

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD [ "node", "index.js" ]
