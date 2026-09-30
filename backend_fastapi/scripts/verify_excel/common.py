"""
Bantu verifikasi data Excel <-> database (hanya BACA; tidak menulis apa pun).

Konfigurasi lewat environment variable (semua opsional):
  EXCEL_DIR       folder berisi ketiga file Excel           (default: ~/Downloads)
  EXCEL_AREAL     nama file areal statement
  EXCEL_PRODUKSI  nama file produksi (boleh format Strict OOXML)
  EXCEL_ROTASI    nama file rotasi & pusingan
  VERIFY_DB       nama database yang dibaca                 (default: DB_NAME dari .env / gis_db_v3)
Koneksi database mengikuti app/core/config.py (.env).
"""
import csv
import os
import re
import sys
import tempfile
import warnings
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np  # noqa: F401  (diekspor ke skrip yang memakai `from common import *`)
import pandas as pd
import psycopg2

warnings.simplefilter("ignore")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # Settings membaca .env relatif terhadap direktori kerja

from app.core.config import settings  # noqa: E402

EXCEL_DIR = Path(os.environ.get("EXCEL_DIR", Path.home() / "Downloads"))
F_AREAL = EXCEL_DIR / os.environ.get("EXCEL_AREAL", "Data-Areal-Statement-2025-2026-convert.xlsx")
F_PRODUKSI = EXCEL_DIR / os.environ.get("EXCEL_PRODUKSI", "Data Plantation Produksi 2025-2026 (1).xlsx")
F_ROTASI = EXCEL_DIR / os.environ.get("EXCEL_ROTASI", "Data Transaksi - Rotasi&Pusingan_Sample-convert.xlsx")
DB_NAME = os.environ.get("VERIFY_DB", settings.DB_NAME)
CACHE = Path(tempfile.gettempdir()) / "verify_excel_cache"
CACHE.mkdir(exist_ok=True)

MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
BLK = "bl.id block_id, e.code est, d.code dv, bl.code blk"   # `dv`, bukan `div` (bentrok dgn DataFrame.div)
BJ = "FROM master.blocks bl JOIN master.divisions d ON d.id=bl.division_id JOIN master.estates e ON e.id=d.estate_id"


def con(db: str | None = None):
    return psycopg2.connect(host=settings.DB_HOST, port=settings.DB_PORT, user=settings.DB_USER,
                            password=settings.DB_PASSWORD, dbname=db or DB_NAME)


def sql(q: str, db: str | None = None) -> pd.DataFrame:
    c = con(db)
    try:
        return pd.read_sql(q, c)
    finally:
        c.close()


def load_stmt() -> pd.DataFrame:
    return pd.read_excel(F_AREAL)


def load_rot() -> pd.DataFrame:
    return pd.read_excel(F_ROTASI)


def _strict_xlsx_to_csv(src: Path, dest: Path, ncols: int = 23) -> None:
    """Excel 'Strict Open XML' tidak terbaca openpyxl; urai XML sheet pertama langsung ke CSV."""
    ns = "{http://purl.oclc.org/ooxml/spreadsheetml/main}"
    z = zipfile.ZipFile(src)
    strings = []
    for _, el in ET.iterparse(z.open("xl/sharedStrings.xml")):
        if el.tag == ns + "si":
            strings.append("".join(t.text or "" for t in el.iter(ns + "t")))
            el.clear()

    def col_index(ref: str) -> int:
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group():
            n = n * 26 + ord(ch) - 64
        return n - 1

    with open(dest, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        for _, el in ET.iterparse(z.open("xl/worksheets/sheet1.xml")):
            if el.tag == ns + "row":
                row = [""] * ncols
                for c in el.findall(ns + "c"):
                    v = c.find(ns + "v")
                    if v is None:
                        continue
                    val = strings[int(v.text)] if c.get("t") == "s" else v.text
                    i = col_index(c.get("r"))
                    if i < ncols:
                        row[i] = val
                writer.writerow(row)
                el.clear()


def load_prod() -> pd.DataFrame:
    """Produksi; baris total Excel di paling bawah (Year tak wajar) dibuang."""
    if str(F_PRODUKSI).lower().endswith(".csv"):
        x = pd.read_csv(F_PRODUKSI)
    else:
        try:
            x = pd.read_excel(F_PRODUKSI)
        except Exception:
            x = None
        if x is None or x.empty:
            cache = CACHE / (F_PRODUKSI.stem + ".csv")
            if not cache.exists() or cache.stat().st_mtime < F_PRODUKSI.stat().st_mtime:
                _strict_xlsx_to_csv(F_PRODUKSI, cache)
            x = pd.read_csv(cache)
    return x[x.Year.isin([2024, 2025, 2026])].copy()


load_prod_raw = load_prod
