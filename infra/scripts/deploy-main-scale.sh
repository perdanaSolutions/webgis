#!/bin/bash
# Auto-deploy prod main ke STACK SCALE (infra/docker-compose.scale.yaml, project webgis-scale). Staging untouched.
# Pasang: cp infra/scripts/deploy-main-scale.sh /var/aplikasi/project-webgis/deploy-main.sh (deploy-listener tetap sama).
# Beda dengan versi compose lama:
#   - COMPOSE = docker compose -p webgis-scale -f infra/docker-compose.scale.yaml --env-file /etc/webgis/scale.env
#   - hanya backend_fastapi, upload_worker, gis-dashboard yang di-recreate (redis/redis-cache/pgbouncer TIDAK,
#     agar sesi & pool tetap). haproxy di-recreate hanya bila infra/haproxy/haproxy.cfg berubah, selain itu reload HUP.
#     Service infra di-recreate hanya bila docker-compose.scale.yaml berubah (compose up tanpa --force-recreate → hanya yang berubah).
#   - health lewat HAProxy 127.0.0.1:8080 + stats 8404.
#   - migrasi: container sementara image baru, DB_HOST=pgbouncer (stack infra harus sudah jalan).
set -u
set -o pipefail  # agar kegagalan git pull/build/up terdeteksi walau output di-pipe ke while/log
REPO=/home/ginanjar/aplikasi/webgis
LOG=/var/log/webgis-deploy-main.log
LOCK=/tmp/webgis-deploy-main.lock
SCALE_ENV=/etc/webgis/scale.env
COMPOSE_FILE_REL=infra/docker-compose.scale.yaml
COMPOSE="docker compose -p webgis-scale -f $COMPOSE_FILE_REL --env-file $SCALE_ENV"
APP_SVCS="backend_fastapi upload_worker gis-dashboard"
INFRA_SVCS="redis redis-cache pgbouncer"
LB="http://127.0.0.1:8080"
BE_HEALTH="$LB/health"
FE_URL="$LB/"
PENGUMUMAN="$LB/api/v1/pengumuman/"
HAPROXY_STATS="http://127.0.0.1:8404/stats;csv"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[$(date '+%F %T')] deploy already running, exit" >>"$LOG"
  exit 0
fi

RUN_TS=$(date '+%F %T')
echo "[$RUN_TS] === deploy start ===" | tee -a "$LOG"
# Notifikasi Telegram saat script selesai (setting: /etc/webgis-deploy/telegram.env).
# Exit karena lock/busy terjadi sebelum trap ini, jadi tidak dinotifikasi. Tidak pernah menggagalkan deploy.
NOTIFY=/usr/local/sbin/webgis-deploy-notify
trap 'rc=$?; [ -x "$NOTIFY" ] && timeout 60 "$NOTIFY" "$rc" "$RUN_TS" >/dev/null 2>&1; exit $rc' EXIT
cd "$REPO" || { log "FAIL cd repo"; exit 1; }
[ -r "$SCALE_ENV" ] || { log "FAIL $SCALE_ENV tidak ada/terbaca"; exit 1; }

# SSH: fixed agent socket (key lama) prioritas, deploy key fallback
SSH_SOCK=/run/user/0/webgis-ssh-agent.sock
[ -S "$SSH_SOCK" ] && export SSH_AUTH_SOCK="$SSH_SOCK"
ssh_cmd() {
  if [ -n "${SSH_AUTH_SOCK:-}" ] && ssh-add -l >/dev/null 2>&1; then
    echo "ssh -o StrictHostKeyChecking=no"
  elif [ -f ~/.ssh/id_deploy_webgis ]; then
    echo "ssh -i ~/.ssh/id_deploy_webgis -o StrictHostKeyChecking=no -o BatchMode=yes"
  else
    echo "ssh -o StrictHostKeyChecking=no"
  fi
}
export GIT_SSH_COMMAND="$(ssh_cmd)"

