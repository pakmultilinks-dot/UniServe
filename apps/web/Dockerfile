# UniServe — Web (Next.js) Static Export
# Builds static files. In production, Caddy serves them via bind mount.
# This Dockerfile is kept for CI/CD and optional container-based builds.

# ---- Build ----
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json ./
COPY package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN if [ -f pnpm-lock.yaml ]; then npm install -g pnpm && pnpm install --frozen-lockfile; \
    elif [ -f yarn.lock ]; then yarn install --frozen-lockfile; \
    else npm ci; fi

# Copy source
COPY . .

# Build-time API URL — replaced at build time
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build static export
RUN npm run build

# Output is in /app/out — use 'docker cp' to extract, or mount as volume.
