# Build the React app, then bake it into a Caddy image that also
# reverse-proxies /api/* to the backend service.

FROM node:22-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY --from=builder /app/dist /srv
# Default to dev Caddyfile; production compose overlay can mount the prod one.
COPY Caddyfile.dev /etc/caddy/Caddyfile
EXPOSE 80 443
