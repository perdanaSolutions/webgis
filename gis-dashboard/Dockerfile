# ---- tahap build ----
  FROM node:24.22.1-alpine AS build
  WORKDIR /app
  COPY package*.json ./
  # postinstall (sync-vendor-security-deps) butuh scripts/ dan vendor/ saat npm ci
  COPY scripts ./scripts
  COPY vendor ./vendor
  RUN npm ci --legacy-peer-deps
  COPY . .
  RUN npm run build

  # ---- tahap runtime (kecil, tanpa source & node_modules dev) ----
  FROM node:24.22.1-alpine
  WORKDIR /app
  ENV NODE_ENV=production \
      HOST=0.0.0.0 \
      PORT=3000
  COPY --from=build /app/.output ./.output
  EXPOSE 3000
  CMD ["node", ".output/server/index.mjs"]
