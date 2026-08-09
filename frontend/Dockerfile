FROM node:22-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm config set fetch-retries 8 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm ci --prefer-offline
COPY . .
ARG BACKEND_INTERNAL_URL=http://backend:8000
ARG CACHE_BUST=0
ENV BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL
ENV NEXT_TELEMETRY_DISABLED=1
# Alpine may fall back to the SWC WASM binding when the native optional
# package is unavailable. Turbopack requires native SWC, while Webpack works
# with the WASM fallback and produces the same standalone runtime artifact.
RUN echo "cache_bust=$CACHE_BUST" && npm run build -- --webpack

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