git fetch origin main 2>&1 | while read -r l; do log "fetch: $l"; done
if [ "${PIPESTATUS[0]}" -ne 0 ]; then
  # fallback: coba ssh default (key lama via agent)
  log "fetch via deploy key gagal, coba ssh default"
  export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"
  git fetch origin main 2>&1 | while read -r l; do log "fetch2: $l"; done
  if [ "${PIPESTATUS[0]}" -ne 0 ]; then
    log "FAIL git fetch (deploy key belum ditambah ke GitHub?)"
    exit 1
  fi
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
log "local=$LOCAL remote=$REMOTE"
if [ "$LOCAL" = "$REMOTE" ]; then
  log "SKIP already up-to-date $LOCAL"
  echo "SKIP up-to-date"
  exit 0
fi

CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE" | head -30 | tr '\n' ' ')
log "changed files: $CHANGED"

if ! git pull --ff-only origin main 2>&1 | while read -r l; do log "pull: $l"; done; then
  log "FAIL git pull --ff-only (diverged? manual fix)"
  exit 1
fi
NEWHEAD=$(git rev-parse HEAD)
log "pulled -> $NEWHEAD"

# tag backup image saat ini
TS=$(date +%Y%m%d-%H%M%S)
log "tag backup prev-$TS"
# Tag pakai NAMA image compose (mis. webgis-backend_fastapi:prev-TS) supaya blok rollback
# di bawah bisa menemukannya. Sumbernya image ID yang DIPAKAI container yang sedang jalan,
# bukan :latest (latest bisa sudah berisi build gagal yang belum pernah jalan).
# Image app stack scale (webgis-scale-backend:latest, webgis-scale-dashboard:latest)
IMGS="webgis-scale-backend:latest webgis-scale-dashboard:latest"
HAPROXY_CHANGED=0; COMPOSE_CHANGED=0
git diff --name-only "$LOCAL" "$NEWHEAD" | grep -qx 'infra/haproxy/haproxy.cfg' && HAPROXY_CHANGED=1
git diff --name-only "$LOCAL" "$NEWHEAD" | grep -qx "$COMPOSE_FILE_REL" && COMPOSE_CHANGED=1
log "haproxy.cfg berubah=$HAPROXY_CHANGED compose berubah=$COMPOSE_CHANGED"
backup_tag_images() {
  local img base svc cid src
  for img in $IMGS; do
    base="${img%%:*}"
    case "$base" in
      webgis-scale-backend) svc=backend_fastapi ;;
      webgis-scale-dashboard) svc=gis-dashboard ;;
      *) svc="" ;;
    esac
    cid=$($COMPOSE ps -q --status running "$svc" 2>/dev/null | head -1)
    src=""
    if [ -n "$cid" ]; then
      src=$(docker inspect -f "{{.Image}}" "$cid" 2>/dev/null)
    fi
    if [ -z "$src" ]; then
      log "WARN container $svc tidak jalan, backup pakai $img"
      docker image inspect "$img" >/dev/null 2>&1 && src="$img"
    fi
    if [ -n "$src" ]; then
      docker tag "$src" "$base:prev-$TS" && log "backup $svc (${src:0:19}) -> $base:prev-$TS" || log "WARN gagal tag $img"
    else
      log "WARN image $img belum ada, tidak ada backup untuk rollback"
    fi
  done
}
backup_tag_images

log "build..."
if ! $COMPOSE build backend_fastapi gis-dashboard 2>&1 | tail -5 | while read -r l; do log "build: $l"; done; then
  log "FAIL build"
  exit 1
fi

