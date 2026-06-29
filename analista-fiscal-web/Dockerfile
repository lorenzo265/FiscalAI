# syntax=docker/dockerfile:1.7
# Marco 4 PR4 (#15) -- Dockerfile de producao do frontend Next 15 (standalone).
#
# Multi-stage: deps (npm ci) -> builder (next build, standalone) -> runner
# (so o output minimo + node). Espelha as convencoes do Dockerfile.api:
# imagem slim, user nao-root uid 1000, EXPOSE + CMD explicito.
#
# NEXT_PUBLIC_API_BASE_URL e inlinado no bundle em BUILD-TIME (variavel
# NEXT_PUBLIC_*), por isso entra como build-arg -- nao adianta setar em runtime.

ARG NODE_VERSION=20-bookworm-slim

# ---------- deps: instala dependencias com lockfile ----------
FROM node:${NODE_VERSION} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---------- builder: next build (gera .next/standalone) ----------
FROM node:${NODE_VERSION} AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# URL do backend, inlinada no bundle em build-time. Default = mesmo fallback
# do src/lib/http.ts; o deploy do PO sobrescreve com --build-arg.
ARG NEXT_PUBLIC_API_BASE_URL="http://localhost:8000/v1"
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build

# ---------- runner: imagem final minima ----------
FROM node:${NODE_VERSION} AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Usuario nao-root (mesma convencao do Dockerfile.api: uid 1000).
RUN groupadd --system --gid 1000 nodejs \
    && useradd --system --uid 1000 --gid nodejs nextjs

# O output standalone ja traz o server.js + node_modules minimos; static e
# public sao copiados a parte (o tracing nao os inclui).
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

# Healthcheck simples: a home responde 200 quando o server esta de pe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
