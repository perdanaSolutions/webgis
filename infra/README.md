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
| `k8s/09-pgbouncer.yaml` | PgBouncer transaction pooling (2 replica) + NetworkPolicy |
| `k8s/10-pdb.yaml` | PodDisruptionBudget minAvailable 1 (API, FE, HAProxy, PgBouncer) |
| `k8s/11-networkpolicy.yaml` | Ingress policy API/FE/worker (egress bebas) |
| `k8s/kustomization.yaml` | Satu titik parameter: image registry/tag, host Ingress, TLS (`kubectl apply -k infra/k8s`) |

## Hardening scaling (Nov 2026)

**Redis dua instance**
- `redis` (StatefulSet + PVC 2Gi): sesi auth `gis:auth:*` via `REDIS_URL`. AOF `everysec`, `noeviction` → restart tidak me-logout user, memori penuh tidak membuang sesi.
- `redis-cache` (tanpa persistence): cache `gis:map:*` + ubin Foto Udara via `REDIS_CACHE_URL`, `maxmemory 768mb` + `allkeys-lru`.
- `REDIS_CACHE_URL` kosong → semua di `REDIS_URL` (perilaku lama). Cache mati → API lanjut tanpa cache; auth tidak terpengaruh.
- HA: belum (1 node). Opsi: Redis Sentinel (chart bitnami) atau Redis managed — cukup ganti URL di Secret.

**Koneksi database**
- Hitungan: tiap proses = `DB_POOL_SIZE + DB_MAX_OVERFLOW` (5+10). 10 pod API × 15 + 2 worker × 5 = 160 > `max_connections` 100.
- Solusi: semua API/worker ke `pgbouncer:6432` (transaction mode). Koneksi ke Postgres = pod PgBouncer × (`DEFAULT_POOL_SIZE` 30 + reserve 5) = 70.
- psycopg2 (sync) aman di transaction mode (tanpa prepared statement server). Audit `set_config(...,true)` dan DDL startup (`pg_advisory_xact_lock`) per transaksi. **Jangan** tambah `SET` level sesi / `LISTEN` / advisory lock sesi.
- Dulu ada 2 engine SQLAlchemy per proses (`app/core/database.py` hardcode 5+10 + `app/db/session.py`) → kini satu engine.

**Probe**: API `/health` (startup/readiness/liveness), FE `/favicon.ico` (statis, tanpa SSR), HAProxy `monitor-uri /healthz` di port 8404, worker exec cek mtime `UPLOAD_WORKER_ALIVE_FILE`, Redis `redis-cli ping`.

**Multi-replica aman**: upload disimpan di DB (`audit.upload_jobs.content`), bukan disk pod; worker klaim job `FOR UPDATE SKIP LOCKED`; housekeeping worker idempoten; DDL startup dikunci advisory lock. Cache status maintenance per proses 10 dtk (replica lain menyusul ≤10 dtk).

**Env baru**: `REDIS_CACHE_URL`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE_SECONDS`, `DB_STARTUP_DDL`, `UPLOAD_WORKER_ALIVE_FILE`, `PGB_DB_HOST/PORT/USER/PASSWORD/NAME`, `PGB_DEFAULT_POOL_SIZE`, `PGB_AUTH_TYPE` (Compose). Lihat `env.scale.example`.

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
- Redis HA (SPOF sesi): Sentinel / managed [PERLU KONFIRMASI] — persistence + noeviction sudah aktif
- PgBouncer: `AUTH_TYPE` sama dengan `password_encryption` Postgres; pin tag image [PERLU KONFIRMASI]
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
