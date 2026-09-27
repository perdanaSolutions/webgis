"""Konversi nilai mentah (Excel / properti GeoJSON / hasil DB) ke tipe Python yang aman."""
import math
import re
from functools import lru_cache
from decimal import Decimal
from typing import Any

MONTHS = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "februari": 2, "february": 2, "peb": 2,
    "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5, "mei": 5,
    "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7,
    "aug": 8, "agu": 8, "agt": 8, "agustus": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "okt": 10, "oktober": 10, "october": 10,
    "nov": 11, "nop": 11, "november": 11, "nopember": 11,
    "dec": 12, "des": 12, "desember": 12, "december": 12,
}
MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
              7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


# Penanda "kosong" yang lazim di ekspor Excel/pivot (mis. '(Blanks)' di kolom Status Pusingan).
BLANK_MARKERS = {"", "(blank)", "(blanks)", "-", "--", "n/a", "#n/a", "null", "none", "nan"}


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and value.strip().lower() in BLANK_MARKERS


def clean_str(value: Any) -> str | None:
    if is_blank(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip() or None


def to_float(value: Any) -> float | None:
    if is_blank(value):
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    number = to_float(value)
    return int(number) if number is not None else None


def to_month(value: Any) -> int | None:
    """Terima 1-12, '01', 'Jan', 'Januari', tanggal (ambil bulannya)."""
    if is_blank(value):
        return None
    if hasattr(value, "month"):
        return value.month
    number = to_int(value)
    if number is not None:
        return number if 1 <= number <= 12 else None
    text = str(value).strip().lower()
    return MONTHS.get(text) or MONTHS.get(text[:3])


@lru_cache(maxsize=65536)
def _norm_text(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def norm_key(value: Any) -> str:
    """Kunci pencocokan longgar: huruf besar, tanpa spasi/titik/strip. 'PT. Telen' == 'PT TELEN'."""
    return _norm_text(str(value or ""))


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def num(value: Any, default: float = 0.0) -> float:
    return float(value) if value is not None else default


def whole(value: Any, default: int = 0) -> int:
    return int(value) if value is not None else default
