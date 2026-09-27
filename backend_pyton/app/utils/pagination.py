import math
from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def page_response(total: int, page: int, limit: int, data: Sequence[Any]) -> dict:
    return {
        "total_data": total,
        "page": page,
        "limit": limit,
        "total_page": max(math.ceil(total / limit), 1) if limit else 1,
        "data": list(data),
    }


def paginate_sql(
    db: Session,
    select_sql: str,
    params: dict,
    order_by: str,
    page: int,
    limit: int,
    formatter: Callable[[dict], dict] = dict,
) -> dict:
    """
    Pagination untuk query mentah dalam 1 round-trip (COUNT(*) OVER()).
    `select_sql` = SELECT lengkap tanpa ORDER BY/LIMIT. Fallback COUNT terpisah
    hanya jika halaman yang diminta di luar jangkauan data.
    """
    sql = f"SELECT q.*, COUNT(*) OVER() AS _total FROM ({select_sql}) q ORDER BY {order_by} LIMIT :_limit OFFSET :_offset"
    rows = db.execute(text(sql), {**params, "_limit": limit, "_offset": (page - 1) * limit}).mappings().all()
    if rows:
        total = rows[0]["_total"]
    else:
        total = db.execute(text(f"SELECT COUNT(*) FROM ({select_sql}) q"), params).scalar_one()
    data = [formatter({k: v for k, v in row.items() if k != "_total"}) for row in rows]
    return page_response(total, page, limit, data)
