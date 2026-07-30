"""
Service untuk 2 kebutuhan terkait popup peta blok:

1. `get_blok_detail`  -> semua informasi 1 blok untuk 1 periode (dipanggil
   saat blok diklik di peta): data master blok + hierarki (afdeling/estate/
   PT/area) + snapshot 1 baris dari trx_areal_statement & trx_produksi_tbs
   + daftar (bisa lebih dari 1 baris per bulan) trx_rotasi_pusingan.

2. `get_history`      -> data mentah 1 tabel transaksi untuk 1 blok
   sepanjang 1 tahun (dipakai untuk grafik tren di dalam popup).

=========================== CATATAN KEAMANAN ===========================
`get_history` menerima nama tabel LANGSUNG dari parameter request FE.
Nama tabel TIDAK PERNAH dipakai membangun SQL sebelum dicocokkan ke
`HISTORY_TABLE_REGISTRY` (whitelist). Kalau tidak cocok -> 400, request
tidak pernah sampai ke SQL. Ini mencegah parameter itu dipakai mengakses
tabel lain (mis. users, sys_upload_log) di luar 3 tabel trx yang memang
dimaksudkan untuk endpoint ini.
===========================================================================
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

# Whitelist tabel yang boleh diakses lewat endpoint history generik, plus
# daftar kolom yang boleh di-SELECT (juga whitelist -- bukan "SELECT *")
# dan urutan sort-nya. Cuma tabel yang terdaftar di sini yang bisa diquery.
HISTORY_TABLE_REGISTRY = {
    "trx_areal_statement": {
        "label": "Pernyataan Areal (Areal Statement)",
        "columns": [
            "id_areal_statement", "blok_id", "tahun", "bulan",
            "luas_tanam", "luas_tanah", "total_pokok", "sph",
            "pct_tanah_datar", "pct_berbukit", "pct_gelombang", "pct_curam",
        ],
        "order_by": "tahun, bulan",
    },
    "trx_produksi_tbs": {
        "label": "Produksi TBS",
        "columns": [
            "id_produksi", "blok_id", "tahun", "bulan",
            "tbs_aktual", "tbs_budget", "tbs_sensus",
            "janjang_aktual", "janjang_budget", "janjang_sensus",
            "bjr_aktual", "bjr_budget", "bjr_sensus",
        ],
        "order_by": "tahun, bulan",
    },
    "trx_rotasi_pusingan": {
        "label": "Rotasi Pusingan",
        "columns": [
            "id_rotasi_pusingan", "blok_id", "tanggal", "tahun", "bulan",
            "rotasi_ke", "pusingan_hari", "status_pusingan",
        ],
        "order_by": "tanggal",
    },
}


# def get_history(db: Session, table: str, tahun: int, blok_id: Optional[str] = None) -> dict:
#     """
#     Ambil data mentah 1 tabel trx untuk 1 tahun (opsional difilter 1 blok),
#     dipakai untuk grafik/riwayat di dalam popup.
#     """
#     config = HISTORY_TABLE_REGISTRY.get(table)
#     if config is None:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Tabel '{table}' tidak tersedia untuk endpoint history. Pilihan: {sorted(HISTORY_TABLE_REGISTRY)}.",
#         )

#     # Aman: `table` di titik ini sudah PASTI salah satu literal key
#     # HISTORY_TABLE_REGISTRY (bukan string bebas dari request), begitu juga
#     # `columns_sql` yang seluruhnya berasal dari whitelist di atas.
#     columns_sql = ", ".join(config["columns"])
#     sql = f"SELECT {columns_sql} FROM {table} WHERE tahun = :tahun"
#     params = {"tahun": tahun}

#     if blok_id:
#         sql += " AND blok_id = :blok_id"
#         params["blok_id"] = blok_id

#     sql += f" ORDER BY {config['order_by']}"

#     rows = db.execute(text(sql), params).fetchall()
#     return {
#         "table": table,
#         "label": config["label"],
#         "tahun": tahun,
#         "blok_id": blok_id,
#         "total_data": len(rows),
#         "data": [dict(r._mapping) for r in rows],
#     }

