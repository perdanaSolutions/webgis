"""
Konversi (bulan, tahun) API <-> kolom `period` (domain ref.month_period = tanggal 1 tiap bulan).
"""
from datetime import date

from app.core.exceptions import bad_request


def to_period(bulan: int, tahun: int) -> date:
    if not 1 <= int(bulan) <= 12:
        raise bad_request("Bulan harus di antara 1-12.", field="bulan")
    return date(int(tahun), int(bulan), 1)


def period_parts(period: date | None) -> tuple[int | None, int | None]:
    if period is None:
        return None, None
    return period.month, period.year


def period_label(period: date | None) -> str | None:
    return f"{period.month}-{period.year}" if period else None


def as_of_period(bulan: int | None, tahun: int | None) -> date | None:
    """
    Batas atas periode untuk query "kondisi per periode":
    bulan+tahun -> bulan itu; hanya tahun -> Desember tahun itu; kosong -> None (tanpa batas / terbaru).
    """
    if tahun is None:
        return None
    return to_period(bulan or 12, tahun)
