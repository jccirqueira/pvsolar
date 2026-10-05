# ============ build ============
FROM node:20-alpine AS builder
WORKDIR /app

# URLs dos servicos consumidas pelo browser (inlinadas em tempo de build).
# Padrao = caminhos relativos do Caddy -> mesma origem, sem CORS.
ARG NEXT_PUBLIC_GATEWAY_URL=/gateway
ARG NEXT_PUBLIC_ANALYTICS_URL=/analytics
ARG NEXT_PUBLIC_SCADA_URL=/scada
ARG NEXT_PUBLIC_REPORTS_URL=/reports
ARG NEXT_PUBLIC_FLEET_URL=/fleet
ARG NEXT_PUBLIC_ALERT_URL=/alert
ARG NEXT_PUBLIC_GRID_URL=/grid
ARG NEXT_PUBLIC_TWIN_URL=/twin
ARG NEXT_PUBLIC_AUTH_URL=/auth
ENV NEXT_PUBLIC_GATEWAY_URL=$NEXT_PUBLIC_GATEWAY_URL \
    NEXT_PUBLIC_ANALYTICS_URL=$NEXT_PUBLIC_ANALYTICS_URL \
    NEXT_PUBLIC_SCADA_URL=$NEXT_PUBLIC_SCADA_URL \
    NEXT_PUBLIC_REPORTS_URL=$NEXT_PUBLIC_REPORTS_URL \
    NEXT_PUBLIC_FLEET_URL=$NEXT_PUBLIC_FLEET_URL \
    NEXT_PUBLIC_ALERT_URL=$NEXT_PUBLIC_ALERT_URL \
    NEXT_PUBLIC_GRID_URL=$NEXT_PUBLIC_GRID_URL \
    NEXT_PUBLIC_TWIN_URL=$NEXT_PUBLIC_TWIN_URL \
    NEXT_PUBLIC_AUTH_URL=$NEXT_PUBLIC_AUTH_URL

COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ============ runner ============
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3001
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3001', r => process.exit(0)).on('error', () => process.exit(1))"

CMD ["node", "server.js"]
