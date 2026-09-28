"""
Bulk insert dengan PostgreSQL COPY dalam transaksi sesi SQLAlchemy yang sedang berjalan
(ikut ter-rollback kalau langkah lain gagal). Geometry dikirim sebagai hex EWKB.
"""
import io
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.utils.sql import quote_ident


def _escape(value: Any) -> str:
    if value is None:
        return "\\N"
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, (list, tuple)):
        return "{" + ",".join(str(v) for v in value) + "}"
    text_value = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return text_value.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def copy_rows(db: Session, table_sql: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
    """`table_sql` harus identifier yang sudah di-quote/tervalidasi (mis. hasil quote_table)."""
    buffer = io.StringIO()
    count = 0
    for row in rows:
        buffer.write("\t".join(_escape(v) for v in row) + "\n")
        count += 1
    if not count:
        return 0
    buffer.seek(0)
    cols = ", ".join(quote_ident(c) for c in columns)
    cursor = db.connection().connection.cursor()
    try:
        cursor.copy_expert(f"COPY {table_sql} ({cols}) FROM STDIN WITH (FORMAT text)", buffer)
    finally:
        cursor.close()
    return count
