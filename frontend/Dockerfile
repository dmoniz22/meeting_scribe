FROM node:20-alpine

WORKDIR /app

# Install dependencies first (better caching)
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Create next.js cache directories
RUN mkdir -p .next/cache

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev"]
