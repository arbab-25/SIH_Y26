## Multi-stage Dockerfile for React + Vite production build
# ---------- Builder Stage ----------
FROM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Install dependencies (only package.json and lock file for caching)
COPY package.json ./
RUN npm install

# Copy source code
COPY . .

# Build the production assets
RUN npm run build

# ---------- Production Stage ----------
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose default HTTP port
EXPOSE 80

# Use the default nginx entrypoint (no additional command needed)
