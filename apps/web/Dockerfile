# PersonaAI web image (Next.js standalone output).
FROM node:22-slim AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-slim AS builder
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# API calls are proxied at runtime to API_PROXY_TARGET (see next.config.ts).
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.ts ./next.config.ts
EXPOSE 3000
CMD ["pnpm", "start"]