# ---- backup DB + migrasi (sebelum container lama diganti) ----
BACKUP_DIR=/var/backups/postgres
# Nama DB dibaca dari backend_fastapi/.env (DB_NAME); gagal = deploy dibatalkan
DB_NAME_BK=$(sed -n 's/^DB_NAME=//p' "$REPO/backend_fastapi/.env" | tail -1 | tr -d '\r"' | xargs)
if [ -z "$DB_NAME_BK" ] && [ "${SKIP_DB_STEPS:-0}" != "1" ]; then log "FAIL DB_NAME tidak ditemukan di backend_fastapi/.env -> deploy dibatalkan"; exit 1; fi
KEEP_DUMPS=10
db_backup() {
  mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR" || return 1
  local f="$BACKUP_DIR/${DB_NAME_BK}-predeploy-$TS.dump"
  if ! docker exec gis-postgres pg_dump -U postgres -Fc -d "$DB_NAME_BK" > "$f.tmp" 2>>"$LOG"; then
    rm -f "$f.tmp"; return 1
  fi
  [ -s "$f.tmp" ] || { rm -f "$f.tmp"; return 1; }
  mv "$f.tmp" "$f" && chmod 600 "$f"
  log "backup DB OK $f ($(du -h "$f" | cut -f1))"
  # retensi: simpan 10 file .dump terbaru (semua jenis backup)
  ls -1t "$BACKUP_DIR"/*.dump 2>/dev/null | tail -n +$((KEEP_DUMPS+1)) | while read -r old; do
    rm -f "$old" && log "retensi: hapus $old"
  done
}
db_migrate() {
  # infra (redis/pgbouncer) harus jalan; up -d tanpa recreate bila tidak berubah.
  $COMPOSE up -d $INFRA_SVCS 2>&1 | while read -r l; do log "infra: $l"; done
  $COMPOSE run --rm --no-deps -T backend_fastapi python -m scripts.apply_migrations </dev/null 2>&1 | while read -r l; do log "migrate: $l"; done
}
if [ "${SKIP_DB_STEPS:-0}" != "1" ]; then
  log "backup DB..."
  if ! db_backup; then
    log "FAIL backup DB -> deploy dibatalkan, container lama tetap jalan"
    exit 1
  fi
  log "migrasi DB (image baru, container sementara)..."
  if ! db_migrate; then
    log "FAIL migrasi DB -> deploy dibatalkan, container lama tetap jalan (backup: $BACKUP_DIR/${DB_NAME_BK}-predeploy-$TS.dump)"
    exit 1
  fi
  log "migrasi DB OK"
fi

if [ "$COMPOSE_CHANGED" = "1" ]; then
  log "compose berubah -> up -d (hanya service yang konfigurasinya berubah di-recreate)"
  $COMPOSE up -d 2>&1 | while read -r l; do log "up-infra: $l"; done
fi
log "up -d --force-recreate --no-deps $APP_SVCS ..."
if ! $COMPOSE up -d --force-recreate --no-deps $APP_SVCS 2>&1 | while read -r l; do log "up: $l"; done; then
  log "FAIL compose up"
  exit 1
fi
if [ "$HAPROXY_CHANGED" = "1" ]; then
  log "haproxy.cfg berubah -> validasi + recreate haproxy"
  if docker run --rm -v "$REPO/infra/haproxy:/usr/local/etc/haproxy:ro" haproxy:2.9.15-alpine haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg >/dev/null 2>&1; then
    $COMPOSE up -d --force-recreate --no-deps haproxy 2>&1 | while read -r l; do log "haproxy: $l"; done
  else
    log "WARN haproxy.cfg baru TIDAK valid -> haproxy lama dipertahankan"
  fi
else
  $COMPOSE up -d --no-deps haproxy 2>&1 | while read -r l; do log "haproxy: $l"; done
fi

# >>> health-check (semua cek harus lolos di try yang SAMA, 2x berturut-turut, jeda 5 dtk)
# Frontend: 2xx OK; 3xx hanya OK bila Location ke /login atau /maintenance (relatif / host yang sama).
fe_check() {
  local url=$1 hdr code loc host lhost path
  hdr=$(curl -s -o /dev/null -D - -m 5 "$url" 2>/dev/null || true)
  code=$(printf '%s\n' "$hdr" | tr -d '\r' | awk 'toupper($1) ~ /^HTTP\// {c=$2} END {print c}')
  code=${code:-000}
  loc=$(printf '%s\n' "$hdr" | tr -d '\r' | awk 'tolower($1)=="location:" {print $2}' | tail -n 1)
  FE_DESC="$code${loc:+->$loc}"
  case "$code" in
    2??) return 0 ;;
    3??) ;;
    *) return 1 ;;
  esac
  path=$loc
  case "$loc" in
    http://*|https://*)
      host=${url#*://}; host=${host%%/*}
      lhost=${loc#*://}; lhost=${lhost%%/*}
      [ "$lhost" = "$host" ] || return 1
      path=/${loc#*://*/}
      [ "$path" = "/$loc" ] && path=/
      ;;
  esac
  path=${path%%\?*}; path=${path%%#*}; path=${path%/}
  case "$path" in /login|/maintenance) return 0 ;; esac
  return 1
}

