# Verifikasi Excel <-> Database <-> Respons API

Hanya membaca database; tidak menulis apa pun. Jalankan dari `backend_fastapi/`:

    venv/Scripts/python.exe scripts/verify_excel/run_all.py

Konfigurasi (env, opsional): `EXCEL_DIR` (default `~/Downloads`), `EXCEL_AREAL`, `EXCEL_PRODUKSI`,
`EXCEL_ROTASI`, `VERIFY_DB` (default `DB_NAME` dari `.env`). Format Excel "Strict Open XML" dibaca otomatis.

| Skrip | Yang dicek |
|---|---|
| `l1_*` | Data mentah di tabel `trx.*` vs baris Excel (laporan informasi) |
| `l2_history_produksi.py` | `GET /history` `trx_produksi_tbs`: 606 skenario filter x tahun, dihitung ulang dari Excel |
| `l2_history_areal_rotasi.py` | `trx_areal_statement` dan `trx_rotasi_pusingan` |
| `l2_detail.py` | `GET /spatial/blok/detail` untuk ~1.100 kombinasi blok/tahun/bulan |
| `l3_http.py` | Request HTTP nyata (token superadmin) == keluaran service |

Pengecualian yang diketahui (file produksi `(1)`): 113 baris ganda/bertentangan tidak dimuat (lihat
`quarantine.rows`), dan 4 sel 2.970 kg tercatat `E017` di Excel tetapi disimpan di `E014`/`E027` di database
(`REROUTE` di `l2_history_produksi.py` dan `l2_detail.py`). Perbarui bila file sumber berubah.
