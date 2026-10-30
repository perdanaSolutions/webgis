"""Satu-satunya aturan kategori GAP produksi (rumus Excel lama), dipakai detail blok, peta, histori, rekap, Gap Produksi.

    gap >= 0            -> OPTIMUM  (tepat 0 = OPTIMUM)
    -20 < gap < 0       -> GAP I
    -40 <= gap <= -20   -> GAP II   (tepat -20 dan tepat -40 = GAP II)
    gap < -40           -> GAP III
    None (tanpa target) -> tanpa kategori
"""


def gap_kategori(value: float | None) -> str:
    """Kategori GAP; "" bila value None."""
    if value is None:
        return ""
    if value < -40:
        return "GAP III"
    if value <= -20:
        return "GAP II"
    if value < 0:
        return "GAP I"
    return "OPTIMUM"