health_try() {
  ok_be=0; ok_fe=0; ok_api=0; ok_pub=0
  BE=$(curl -s -m 5 "$BE_HEALTH" || true)
  echo "$BE" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' && ok_be=1
  fe_check "$FE_URL" && ok_fe=1; FE_CODE=$FE_DESC
  # curl sudah mencetak 000 saat gagal; jangan tambah "|| echo 000"
  API_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$PENGUMUMAN" 2>/dev/null || true); API_CODE=${API_CODE:-000}
  # 401 = auth guard hidup (ok); 307 = FastAPI slash redirect (ok)
  { [ "$API_CODE" = "401" ] || [ "$API_CODE" = "307" ]; } && ok_api=1
  PUB_DESC=""
  if [ -n "${PUB_BE:-}" ]; then
    PB=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$PUB_BE" 2>/dev/null || true); PB=${PB:-000}
    fe_check "$PUB_FE" && [ "$PB" = "200" ] && ok_pub=1
    PUB_DESC=" pub=$ok_pub(be=$PB fe=$FE_DESC)"
  else
    ok_pub=1
  fi
  # HAProxy: minimal 1 server UP di api_backends dan fe_backends
  ok_lb=0
  STATS=$(curl -s -m 5 "$HAPROXY_STATS" 2>/dev/null || true)
  UP_API=$(printf '%s\n' "$STATS" | awk -F, '$1=="api_backends" && $2!="BACKEND" && $18=="UP"' | wc -l)
  UP_FE=$(printf '%s\n' "$STATS" | awk -F, '$1=="fe_backends" && $2!="BACKEND" && $18=="UP"' | wc -l)
  [ "$UP_API" -ge 1 ] && [ "$UP_FE" -ge 1 ] && ok_lb=1
  HEALTH_LINE="be=$ok_be($BE) fe=$ok_fe($FE_CODE) api=$ok_api($API_CODE) lb=$ok_lb(api_up=$UP_API fe_up=$UP_FE)$PUB_DESC"
  [ "$ok_be$ok_fe$ok_api$ok_pub$ok_lb" = "11111" ]
}

# 30 try x 5 dtk (~2,5 mnt + waktu curl); healthy = 2 try berturut-turut lolos
health_wait() {
  local i streak=0
  HEALTHY=0
  for i in $(seq 1 "${HEALTH_TRIES:-30}"); do
    sleep "${HEALTH_SLEEP:-5}"
    if health_try; then
      streak=$((streak + 1))
      log "health try $i PASS ($streak/2) $HEALTH_LINE"
      if [ "$streak" -ge 2 ]; then
        log "health OK try $i $HEALTH_LINE"
        HEALTHY=1
        return 0
      fi
    else
      streak=0
      log "health try $i FAIL $HEALTH_LINE"
    fi
  done
  return 1
}
# <<< health-check

health_wait

if [ "$HEALTHY" = "1" ]; then
  log "DEPLOY OK head=$NEWHEAD"
  echo "OK $NEWHEAD"
  exit 0
fi

log "HEALTH FAIL (last: $HEALTH_LINE) -> rollback prev-$TS"
for img in $IMGS; do
  base="${img%%:*}"
  if docker image inspect "$base:prev-$TS" >/dev/null 2>&1; then
    docker tag "$base:prev-$TS" "$img" 2>/dev/null || true
  fi
done
$COMPOSE up -d --force-recreate --no-deps $APP_SVCS 2>&1 | tail -3 | while read -r l; do log "rollback: $l"; done
log "ROLLED BACK to prev-$TS"
echo "ROLLBACK prev-$TS"
exit 1
