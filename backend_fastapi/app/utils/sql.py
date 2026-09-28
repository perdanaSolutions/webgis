"""
Identifier SQL yang dibangun dari input (nama layer dinamis, kolom GeoJSON).

Postgres tidak menerima nama tabel/kolom sebagai bind parameter, jadi SETIAP
identifier dari input wajib lewat `sanitize_identifier` lalu `quote_ident`.
Jangan pernah menyisipkan input mentah ke SQL dengan f-string.
"""
import re

from app.core.exceptions import bad_request

IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
FORBIDDEN_PREFIXES = ("pg_", "sys_")
ALLOWED_SCHEMAS = {"spatial", "trx", "master", "auth", "audit", "ref", "quarantine"}


def sanitize_identifier(raw: str, prefix: str = "") -> str:
    if not raw or not str(raw).strip():
        raise bad_request("Nama tidak boleh kosong.")
    value = re.sub(r"[^a-z0-9]+", "_", str(raw).strip().lower())
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        raise bad_request(f"Nama '{raw}' tidak menghasilkan identifier yang valid.")
    if value[0].isdigit():
        value = f"c_{value}"
    value = f"{prefix}{value}"[:63].rstrip("_")
    if not IDENTIFIER_PATTERN.match(value) or value.startswith(FORBIDDEN_PREFIXES):
        raise bad_request(f"Identifier hasil sanitasi tidak valid: '{value}'.")
    return value


def quote_ident(name: str) -> str:
    if not IDENTIFIER_PATTERN.match(name):
        raise bad_request(f"Identifier tidak aman untuk SQL: '{name}'.")
    return f'"{name}"'


def quote_table(qualified_name: str) -> str:
    """'spatial.roads' -> '"spatial"."roads"' dengan validasi schema & nama tabel."""
    schema, _, table = qualified_name.partition(".")
    if not table:
        schema, table = "public", schema
    if schema not in ALLOWED_SCHEMAS:
        raise bad_request(f"Schema '{schema}' tidak diizinkan.")
    return f"{quote_ident(schema)}.{quote_ident(table)}"
