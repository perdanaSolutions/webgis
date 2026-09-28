import io
import zipfile
from typing import Any

import pandas as pd

from app.core.exceptions import bad_request
from app.utils.parsing import is_blank

_STRICT_REPLACEMENTS = (
    (b"http://purl.oclc.org/ooxml/spreadsheetml/main", b"http://schemas.openxmlformats.org/spreadsheetml/2006/main"),
    (b"http://purl.oclc.org/ooxml/officeDocument/relationships",
     b"http://schemas.openxmlformats.org/officeDocument/2006/relationships"),
    (b'conformance="strict"', b""),
)


def _strict_to_transitional(content: bytes) -> bytes:
    """File .xlsx 'Strict Open XML' tidak bisa dibaca openpyxl; ubah namespace-nya ke format standar."""
    try:
        source = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        return content
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.endswith((".xml", ".rels")):
                for old, new in _STRICT_REPLACEMENTS:
                    data = data.replace(old, new)
            target.writestr(item, data)
    return output.getvalue()


def read_excel_rows(filename: str | None, content: bytes) -> list[dict[str, Any]]:
    if not (filename or "").lower().endswith((".xlsx", ".xls")):
        raise bad_request("Format file harus Excel (.xlsx/.xls).", field="file")
    data = _strict_to_transitional(content)
    try:
        # calamine (Rust) ~6x lebih cepat dari openpyxl untuk file puluhan ribu baris.
        frame = pd.read_excel(io.BytesIO(data), engine="calamine")
    except Exception:
        try:
            engine = "openpyxl" if filename.lower().endswith(".xlsx") else None
            frame = pd.read_excel(io.BytesIO(data), engine=engine)
        except Exception as exc:  # pandas melempar banyak jenis error untuk file rusak
            raise bad_request(f"File Excel tidak bisa dibaca: {exc}", field="file") from exc
    frame.columns = [str(c).strip() for c in frame.columns]
    frame = frame.astype(object).where(frame.notna(), None)
    return frame.to_dict(orient="records")


def pick(row: dict[str, Any], *names: str) -> Any:
    """Ambil nilai kolom pertama yang tersedia dari beberapa kemungkinan nama header."""
    for name in names:
        value = row.get(name)
        if not is_blank(value):
            return value
    return None
