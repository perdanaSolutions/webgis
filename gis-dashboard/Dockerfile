# ---- tahap build ----
  FROM node:22-alpine AS build
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci --legacy-peer-deps
  COPY . .
  RUN npm run build

  # ---- tahap runtime (kecil, tanpa source & node_modules dev) ----
  FROM node:22-alpine
  WORKDIR /app
  ENV NODE_ENV=production \
      HOST=0.0.0.0 \
      PORT=3000
  COPY --from=build /app/.output ./.output
  EXPOSE 3000
  CMD ["node", ".output/server/index.mjs"]
