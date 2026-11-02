#!/usr/bin/env sh
# Smoke HAProxy: health + redis_auth + bukti round-robin (field instance).
# Tidak membaca .env / secret.
# Usage:
#   LB_BASE=http://127.0.0.1:8080 ./infra/scripts/smoke-lb.sh
#   RR_SAMPLES=20 MIN_UNIQUE_INSTANCES=2 LB_BASE=http://127.0.0.1:8080 ./infra/scripts/smoke-lb.sh
set -eu
LB_BASE="${LB_BASE:-http://127.0.0.1:8080}"
RR_SAMPLES="${RR_SAMPLES:-20}"
MIN_UNIQUE_INSTANCES="${MIN_UNIQUE_INSTANCES:-2}"

echo "== GET $LB_BASE/health =="
body="$(curl -fsS "$LB_BASE/health")"
echo "$body"
echo "$body" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' || {
  echo "FAIL: status bukan ok" >&2
  exit 1
}
echo "$body" | grep -Eq '"redis_auth"[[:space:]]*:[[:space:]]*"enabled"' || {
  echo "FAIL: redis_auth bukan enabled (horizontal auth butuh Redis jti)" >&2
  exit 1
}
echo "OK health + redis_auth=enabled"

echo "== Round-robin / sticky OFF ($RR_SAMPLES sampel) =="
tmp="$(mktemp)"
i=0
while [ "$i" -lt "$RR_SAMPLES" ]; do
  curl -fsS "$LB_BASE/health" | sed -n 's/.*"instance"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' >>"$tmp" || true
  i=$((i + 1))
done
uniq_count="$(sort -u "$tmp" | grep -c . || true)"
echo "instance unik: $uniq_count (min $MIN_UNIQUE_INSTANCES)"
sort -u "$tmp" | sed 's/^/  - /'
rm -f "$tmp"
if [ "$uniq_count" -lt "$MIN_UNIQUE_INSTANCES" ]; then
  echo "FAIL: terlalu sedikit hostname unik — cek --scale backend_fastapi>=2 dan sticky OFF" >&2
  exit 1
fi
echo "OK distribusi instance (tanpa affinity)"

echo "== HEAD FE via LB =="
code="$(curl -sS -o /dev/null -w "%{http_code}" "$LB_BASE/")"
case "$code" in
  2*|3*) echo "OK FE HTTP $code" ;;
  *) echo "FAIL FE HTTP $code" >&2; exit 1 ;;
esac

echo "Smoke LB selesai (PASS)."
