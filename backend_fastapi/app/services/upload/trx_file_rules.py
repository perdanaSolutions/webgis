"""Aturan file upload Excel transaksi (halaman /transaksi): hanya .xlsx / .xls."""
from app.core.exceptions import bad_request

TRX_EXCEL_EXTENSIONS = (".xlsx", ".xls")


def is_trx_excel_filename(filename: str | None) -> bool:
    return (filename or "").strip().lower().endswith(TRX_EXCEL_EXTENSIONS)


def ensure_trx_excel_file(filename: str | None) -> None:
    """Tolak file non-Excel (termasuk .json) untuk layer transaksi dengan alasan yang jelas (400)."""
    if is_trx_excel_filename(filename):
        return
    name = (filename or "").strip() or "(tanpa nama)"
    raise bad_request(
        f"Format file '{name}' tidak didukung untuk upload transaksi. "
        "Hanya file Excel (.xlsx atau .xls) yang bisa diupload; file JSON tidak lagi diterima.",
        field="file",
    )