# Whitelist tabel beserta rumus akumulasi SQL masing-masing
HISTORY_METRICS_CONFIG = {
    "trx_produksi_tbs": {
        "label": "Produksi TBS",
        "select": """
            SUM(COALESCE(t.tbs_aktual, 0)) AS tbs_aktual,
            SUM(COALESCE(t.tbs_budget, 0)) AS tbs_budget,
            SUM(COALESCE(t.tbs_sensus, 0)) AS tbs_sensus,
            SUM(COALESCE(t.janjang_aktual, 0)) AS janjang_aktual,
            SUM(COALESCE(t.janjang_budget, 0)) AS janjang_budget,
            SUM(COALESCE(t.janjang_sensus, 0)) AS janjang_sensus,
            AVG(COALESCE(t.bjr_aktual, 0)) AS bjr_aktual,
            AVG(COALESCE(t.bjr_budget, 0)) AS bjr_budget,
            AVG(COALESCE(t.bjr_sensus, 0)) AS bjr_sensus
        """
    },
    "trx_areal_statement": {
        "label": "Areal Statement",
        "select": """
            AVG(COALESCE(t.luas_tanam, 0)) AS luas_tanam,
            AVG(COALESCE(t.luas_tanah, 0)) AS luas_tanah,
            AVG(COALESCE(t.total_pokok, 0)) AS total_pokok,
            AVG(COALESCE(t.sph, 0)) AS sph,
            AVG(COALESCE(t.pct_tanah_datar, 0)) AS pct_tanah_datar,
            AVG(COALESCE(t.pct_berbukit, 0)) AS pct_berbukit,
            AVG(COALESCE(t.pct_gelombang, 0)) AS pct_gelombang,
            AVG(COALESCE(t.pct_curam, 0)) AS pct_curam
        """
    },
    "trx_rotasi_pusingan": {
        "label": "Rotasi Pusingan",
        "select": """
            COUNT(t.id_rotasi_pusingan) AS total_rotasi,
            MAX(t.rotasi_ke) AS rotasi_terakhir,
            AVG(COALESCE(t.pusingan_hari, 0)) AS avg_pusingan_hari,
            SUM(COALESCE(t.luas, 0)) AS total_luas_rotasi,
            SUM(COALESCE(t.pokok, 0)) AS total_pokok_rotasi
        """
    }
}


def get_history_aggregated(
    db: Session,
    table: str = "trx_produksi_tbs",
    tahun: Optional[int] = None,
    area_id: Optional[str] = None,
    kode_pt: Optional[str] = None,
    kode_est: Optional[str] = None,
    kode_afd: Optional[str] = None,
    blok_id: Optional[str] = None
) -> dict:
    """
    Mengambil data history teragregasi untuk 3 tabel transaksi.
    - tahun DIISI -> Akumulasi Bulanan (Bulan 1-12) pada tahun tersebut.
    - tahun KOSONG -> Akumulasi Tahunan (Multi-Year).
    """
    # Validation Whitelist Table
    config = HISTORY_METRICS_CONFIG.get(table)
    if not config:
        raise HTTPException(
            status_code=400,
            detail=f"Tabel '{table}' tidak valid. Pilihan: {list(HISTORY_METRICS_CONFIG.keys())}"
        )

    # Menentukan Grouping berdasarkan periode
    is_monthly = tahun is not None
    group_by_clause = "t.bulan, t.tahun" if is_monthly else "t.tahun"
    select_time_clause = "t.tahun, t.bulan" if is_monthly else "t.tahun, NULL as bulan"
    order_by_clause = "t.tahun ASC, t.bulan ASC" if is_monthly else "t.tahun ASC"

    # Dynamic Joins & Where Clause
    joins = [
        f"JOIN blok b ON t.blok_id = b.blok_id AND t.bulan = b.bulan AND t.tahun = b.tahun",
        "JOIN afdeling af ON b.afd_id = af.afd_id AND b.bulan = af.bulan AND b.tahun = af.tahun",
        "JOIN estate e ON af.est_id = e.est_id AND af.bulan = e.bulan AND af.tahun = e.tahun",
        "JOIN perusahaan p ON e.pt_id = p.pt_id"
    ]

    where_conditions = []
    params = {}

    if tahun:
        where_conditions.append("t.tahun = :tahun")
        params["tahun"] = tahun

    if blok_id:
        where_conditions.append("b.blok_id = :blok_id")
        params["blok_id"] = blok_id
    elif kode_afd:
        where_conditions.append("af.kode_afd = :kode_afd")
        params["kode_afd"] = kode_afd
    elif kode_est:
        where_conditions.append("e.kode_est = :kode_est")
        params["kode_est"] = kode_est
    elif kode_pt:
        where_conditions.append("p.kode_pt = :kode_pt")
        params["kode_pt"] = kode_pt
    elif area_id:
        where_conditions.append("p.area_id = :area_id")
        params["area_id"] = area_id

    where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    join_clause = " ".join(joins)

    sql = f"""
        SELECT 
            {select_time_clause},
            {config['select']}
        FROM {table} t
        {join_clause}
        {where_clause}
        GROUP BY {group_by_clause}
        ORDER BY {order_by_clause}
    """

    rows = db.execute(text(sql), params).fetchall()

    return {
        "table": table,
        "label": config["label"],
        "mode_akumulasi": "BULANAN" if is_monthly else "TAHUNAN",
        "filter_applied": {
            "tahun": tahun,
            "area_id": area_id,
            "kode_pt": kode_pt,
            "kode_est": kode_est,
            "kode_afd": kode_afd,
            "blok_id": blok_id
        },
        "total_periode": len(rows),
        "data": [dict(r._mapping) for r in rows]
    }


