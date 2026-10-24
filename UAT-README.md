# WebGIS UAT

Stack UAT terpisah dari production (`../webgis`). Compose project `webgis-uat`, file `docker-compose.uat.yaml`.

| Service | Container | Internal (127.0.0.1) | Publik (via Caddy) |
|---|---|---|---|
| Dashboard Nuxt | gis-dashboard-uat | 3002 | http://144.91.90.112:8082 |
| Backend FastAPI | gis-backend-uat | 8002 | http://144.91.90.112:8084 (/api/v1) |
| Upload worker | gis-upload-worker-uat | - | - |

- DB: `db_uat_v1` di container gis-postgres (user superadmin_gis). Redis: DB index 1 (prod index 0).
- mTLS dimatikan di UAT (port 8443 dipakai production).
- Caddy global: `/var/aplikasi/caddy/Caddyfile` blok `:8082` dan `:8084`.

## Perintah (dari folder ini)
    docker compose -f docker-compose.uat.yaml ps
    docker compose -f docker-compose.uat.yaml logs -f --tail 100
    docker compose -f docker-compose.uat.yaml stop        # hentikan
    docker compose -f docker-compose.uat.yaml up -d       # jalankan
    # rebuild (satu per satu, RAM tanpa swap):
    docker compose -f docker-compose.uat.yaml build backend_fastapi
    docker compose -f docker-compose.uat.yaml build gis-dashboard
    docker compose -f docker-compose.uat.yaml up -d
    # migrasi DB UAT
    docker compose -f docker-compose.uat.yaml run --rm --no-deps -T backend_fastapi python -m scripts.apply_migrations

JANGAN pakai `docker-compose.yaml` (tanpa .uat) di folder ini: nama container-nya sama dengan production.

## Rollback / hapus UAT
    docker compose -f docker-compose.uat.yaml down
    # .env asli: backend_fastapi/.env.bak-<ts>, gis-dashboard/.env.bak-<ts>
    # Caddy: kembalikan /var/aplikasi/caddy/Caddyfile.bak-<ts>, lalu
    docker exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
    ufw delete allow 8082/tcp; ufw delete allow 8084/tcp
