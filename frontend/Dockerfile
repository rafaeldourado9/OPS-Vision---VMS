# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Build args (Vite bakes these into the static bundle at build time)
ARG VITE_API_URL
ARG VITE_WS_URL
ARG VITE_GOOGLE_MAPS_API_KEY
ARG VITE_GOOGLE_MAPS_KEY

ENV VITE_API_URL=$VITE_API_URL \
    VITE_WS_URL=$VITE_WS_URL \
    VITE_GOOGLE_MAPS_KEY=${VITE_GOOGLE_MAPS_KEY:-$VITE_GOOGLE_MAPS_API_KEY}

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# ── Stage 2: Serve via Nginx ──────────────────────────────────────────────────
FROM nginx:alpine AS runner

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
