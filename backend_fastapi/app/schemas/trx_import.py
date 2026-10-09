from pydantic import BaseModel, Field

MAX_JSON_ROWS = 100_000

Scalar = str | int | float | bool | None


class TrxJsonImport(BaseModel):
    """Baris transaksi dalam JSON. Nama kolom sama dengan header file Excel (mis. KodeBlok, Bulan, Tahun)."""

    sumber: str | None = Field(
        default=None, max_length=255,
        description="Nama sumber data untuk riwayat upload (mis. nama sistem pengirim). Default 'JSON API'.",
    )
    data: list[dict[str, Scalar]] = Field(min_length=1, max_length=MAX_JSON_ROWS)
