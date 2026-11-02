#!/usr/bin/env sh
# Smoke auth lintas replica (sticky OFF): login → /me → logout → /me = 401.
# Kredensial hanya dari env shell (jangan cat .env di skrip).
# Usage:
#   export SMOKE_EMAIL='user@example.com'
#   export SMOKE_PASSWORD='...'   # set di shell VPS, jangan commit
#   LB_BASE=http://127.0.0.1:8080 ./infra/scripts/smoke-auth-scale.sh
set -eu
LB_BASE="${LB_BASE:-http://127.0.0.1:8080}"
API="${LB_BASE%/}/api/v1"
SMOKE_EMAIL="${SMOKE_EMAIL:-}"
SMOKE_PASSWORD="${SMOKE_PASSWORD:-}"
ME_HITS="${ME_HITS:-8}"

if [ -z "$SMOKE_EMAIL" ] || [ -z "$SMOKE_PASSWORD" ]; then
  echo "FAIL: set SMOKE_EMAIL dan SMOKE_PASSWORD di environment shell" >&2
  exit 2
fi

echo "== POST $API/auth/login =="
login_body="$(curl -fsS -X POST "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -H 'accept: application/json' \
  -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}")"
token="$(printf '%s' "$login_body" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
if [ -z "$token" ]; then
  echo "FAIL: access_token kosong" >&2
  echo "$login_body" >&2
  exit 1
fi
echo "OK login (token diterima)"

echo "== GET /auth/me × $ME_HITS (replica acak via LB) =="
i=0
while [ "$i" -lt "$ME_HITS" ]; do
  code="$(curl -sS -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $token" \
    -H 'accept: application/json' \
    "$API/auth/me")"
  if [ "$code" != "200" ]; then
    echo "FAIL: /me HTTP $code sebelum logout (hit $((i + 1)))" >&2
    exit 1
  fi
  i=$((i + 1))
done
echo "OK /me 200 di semua hit (tanpa sticky)"

echo "== POST /auth/logout =="
logout_code="$(curl -sS -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $token" \
  -H 'accept: application/json' \
  "$API/auth/logout")"
if [ "$logout_code" != "200" ]; then
  echo "FAIL: logout HTTP $logout_code" >&2
  exit 1
fi
echo "OK logout"

echo "== GET /auth/me token lama × $ME_HITS → wajib 401 =="
i=0
while [ "$i" -lt "$ME_HITS" ]; do
  code="$(curl -sS -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $token" \
    -H 'accept: application/json' \
    "$API/auth/me")"
  if [ "$code" != "401" ]; then
    echo "FAIL: setelah logout /me HTTP $code (harus 401), hit $((i + 1))" >&2
    exit 1
  fi
  i=$((i + 1))
done
echo "OK token dicabut lintas instance (401)"

echo "Smoke auth-scale selesai (PASS)."
