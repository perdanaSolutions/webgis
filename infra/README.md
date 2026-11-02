# Infrastruktur WEBGIS — HAProxy + Horizontal Scale + HPA

| | |
|---|---|
| Branch | `bayu-v2` |
| LB utama | **HAProxy** (sticky OFF) |
| Auth scale | JWT + Redis `jti` (ADR-001) |
| Panduan VPS | [`RUNBOOK-VPS.md`](./RUNBOOK-VPS.md) |

## Tiga poin implementasi

| # | Poin | Artefak |
|---|------|---------|
| 1 | Horizontal scaling | Compose `--scale` + K8s Deployment multi-replica; env identik (`SECRET_KEY`, `REDIS_*`) |
| 2 | Load balancer HAProxy | `haproxy/haproxy.cfg` + service `haproxy` di compose / `k8s/08-haproxy.yaml` |
| 3 | Orkestrasi & auto-scaling | `k8s/*.yaml` + HPA CPU/memory **≥ 70%** (`07-hpa.yaml`) |

## Diagram

```text
Internet / VPS :8080 (atau :80 TLS [PERLU KONFIRMASI])
        │
        ▼
   [ HAProxy ]
   roundrobin · sticky OFF · hc GET /health
        │
        ├── /health,/api → backend_fastapi × N (:8000)
        └── /            → gis-dashboard × M (:3000)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
           Redis          Postgres      upload_worker
        (shared)         (shared)     (bukan pool LB)
```

## Artefak

| Path | Fungsi |
|------|--------|
| `haproxy/haproxy.cfg` | Round-robin, no stick-table, `option httpchk GET /health`, Docker DNS `server-template` |
| `docker-compose.scale.yaml` | Redis + API×N + FE×M + worker + HAProxy |
| `env.scale.example` | Checklist variabel (tanpa rahasia) |
| `RUNBOOK-VPS.md` | Install → env → up → scale → verifikasi |
| `k8s/01`–`05` | Namespace, Redis, API, worker, FE |
| `k8s/06-ingress.yaml` | Alternatif cloud Ingress (**tanpa** affinity) |
| `k8s/07-hpa.yaml` | HPA target utilization **70%** |
| `k8s/08-haproxy.yaml` | HAProxy di cluster |
| `nginx/nginx.conf.example` | Referensi lama — **bukan** LB utama |

## Quick start Compose

```bash
# Siapkan .env lokal di VPS (lihat env.scale.example) — jangan commit
export REDIS_PASSWORD='<kuat>'   # wajib — auth jti
docker compose -f infra/docker-compose.scale.yaml up -d --build \
  --scale backend_fastapi=3 --scale gis-dashboard=2
curl -sS http://127.0.0.1:8080/health
```

## Wajib sebelum production

- TLS di HAProxy / reverse edge [PERLU KONFIRMASI] — **blocker** go-live publik
- `CORS_ORIGINS` allowlist + `NUXT_PUBLIC_AUTH_COOKIE_SECURE=true`
- `REDIS_PASSWORD` + NetworkPolicy; jangan publish 6379
- `TRUSTED_PROXY_CIDRS` + HAProxy strip XFF (sudah di `haproxy.cfg`)
- `minReplicas` / `maxReplicas` HPA
- Redis HA (SPOF sesi) via secret manager [PERLU KONFIRMASI]
- Postgres backup/restore RPO/RTO
- Monitoring: `/health`, stats localhost/`haproxy-stats`, alert CPU ≥70%, 5xx
- `MTLS_*` di belakang LB: biasanya off untuk HTTP internal [PERLU KONFIRMASI]
- Review: `backend_fastapi/docs/sec-review-002-haproxy-redis-jti.md`

## Smoke

```bash
LB_BASE=http://127.0.0.1:8080 ./infra/scripts/smoke-lb.sh
# butuh akun uji di shell (bukan dari file .env di skrip):
export SMOKE_EMAIL='…' SMOKE_PASSWORD='…'
LB_BASE=http://127.0.0.1:8080 ./infra/scripts/smoke-auth-scale.sh
```

| Cek | Hasil diharapkan |
|-----|------------------|
| `GET /health` | `status=ok`, `redis_auth=enabled`, `instance` berganti antar hit |
| Login → `/me`×N | 200 lewat LB (tanpa sticky) |
| Logout → `/me`×N | **401** di semua hit |
| Matriks QA | [`QA-SCALE-CHECKLIST.md`](./QA-SCALE-CHECKLIST.md) |