def list_history_tables() -> list:
    """Untuk FE menampilkan pilihan tabel/tema yang tersedia di dropdown, dsb."""
    return [{"table": k, "label": v["label"]} for k, v in HISTORY_TABLE_REGISTRY.items()]


# =====================================================================
# DETAIL BLOK UNTUK POPUP (1 blok, 1 periode, semua tabel sekaligus)
# =====================================================================

def _resolve_blok_period(db: Session, blok_id: str, bulan: Optional[int], tahun: Optional[int]) -> tuple:
    if bulan is not None and tahun is not None:
        return bulan, tahun
    row = db.execute(
        text("SELECT bulan, tahun FROM blok WHERE blok_id = :bid ORDER BY tahun DESC, bulan DESC LIMIT 1"),
        {"bid": blok_id},
    ).fetchone()
    if not row:
        return None, None
    return (bulan if bulan is not None else row.bulan), (tahun if tahun is not None else row.tahun)


def get_blok_detail(db: Session, blok_id: str, bulan: Optional[int] = None, tahun: Optional[int] = None) -> dict:
    """
    Mengambil data popup lengkap saat Polygon Blok diklik pada Peta.
    Mendukung recalculation KPI (SPH, BJR, Kg/pkk, Jjg/pkk, GAP, Kategori Yield) s/d Bulan ini (sdBi).
    """
    # Resolve periode jika dikosongi di popup
    if bulan is None or tahun is None:
        period_row = db.execute(
            text("SELECT bulan, tahun FROM blok WHERE blok_id = :bid ORDER BY tahun DESC, bulan DESC LIMIT 1"),
            {"bid": blok_id}
        ).fetchone()
        if not period_row:
            raise HTTPException(status_code=404, detail=f"Blok ID '{blok_id}' tidak ditemukan.")
        bulan = bulan if bulan is not None else period_row.bulan
        tahun = tahun if tahun is not None else period_row.tahun

    # Kueri gabungan Master + Hierarki + Areal Statement + Produksi TBS (s/d Bulan ini)
    sql = """
        SELECT 
            -- Hierarki & Master Blok
            b.blok_id, b.nama_blok, b.kode_blok, b.tahun_tanam, b.jenis_bibit, b.status_tanam,
            af.kode_afd, e.nama_estate, e.kode_est, p.nama_pt, p.kode_pt, ar.nama AS nama_area,
            b.bulan, b.tahun,
            
            -- Areal Statement
            COALESCE(ast.luas_tanam, 0) AS luas,
            COALESCE(ast.total_pokok, 0) AS pokok,
            CASE 
                WHEN COALESCE(ast.luas_tanam, 0) > 0 THEN ROUND((COALESCE(ast.total_pokok, 0) / ast.luas_tanam)::numeric, 2)
                ELSE 0 
            END AS sph,
            
            -- Produksi TBS (s/d Bulan ini / Cumulative to Date)
            COALESCE(prod.tbs_aktual, 0) AS act_sdbi,
            COALESCE(prod.tbs_budget, 0) AS bgt_sdbi,
            (COALESCE(prod.tbs_aktual, 0) - COALESCE(prod.tbs_budget, 0)) AS gap_sdbi,
            COALESCE(prod.janjang_aktual, 0) AS janjang_aktual,
            COALESCE(prod.bjr_aktual, 0) AS bjr_sdbi,
            
            -- KPI Kalkulasi Per Pokok
            CASE 
                WHEN COALESCE(ast.total_pokok, 0) > 0 THEN ROUND((COALESCE(prod.tbs_aktual, 0) / ast.total_pokok)::numeric, 2)
                ELSE 0 
            END AS kg_pkk_sdbi,
            
            CASE 
                WHEN COALESCE(ast.total_pokok, 0) > 0 THEN ROUND((COALESCE(prod.janjang_aktual, 0) / ast.total_pokok)::numeric, 2)
                ELSE 0 
            END AS jjg_pkk_sdbi
            
        FROM blok b
        JOIN afdeling af ON b.afd_id = af.afd_id AND b.bulan = af.bulan AND b.tahun = af.tahun
        JOIN estate e ON af.est_id = e.est_id AND af.bulan = e.bulan AND af.tahun = e.tahun
        JOIN perusahaan p ON e.pt_id = p.pt_id
        LEFT JOIN area ar ON p.area_id = ar.area_id
        LEFT JOIN trx_areal_statement ast ON b.blok_id = ast.blok_id AND b.bulan = ast.bulan AND b.tahun = ast.tahun
        LEFT JOIN trx_produksi_tbs prod ON b.blok_id = prod.blok_id AND b.bulan = prod.bulan AND b.tahun = prod.tahun
        WHERE b.blok_id = :bid AND b.bulan = :b AND b.tahun = :t
    """
    
    row = db.execute(text(sql), {"bid": blok_id, "b": bulan, "t": tahun}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Detail data untuk blok '{blok_id}' periode {bulan}-{tahun} tidak ditemukan.")

    data = dict(row._mapping)
    
    # Penentuan Dynamic Kategori Yield berdasarkan pencapaian % ACT vs BGT
    act = data["act_sdbi"]
    bgt = data["bgt_sdbi"]
    if bgt > 0:
        pct = (act / bgt) * 100
        if pct >= 100:
            kategori_yield = "HIGH YIELD"
        elif pct >= 85:
            kategori_yield = "MEDIUM YIELD"
        else:
            kategori_yield = "LOW YIELD"
    else:
        kategori_yield = "NO TARGET"

    data["kategori_yield"] = kategori_yield
    return data


# =====================================================================
# RINGKASAN TRX UNTUK EMBED DI /geojson (dipakai spatial_refactored.py)
# =====================================================================

def fetch_trx_summary_by_blok(db: Session, blok_ids: list, bulan: Optional[int], tahun: Optional[int]) -> dict:
    """
    Ambil ringkasan trx_areal_statement + trx_produksi_tbs + rotasi TERAKHIR
    untuk SEKUMPULAN blok_id sekaligus (masing-masing 1 query, bukan per
    blok) -- supaya /geojson tetap cepat walau jumlah blok yang tampil di
    peta ratusan/ribuan.

    Sengaja hanya kolom ringkas yang diambil (bukan semua kolom trx) supaya
    payload GeoJSON tetap ramping untuk rendering peta; info lengkap ada di
    `get_blok_detail` yang dipanggil terpisah saat blok diklik.
    """
    if not blok_ids or bulan is None or tahun is None:
        return {}

    summary = {bid: {} for bid in blok_ids}

    areal_rows = db.execute(
        text("""
            SELECT blok_id, luas_tanam, luas_tanah, total_pokok, sph
            FROM trx_areal_statement
            WHERE blok_id = ANY(:blok_ids) AND bulan = :b AND tahun = :t
        """),
        {"blok_ids": blok_ids, "b": bulan, "t": tahun},
    ).fetchall()
    for r in areal_rows:
        summary[r.blok_id]["areal_statement"] = {
            "luas_tanam": r.luas_tanam, "luas_tanah": r.luas_tanah,
            "total_pokok": r.total_pokok, "sph": r.sph,
        }

    produksi_rows = db.execute(
        text("""
            SELECT blok_id, tbs_aktual, tbs_budget, janjang_aktual, bjr_aktual
            FROM trx_produksi_tbs
            WHERE blok_id = ANY(:blok_ids) AND bulan = :b AND tahun = :t
        """),
        {"blok_ids": blok_ids, "b": bulan, "t": tahun},
    ).fetchall()
    for r in produksi_rows:
        summary[r.blok_id]["produksi_tbs"] = {
            "tbs_aktual": r.tbs_aktual, "tbs_budget": r.tbs_budget,
            "janjang_aktual": r.janjang_aktual, "bjr_aktual": r.bjr_aktual,
        }

    # DISTINCT ON (Postgres) -- ambil 1 baris rotasi TERAKHIR (tanggal
    # terbesar) per blok_id, bukan semua riwayat (itu tugas get_blok_detail).
    rotasi_rows = db.execute(
        text("""
            SELECT DISTINCT ON (blok_id) blok_id, rotasi_ke, status_pusingan, tanggal
            FROM trx_rotasi_pusingan
            WHERE blok_id = ANY(:blok_ids) AND bulan = :b AND tahun = :t
            ORDER BY blok_id, tanggal DESC
        """),
        {"blok_ids": blok_ids, "b": bulan, "t": tahun},
    ).fetchall()
    for r in rotasi_rows:
        summary[r.blok_id]["rotasi_terakhir"] = {
            "rotasi_ke": r.rotasi_ke, "status_pusingan": r.status_pusingan,
            "tanggal": r.tanggal.isoformat() if r.tanggal else None,
        }

    return summary