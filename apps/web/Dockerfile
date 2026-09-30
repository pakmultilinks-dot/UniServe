# UniServe — Web (Next.js) Static Export
# Multi-stage: build static files, then serve with Caddy

# ---- Stage 1: Build ----
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

# ---- Stage 2: Serve with Caddy ----
FROM caddy:2-alpine

# Copy Caddyfile
COPY Caddyfile /etc/caddy/Caddyfile

# Copy built static files
COPY --from=builder /app/out /srv

EXPOSE 80 443
