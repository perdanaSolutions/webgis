#!/usr/bin/env bash
# Sertifikat mTLS internal: Root CA, server backend-webgis, klien backend-external.
#
# Hasil:
#   certs/private/ca.key   RAHASIA. Jangan dipasang di aplikasi atau image.
#   certs/runtime/         server.crt, server.key, ca.crt untuk backend-webgis
#   certs/client/          client.crt, client.key, ca.crt untuk backend-external
#
# Argumen opsional:
#   $1 direktori keluaran (default: backend_fastapi/certs)
#   $2 SAN tambahan, contoh: 'DNS:gis.internal,IP:10.0.0.8'
#
# extendedKeyUsage ditambahkan karena OpenSSL 3 menolak sertifikat tanpa purpose
# serverAuth / clientAuth saat handshake.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/certs}"
EXTRA_SAN="${2:-}"

mkdir -p "$OUT/private" "$OUT/runtime" "$OUT/client"
umask 077

openssl genrsa -out "$OUT/private/ca.key" 4096
# keyUsage CA wajib: OpenSSL 3 menolak CA tanpa ekstensi ini saat verifikasi.
openssl req -x509 -new -nodes -key "$OUT/private/ca.key" -sha256 -days 3650 \
  -out "$OUT/private/ca.crt" \
  -subj "/CN=Internal-API-CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

openssl genrsa -out "$OUT/runtime/server.key" 2048
openssl req -new -key "$OUT/runtime/server.key" -out "$WORK/server.csr" \
  -subj "/CN=backend-webgis"

SAN="DNS:backend-webgis,DNS:localhost,IP:127.0.0.1,IP:0.0.0.0"
if [[ -n "$EXTRA_SAN" ]]; then
  SAN="${SAN},${EXTRA_SAN}"
fi
cat > "$WORK/server_ext.cnf" <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=${SAN}
EOF

openssl x509 -req -in "$WORK/server.csr" \
  -CA "$OUT/private/ca.crt" -CAkey "$OUT/private/ca.key" -CAcreateserial \
  -out "$OUT/runtime/server.crt" -days 365 -sha256 -extfile "$WORK/server_ext.cnf"
cp "$OUT/private/ca.crt" "$OUT/runtime/ca.crt"

openssl genrsa -out "$OUT/client/client.key" 2048
openssl req -new -key "$OUT/client/client.key" -out "$WORK/client.csr" \
  -subj "/CN=backend-external"
cat > "$WORK/client_ext.cnf" <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
EOF
openssl x509 -req -in "$WORK/client.csr" \
  -CA "$OUT/private/ca.crt" -CAkey "$OUT/private/ca.key" -CAcreateserial \
  -out "$OUT/client/client.crt" -days 365 -sha256 -extfile "$WORK/client_ext.cnf"
cp "$OUT/private/ca.crt" "$OUT/client/ca.crt"

chmod 600 "$OUT/private/ca.key" "$OUT/runtime/server.key" "$OUT/client/client.key"
chmod 644 "$OUT/private/ca.crt" "$OUT/runtime/server.crt" "$OUT/runtime/ca.crt" \
  "$OUT/client/client.crt" "$OUT/client/ca.crt"

openssl verify -CAfile "$OUT/private/ca.crt" "$OUT/runtime/server.crt" "$OUT/client/client.crt"

echo "CA pribadi (jangan dipasang di aplikasi): $OUT/private/ca.key"
echo "backend-webgis: $OUT/runtime/server.crt $OUT/runtime/server.key $OUT/runtime/ca.crt"
echo "backend-external: $OUT/client/client.crt $OUT/client/client.key $OUT/client/ca.crt"
