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
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


def _json_safe(value: Any):
    """Konversi nilai DB (Decimal, dll) agar aman untuk json.dumps."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value

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


def list_history_tables() -> list:
    """Daftar tabel/tema yang boleh dipakai di GET /history (untuk dropdown FE)."""
    return [
        {"table": table, "label": config["label"]}
        for table, config in HISTORY_TABLE_REGISTRY.items()
    ]


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

def get_history_aggregated(
    db: Session,
    table: str = "trx_produksi_tbs",
    tahun: Optional[int] = None,
    area_id: Optional[str] = None,
    kode_pt: Optional[str] = None,
    kode_est: Optional[str] = None,
    kode_afd: Optional[str] = None,
    blok_id: Optional[str] = None,
    ownership: Optional[str] = None,
    group_by_fields: Optional[list] = None
) -> dict:
    """
    Endpoint History Agregasi Dinamis:
    - Jika table == 'trx_produksi_tbs' -> Mengembalikan format khusus UI (Slope + Luas, Ton, Ton/Ha, BJR, JJG/PKK, KG/PKK).
    - Jika table == 'trx_rotasi_pusingan' -> Mengembalikan format agregasi standar rotasi.
    - Jika table == 'trx_areal_statement' -> Memfilter berdasarkan `tahun_tanam` & `ownership`, dengan grouping Level 1 berdasarkan `tahun`.
    """
    valid_tables = ["trx_produksi_tbs", "trx_areal_statement", "trx_rotasi_pusingan"]
    if table not in valid_tables:
        raise HTTPException(
            status_code=400,
            detail=f"Tabel '{table}' tidak valid. Pilihan yang tersedia: {valid_tables}"
        )

    ownership_clean = ownership.strip() if ownership else None

    # Helper untuk format aman
    def safe_float(val, default=0.0):
        return float(val) if val is not None else default

    def safe_int(val, default=0):
        return int(val) if val is not None else default

    # Dynamic Joins & Where Clauses Dasar
    joins = [
        "JOIN blok b ON t.blok_id = b.blok_id AND t.bulan = b.bulan AND t.tahun = b.tahun",
        "JOIN afdeling af ON b.afd_id = af.afd_id AND b.bulan = af.bulan AND b.tahun = af.tahun",
        "JOIN estate e ON af.est_id = e.est_id AND af.bulan = e.bulan AND af.tahun = e.tahun",
        "JOIN perusahaan p ON e.pt_id = p.pt_id"
    ]

    where_conditions = []
    params = {}

    if blok_id:
        where_conditions.append("(b.blok_id = :blok_id OR b.kode_blok = :blok_id)")
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

    filter_info = {
        "tahun_tanam": tahun if table == "trx_areal_statement" else None,
        "tahun": tahun if table != "trx_areal_statement" else None,
        "area_id": area_id,
        "kode_pt": kode_pt,
        "kode_est": kode_est,
        "kode_afd": kode_afd,
        "blok_id": blok_id,
        "ownership": ownership_clean if table == "trx_areal_statement" else None,
    }

    # =========================================================================
    # CABANG 1: TABEL PRODUKSI TBS
    # =========================================================================
    if table == "trx_produksi_tbs":
        is_monthly = tahun is not None
        if tahun:
            where_conditions.append("t.tahun = :tahun")
            params["tahun"] = tahun

        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        join_clause = " ".join(joins)
        group_by_clause = "t.bulan, t.tahun" if is_monthly else "t.tahun"
        select_time_clause = "t.tahun, t.bulan" if is_monthly else "t.tahun, NULL as bulan"
        order_by_clause = "t.tahun ASC, t.bulan ASC" if is_monthly else "t.tahun ASC"

        # 1. Kueri Slope
        ast_joins = [
            "JOIN blok b ON ast.blok_id = b.blok_id AND ast.bulan = b.bulan AND ast.tahun = b.tahun",
            "JOIN afdeling af ON b.afd_id = af.afd_id AND b.bulan = af.bulan AND b.tahun = af.tahun",
            "JOIN estate e ON af.est_id = e.est_id AND af.bulan = e.bulan AND af.tahun = e.tahun",
            "JOIN perusahaan p ON e.pt_id = p.pt_id"
        ]
        ast_where_conditions = [c.replace("t.", "ast.") for c in where_conditions]
        ast_where_clause = " WHERE " + " AND ".join(ast_where_conditions) if ast_where_conditions else ""

        sql_slope = f"""
            SELECT 
                ROUND(SUM(COALESCE(ast.luas_tanam, 0) * COALESCE(ast.pct_tanah_datar, 0) / 100)::numeric, 2) AS slope_0_3,
                ROUND(SUM(COALESCE(ast.luas_tanam, 0) * COALESCE(ast.pct_gelombang, 0) / 100)::numeric, 2) AS slope_3_8,
                ROUND(SUM(COALESCE(ast.luas_tanam, 0) * COALESCE(ast.pct_berbukit, 0) / 100)::numeric, 2) AS slope_8_15,
                ROUND(SUM(COALESCE(ast.luas_tanam, 0) * COALESCE(ast.pct_curam, 0) / 100)::numeric, 2) AS slope_15_25,
                0.00 AS slope_gt_25
            FROM trx_areal_statement ast
            {" ".join(ast_joins)}
            {ast_where_clause}
        """
        slope_row = db.execute(text(sql_slope), params).fetchone()
        slope_data = dict(slope_row._mapping) if slope_row else {
            "slope_0_3": 0, "slope_3_8": 0, "slope_8_15": 0, "slope_15_25": 0, "slope_gt_25": 0
        }

        # 2. Kueri Histori Produksi
        sql_history = f"""
            SELECT 
                {select_time_clause},
                ROUND(AVG(COALESCE(ast.luas_tanam, 0))::numeric, 2) AS luas,
                ROUND((SUM(COALESCE(t.tbs_aktual, 0)) / 1000.0)::numeric, 2) AS ton,
                CASE 
                    WHEN AVG(COALESCE(ast.luas_tanam, 0)) > 0 
                    THEN ROUND(((SUM(COALESCE(t.tbs_aktual, 0)) / 1000.0) / AVG(ast.luas_tanam))::numeric, 2)
                    ELSE 0 
                END AS ton_ha,
                ROUND(AVG(COALESCE(t.bjr_aktual, 0))::numeric, 2) AS bjr,
                CASE 
                    WHEN SUM(COALESCE(ast.total_pokok, 0)) > 0 
                    THEN ROUND((SUM(COALESCE(t.janjang_aktual, 0)) / SUM(ast.total_pokok))::numeric, 2)
                    ELSE NULL 
                END AS jjg_ppk,
                CASE 
                    WHEN SUM(COALESCE(ast.total_pokok, 0)) > 0 
                    THEN ROUND((SUM(COALESCE(t.tbs_aktual, 0)) / SUM(ast.total_pokok))::numeric, 0)
                    ELSE NULL 
                END AS kg_ppk
            FROM trx_produksi_tbs t
            {join_clause}
            LEFT JOIN trx_areal_statement ast ON t.blok_id = ast.blok_id AND t.bulan = ast.bulan AND t.tahun = ast.tahun
            {where_clause}
            GROUP BY {group_by_clause}
            ORDER BY {order_by_clause}
        """
        rows = db.execute(text(sql_history), params).fetchall()

        return {
            "table": table,
            "label": "Produksi TBS (Histori & Slope)",
            "mode_akumulasi": "BULANAN" if is_monthly else "TAHUNAN",
            "filter_applied": filter_info,
            "slope_kemiringan_lereng": {
                "0-3%": f"{slope_data['slope_0_3']:,} ha".replace(",", "."),
                "3-8%": f"{slope_data['slope_3_8']:,} ha".replace(",", "."),
                "8-15%": f"{slope_data['slope_8_15']:,} ha".replace(",", "."),
                "15-25%": f"{slope_data['slope_15_25']:,} ha".replace(",", "."),
                ">25%": f"{slope_data['slope_gt_25']:,} ha".replace(",", ".")
            },
            "total_periode": len(rows),
            "data_histori": [
                {
                    "periode": r.bulan if is_monthly else r.tahun,
                    "tahun": r.tahun,
                    "bulan": r.bulan,
                    "luas": float(r.luas or 0),
                    "ton": float(r.ton or 0),
                    "ton_ha": float(r.ton_ha or 0),
                    "bjr": float(r.bjr or 0),
                    "jjg_ppk": float(r.jjg_ppk) if r.jjg_ppk is not None else None,
                    "kg_ppk": int(r.kg_ppk) if r.kg_ppk is not None else None
                }
                for r in rows
            ]
        }

    # =========================================================================
    # CABANG 2: TABEL ROTASI PUSINGAN
    # =========================================================================
    elif table == "trx_rotasi_pusingan":
        is_monthly = tahun is not None
        if tahun:
            where_conditions.append("t.tahun = :tahun")
            params["tahun"] = tahun

        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        join_clause = " ".join(joins)
        group_by_clause = "t.bulan, t.tahun" if is_monthly else "t.tahun"
        select_time_clause = "t.tahun, t.bulan" if is_monthly else "t.tahun, NULL as bulan"
        order_by_clause = "t.tahun ASC, t.bulan ASC" if is_monthly else "t.tahun ASC"

        sql = f"""
            SELECT 
                {select_time_clause},
                COUNT(t.id_rotasi_pusingan) AS total_rotasi,
                MAX(t.rotasi_ke) AS rotasi_terakhir,
                AVG(COALESCE(t.pusingan_hari, 0)) AS avg_pusingan_hari,
                SUM(COALESCE(t.luas, 0)) AS total_luas_rotasi,
                SUM(COALESCE(t.pokok, 0)) AS total_pokok_rotasi
            FROM trx_rotasi_pusingan t
            {join_clause}
            {where_clause}
            GROUP BY {group_by_clause}
            ORDER BY {order_by_clause}
        """
        rows = db.execute(text(sql), params).fetchall()
        return {
            "table": table,
            "label": "Rotasi Pusingan",
            "mode_akumulasi": "BULANAN" if is_monthly else "TAHUNAN",
            "filter_applied": filter_info,
            "total_periode": len(rows),
            "data": [dict(r._mapping) for r in rows]
        }

    # =========================================================================
    # CABANG 3: TABEL AREAL STATEMENT (GROUPING TAHUN & FILTER TAHUN TANAM)
    # =========================================================================
    elif table == "trx_areal_statement":
        areal_joins = [
            "LEFT JOIN blok b ON t.blok_id = b.blok_id AND t.tahun = b.tahun",
            "LEFT JOIN afdeling af ON b.afd_id = af.afd_id AND b.tahun = af.tahun",
            "LEFT JOIN estate e ON af.est_id = e.est_id AND af.tahun = e.tahun",
            "LEFT JOIN perusahaan p ON e.pt_id = p.pt_id"
        ]
        areal_join_clause = " ".join(areal_joins)

        # Filter Ownership Khusus trx_areal_statement
        areal_where_conditions = list(where_conditions)
        if ownership_clean:
            areal_where_conditions.append("(LOWER(TRIM(COALESCE(t.tipe_blok, b.tipe_blok))) = LOWER(TRIM(:ownership)))")
            params["ownership"] = ownership_clean

        # Grouping Level 1 Utama: TAHUN TRANSAKSI
        eff_tahun_expr = "COALESCE(t.tahun, b.tahun)"
        # TAHUN TANAM: Digunakan khusus sebagai Atribut/Filter
        eff_tahun_tanam_expr = "COALESCE(t.tahun_tanam, b.tahun_tanam)"

        default_attributes = [
            "status_tanam",
            "bulan_tanam",
            "tahun_tanam",
            "jenis_bibit",
            "jenis_topografi",
            "jenis_tanah"
        ]

        attribute_groups = [
            col for col in (group_by_fields or default_attributes) 
            if col not in ["tahun", "bulan"]
        ]

        valid_group_columns = {
            "tahun": f"{eff_tahun_expr}",
            "tahun_tanam": f"{eff_tahun_tanam_expr}",
            "status_tanam": "COALESCE(t.status_tanam, b.status_tanam)",
            "bulan_tanam": "t.bulan_tanam",
            "jenis_bibit": "COALESCE(t.jenis_bibit, b.jenis_bibit)",
            "jenis_topografi": "COALESCE(t.jenis_topografi, b.jenis_topografi)",
            "jenis_tanah": "COALESCE(t.jenis_tanah, b.jenis_tanah)",
            "tipe_blok": "COALESCE(t.tipe_blok, b.tipe_blok)"
        }

        # Susun kolom SELECT & GROUP BY dengan `tahun` sebagai kunci utama
        select_group_cols = [f"{valid_group_columns['tahun']} AS tahun"]
        group_by_cols = [valid_group_columns['tahun']]

        for col in attribute_groups:
            if col in valid_group_columns:
                select_group_cols.append(f"{valid_group_columns[col]} AS {col}")
                group_by_cols.append(valid_group_columns[col])

        select_group_sql = ", ".join(select_group_cols)
        group_by_sql = ", ".join(group_by_cols)

        # Pemfilteran berdasarkan `tahun_tanam`
        if tahun:
            areal_where_conditions.append(f"{eff_tahun_tanam_expr} = :tahun_tanam")
            params["tahun_tanam"] = tahun
            filter_info["tahun_tanam"] = tahun
        else:
            # Mengambil 5 Tahun Tanam Terakhir sebagai filter
            sql_max_tt = f"""
                SELECT MAX({eff_tahun_tanam_expr}) AS max_tt 
                FROM trx_areal_statement t 
                {areal_join_clause}
                {" WHERE " + " AND ".join(areal_where_conditions) if areal_where_conditions else ""}
            """
            max_tt_res = db.execute(text(sql_max_tt), params).fetchone()
            latest_tt = max_tt_res.max_tt if max_tt_res and max_tt_res.max_tt else 2025

            start_tt = latest_tt - 4
            areal_where_conditions.append(f"{eff_tahun_tanam_expr} BETWEEN :start_tt AND :end_tt")
            params["start_tt"] = start_tt
            params["end_tt"] = latest_tt
            filter_info["tahun_tanam"] = f"{start_tt} - {latest_tt} (5 Tahun Tanam Terakhir)"

        areal_where_clause = " WHERE " + " AND ".join(areal_where_conditions) if areal_where_conditions else ""

        # 1. Grand Total Query
        sql_gt = f"""
            SELECT 
                COUNT(t.id) AS total_records,
                ROUND(SUM(COALESCE(t.luas_tanam, 0))::numeric, 2) AS luas_tanam,
                ROUND(SUM(COALESCE(t.luas_tanah, 0))::numeric, 2) AS luas_tanah,
                SUM(COALESCE(t.total_pokok, 0)) AS total_pokok,
                CASE 
                    WHEN SUM(COALESCE(t.luas_tanam, 0)) > 0 
                    THEN ROUND((SUM(COALESCE(t.total_pokok, 0)) / SUM(t.luas_tanam))::numeric, 2)
                    ELSE 0.0 
                END AS sph,
                ROUND(AVG(COALESCE(t.pct_tanah_datar, 0))::numeric, 2) AS pct_tanah_datar,
                ROUND(AVG(COALESCE(t.pct_berbukit, 0))::numeric, 2) AS pct_berbukit,
                ROUND(AVG(COALESCE(t.pct_gelombang, 0))::numeric, 2) AS pct_gelombang,
                ROUND(AVG(COALESCE(t.pct_curam, 0))::numeric, 2) AS pct_curam
            FROM trx_areal_statement t
            {areal_join_clause}
            {areal_where_clause}
        """
        gt_row = db.execute(text(sql_gt), params).fetchone()
        gt_data = dict(gt_row._mapping) if gt_row else {}

        # 2. Query Groups Per TAHUN (Diurutkan berdasarkan Tahun Descending)
        sql_groups = f"""
            SELECT 
                {select_group_sql},
                COUNT(t.id) AS count_records,
                ROUND(SUM(COALESCE(t.luas_tanam, 0))::numeric, 2) AS luas_tanam,
                ROUND(SUM(COALESCE(t.luas_tanah, 0))::numeric, 2) AS luas_tanah,
                SUM(COALESCE(t.total_pokok, 0)) AS total_pokok,
                CASE 
                    WHEN SUM(COALESCE(t.luas_tanam, 0)) > 0 
                    THEN ROUND((SUM(COALESCE(t.total_pokok, 0)) / SUM(t.luas_tanam))::numeric, 2)
                    ELSE 0.0 
                END AS sph,
                ROUND(AVG(COALESCE(t.pct_tanah_datar, 0))::numeric, 2) AS pct_tanah_datar,
                ROUND(AVG(COALESCE(t.pct_berbukit, 0))::numeric, 2) AS pct_berbukit,
                ROUND(AVG(COALESCE(t.pct_gelombang, 0))::numeric, 2) AS pct_gelombang,
                ROUND(AVG(COALESCE(t.pct_curam, 0))::numeric, 2) AS pct_curam
            FROM trx_areal_statement t
            {areal_join_clause}
            {areal_where_clause}
            GROUP BY {group_by_sql}
            ORDER BY {eff_tahun_expr} DESC
        """
        group_rows = db.execute(text(sql_groups), params).fetchall()

        month_names = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
        }

        # 3. Restrukturisasi JSON Bersarang Berdasarkan TAHUN
        nested_data = defaultdict(list)
        for r in group_rows:
            row_dict = dict(r._mapping)
            th_key = row_dict.get("tahun")

            sub_keys = {
                "status_tanam": row_dict.get("status_tanam"),
                "bulan_tanam": month_names.get(row_dict.get("bulan_tanam"), row_dict.get("bulan_tanam")) if isinstance(row_dict.get("bulan_tanam"), int) else row_dict.get("bulan_tanam"),
                "tahun_tanam": row_dict.get("tahun_tanam"),
                "jenis_bibit": row_dict.get("jenis_bibit"),
                "jenis_topografi": row_dict.get("jenis_topografi"),
                "jenis_tanah": row_dict.get("jenis_tanah")
            }

            group_item = {
                "group_keys": sub_keys,
                "totals": {
                    "count_records": safe_int(row_dict.get("count_records")),
                    "luas_tanam": safe_float(row_dict.get("luas_tanam")),
                    "luas_tanah": safe_float(row_dict.get("luas_tanah")),
                    "total_pokok": safe_int(row_dict.get("total_pokok")),
                    "sph": safe_float(row_dict.get("sph")),
                    "pct_tanah_datar": safe_float(row_dict.get("pct_tanah_datar")),
                    "pct_berbukit": safe_float(row_dict.get("pct_berbukit")),
                    "pct_gelombang": safe_float(row_dict.get("pct_gelombang")),
                    "pct_curam": safe_float(row_dict.get("pct_curam"))
                }
            }

            nested_data[th_key].append(group_item)

        structured_groups = [
            {
                "tahun": th_key,
                "groups": items
            }
            for th_key, items in nested_data.items()
        ]

        return {
            "status": "success",
            "message": "Data Areal Statement berhasil dimuat",
            "meta": {
                "table": "trx_areal_statement",
                "label": "Areal Statement",
                "mode_akumulasi": "SPESIFIK TAHUN TANAM" if tahun else "AKUMULASI TAHUN TANAM (5 Tahun Tanam Terakhir)",
                "grouped_by_level_1": "tahun",
                "filter_applied": filter_info,
                "group_by_attributes": default_attributes,
                "total_records": safe_int(gt_data.get("total_records"))
            },
            "grand_total": {
                "luas_tanam": safe_float(gt_data.get("luas_tanam")),
                "luas_tanah": safe_float(gt_data.get("luas_tanah")),
                "total_pokok": safe_int(gt_data.get("total_pokok")),
                "sph": safe_float(gt_data.get("sph")),
                "pct_tanah_datar": safe_float(gt_data.get("pct_tanah_datar")),
                "pct_berbukit": safe_float(gt_data.get("pct_berbukit")),
                "pct_gelombang": safe_float(gt_data.get("pct_gelombang")),
                "pct_curam": safe_float(gt_data.get("pct_curam"))
            },
            "data": structured_groups
        }

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


# =====================================================================
# DETAIL BLOK UNTUK POPUP (1 blok, filter berdasarkan tahun tanam)
# =====================================================================

def get_blok_detail(
    db: Session, 
    blok_id: str, 
    tahun_tanam: Optional[int] = None,
    ownership: Optional[str] = None  # Parameter Baru: "Inti" atau "Plasma"
) -> dict:
    """
    Mengambil data popup lengkap saat Polygon Blok diklik pada Peta:
    - Filter berdasarkan tahun_tanam & ownership (tipe_blok: 'Inti' / 'Plasma').
    - Jika tahun_tanam KOSONG: Otomatis mengambil data tahun_tanam TERBARU (latest).
    - Format areal_statement disesuaikan dengan struktur get_history_aggregated.
    """
    def safe_float(val, default=0.0):
        return float(val) if val is not None else default

    def safe_int(val, default=0):
        return int(val) if val is not None else default

    # Clean ownership parameter jika dikirim
    ownership_clean = ownership.strip() if ownership else None

    # 1. Tentukan tahun_tanam jika dikosongi (ambil yang terbaru / LATEST)
    is_latest_fallback = tahun_tanam is None
    if is_latest_fallback:
        sql_latest_tt = """
            SELECT tahun_tanam 
            FROM blok 
            WHERE blok_id = :bid AND tahun_tanam IS NOT NULL 
        """
        tt_params = {"bid": blok_id}
        if ownership_clean:
            sql_latest_tt += " AND LOWER(tipe_blok) = LOWER(:ownership)"
            tt_params["ownership"] = ownership_clean

        sql_latest_tt += " ORDER BY tahun_tanam DESC LIMIT 1"
        res_tt = db.execute(text(sql_latest_tt), tt_params).fetchone()
        
        if not res_tt or res_tt.tahun_tanam is None:
            sql_latest_tt_ast = """
                SELECT tahun_tanam 
                FROM trx_areal_statement 
                WHERE blok_id = :bid AND tahun_tanam IS NOT NULL 
            """
            if ownership_clean:
                sql_latest_tt_ast += " AND LOWER(tipe_blok) = LOWER(:ownership)"
            
            sql_latest_tt_ast += " ORDER BY tahun_tanam DESC LIMIT 1"
            res_tt = db.execute(text(sql_latest_tt_ast), tt_params).fetchone()

        if res_tt and res_tt.tahun_tanam:
            tahun_tanam = res_tt.tahun_tanam

    # Parameter SQL dasar untuk query selanjutnya
    trx_params = {"bid": blok_id}
    if tahun_tanam is not None:
        trx_params["tt"] = tahun_tanam
    if ownership_clean:
        trx_params["ownership"] = ownership_clean

    # 2. Ambil Data Master Blok & Hierarki
    where_master = ["b.blok_id = :bid"]

    if tahun_tanam is not None:
        where_master.append("b.tahun_tanam = :tt")
    if ownership_clean:
        where_master.append("LOWER(b.tipe_blok) = LOWER(:ownership)")

    sql_master = f"""
        SELECT 
            b.blok_id, b.nama_blok, b.kode_blok, b.tahun_tanam, b.tipe_blok,
            b.jenis_bibit, b.status_tanam, b.jenis_topografi, b.jenis_tanah,
            af.kode_afd, af.kode_afd AS nama_afd,
            e.kode_est, e.nama_estate,
            p.kode_pt, p.nama_pt,
            ar.area_id, ar.nama AS nama_area
        FROM blok b
        LEFT JOIN afdeling af ON b.afd_id = af.afd_id AND b.tahun = af.tahun
        LEFT JOIN estate e ON af.est_id = e.est_id AND af.tahun = e.tahun
        LEFT JOIN perusahaan p ON e.pt_id = p.pt_id
        LEFT JOIN area ar ON p.area_id = ar.area_id
        WHERE {" AND ".join(where_master)}
        ORDER BY b.tahun DESC, b.bulan DESC
        LIMIT 1
    """
    master_row = db.execute(text(sql_master), trx_params).fetchone()
    
    # Fallback ke master blok jika tidak ditemukan dengan kombinasi filter ketat
    if not master_row:
        master_row = db.execute(
            text("""
                SELECT 
                    b.blok_id, b.nama_blok, b.kode_blok, b.tahun_tanam, b.tipe_blok,
                    b.jenis_bibit, b.status_tanam, b.jenis_topografi, b.jenis_tanah,
                    af.kode_afd, af.kode_afd AS nama_afd,
                    e.kode_est, e.nama_estate,
                    p.kode_pt, p.nama_pt,
                    ar.area_id, ar.nama AS nama_area
                FROM blok b
                LEFT JOIN afdeling af ON b.afd_id = af.afd_id AND b.tahun = af.tahun
                LEFT JOIN estate e ON af.est_id = e.est_id AND af.tahun = e.tahun
                LEFT JOIN perusahaan p ON e.pt_id = p.pt_id
                LEFT JOIN area ar ON p.area_id = ar.area_id
                WHERE b.blok_id = :bid
                ORDER BY b.tahun DESC, b.bulan DESC
                LIMIT 1
            """),
            {"bid": blok_id}
        ).fetchone()

    if not master_row:
        raise HTTPException(status_code=404, detail=f"Blok ID '{blok_id}' tidak ditemukan di sistem.")

    master_data = dict(master_row._mapping)

    # 3. Query Detailed TRX Areal Statement untuk Aggregation (Filter ownership / tipe_blok)
    ast_where = ["ast.blok_id = :bid"]
    if tahun_tanam is not None:
        ast_where.append("ast.tahun_tanam = :tt")
    if ownership_clean:
        ast_where.append("LOWER(ast.tipe_blok) = LOWER(:ownership)")

    sql_ast_detail = f"""
        SELECT 
            ast.tahun,
            COALESCE(ast.status_tanam, b.status_tanam) AS status_tanam,
            ast.bulan_tanam,
            ast.tahun_tanam,
            COALESCE(ast.tipe_blok, b.tipe_blok) AS tipe_blok,
            COALESCE(ast.jenis_bibit, b.jenis_bibit) AS jenis_bibit,
            COALESCE(ast.jenis_topografi, b.jenis_topografi) AS jenis_topografi,
            COALESCE(ast.jenis_tanah, b.jenis_tanah) AS jenis_tanah,
            COALESCE(ast.luas_tanam, 0) AS luas_tanam,
            COALESCE(ast.luas_tanah, 0) AS luas_tanah,
            COALESCE(ast.total_pokok, 0) AS total_pokok,
            COALESCE(ast.pct_tanah_datar, 0) AS pct_tanah_datar,
            COALESCE(ast.pct_berbukit, 0) AS pct_berbukit,
            COALESCE(ast.pct_gelombang, 0) AS pct_gelombang,
            COALESCE(ast.pct_curam, 0) AS pct_curam
        FROM trx_areal_statement ast
        LEFT JOIN blok b ON ast.blok_id = b.blok_id AND ast.tahun = b.tahun AND ast.bulan = b.bulan
        WHERE {" AND ".join(ast_where)}
        ORDER BY ast.tahun DESC
    """
    ast_rows = db.execute(text(sql_ast_detail), trx_params).fetchall()

    # Membangun Struktur Aggregation Areal Statement
    total_records = len(ast_rows)
    
    gt_luas_tanam = 0.0
    gt_luas_tanah = 0.0
    gt_total_pokok = 0
    gt_pct_datar = 0.0
    gt_pct_bukit = 0.0
    gt_pct_gelombang = 0.0
    gt_pct_curam = 0.0

    grouped_tree = defaultdict(lambda: defaultdict(list))

    for r in ast_rows:
        row_dict = dict(r._mapping)
        th = row_dict["tahun"]
        
        gt_luas_tanam += safe_float(row_dict["luas_tanam"])
        gt_luas_tanah += safe_float(row_dict["luas_tanah"])
        gt_total_pokok += safe_int(row_dict["total_pokok"])
        gt_pct_datar += safe_float(row_dict["pct_tanah_datar"])
        gt_pct_bukit += safe_float(row_dict["pct_berbukit"])
        gt_pct_gelombang += safe_float(row_dict["pct_gelombang"])
        gt_pct_curam += safe_float(row_dict["pct_curam"])

        group_key = (
            row_dict.get("status_tanam"),
            row_dict.get("bulan_tanam"),
            row_dict.get("tahun_tanam"),
            row_dict.get("jenis_bibit"),
            row_dict.get("jenis_topografi"),
            row_dict.get("jenis_tanah")
        )
        grouped_tree[th][group_key].append(row_dict)

    if total_records > 0:
        grand_total = {
            "luas_tanam": round(gt_luas_tanam, 2),
            "luas_tanah": round(gt_luas_tanah, 2),
            "total_pokok": gt_total_pokok,
            "sph": round(gt_total_pokok / gt_luas_tanam, 2) if gt_luas_tanam > 0 else 0.0,
            "pct_tanah_datar": round(gt_pct_datar / total_records, 2),
            "pct_berbukit": round(gt_pct_bukit / total_records, 2),
            "pct_gelombang": round(gt_pct_gelombang / total_records, 2),
            "pct_curam": round(gt_pct_curam / total_records, 2)
        }
    else:
        grand_total = {
            "luas_tanam": 0.0,
            "luas_tanah": 0.0,
            "total_pokok": 0,
            "sph": 0.0,
            "pct_tanah_datar": 0.0,
            "pct_berbukit": 0.0,
            "pct_gelombang": 0.0,
            "pct_curam": 0.0
        }

    data_grouped_list = []
    for th in sorted(grouped_tree.keys(), reverse=True):
        groups_list = []
        for g_key, items in grouped_tree[th].items():
            st, bt, tt, jb, jt_topo, jt_tanah = g_key
            cnt = len(items)
            
            sum_lt = sum(safe_float(x["luas_tanam"]) for x in items)
            sum_ltanah = sum(safe_float(x["luas_tanah"]) for x in items)
            sum_tp = sum(safe_int(x["total_pokok"]) for x in items)
            
            avg_datar = sum(safe_float(x["pct_tanah_datar"]) for x in items) / cnt if cnt > 0 else 0.0
            avg_bukit = sum(safe_float(x["pct_berbukit"]) for x in items) / cnt if cnt > 0 else 0.0
            avg_gel = sum(safe_float(x["pct_gelombang"]) for x in items) / cnt if cnt > 0 else 0.0
            avg_curam = sum(safe_float(x["pct_curam"]) for x in items) / cnt if cnt > 0 else 0.0
            
            sph_calc = round(sum_tp / sum_lt, 2) if sum_lt > 0 else 0.0

            groups_list.append({
                "group_keys": {
                    "status_tanam": st,
                    "bulan_tanam": bt,
                    "tahun_tanam": tt,
                    "jenis_bibit": jb,
                    "jenis_topografi": jt_topo,
                    "jenis_tanah": jt_tanah
                },
                "totals": {
                    "count_records": cnt,
                    "luas_tanam": round(sum_lt, 2),
                    "luas_tanah": round(sum_ltanah, 2),
                    "total_pokok": sum_tp,
                    "sph": sph_calc,
                    "pct_tanah_datar": round(avg_datar, 2),
                    "pct_berbukit": round(avg_bukit, 2),
                    "pct_gelombang": round(avg_gel, 2),
                    "pct_curam": round(avg_curam, 2)
                }
            })
        
        data_grouped_list.append({
            "tahun": th,
            "groups": groups_list
        })

    areal_statement_response = {
        "group_by_attributes": [
            "status_tanam",
            "bulan_tanam",
            "tahun_tanam",
            "jenis_bibit",
            "jenis_topografi",
            "jenis_tanah"
        ],
        "total_records": total_records,
        "grand_total": grand_total,
        "data": data_grouped_list
    }

    # 4. Query Produksi TBS (JOIN ke trx_areal_statement untuk memfilter tahun_tanam & ownership)
    prod_where = ["p.blok_id = :bid"]
    prod_join = ""

    if tahun_tanam is not None or ownership_clean:
        prod_join = "JOIN trx_areal_statement ast ON p.blok_id = ast.blok_id AND p.bulan = ast.bulan AND p.tahun = ast.tahun"
        if tahun_tanam is not None:
            prod_where.append("ast.tahun_tanam = :tt")
        if ownership_clean:
            prod_where.append("LOWER(ast.tipe_blok) = LOWER(:ownership)")

    sql_prod = f"""
        SELECT 
            ROUND(SUM(COALESCE(p.tbs_aktual, 0))::numeric, 2) AS tbs_aktual,
            ROUND(SUM(COALESCE(p.tbs_budget, 0))::numeric, 2) AS tbs_budget,
            ROUND(SUM(COALESCE(p.tbs_sensus, 0))::numeric, 2) AS tbs_sensus,
            
            ROUND(SUM(COALESCE(p.janjang_aktual, 0)))::int AS janjang_aktual,
            ROUND(SUM(COALESCE(p.janjang_budget, 0)))::int AS janjang_budget,
            ROUND(SUM(COALESCE(p.janjang_sensus, 0)))::int AS janjang_sensus,
            
            ROUND(AVG(COALESCE(p.bjr_aktual, 0))::numeric, 2) AS bjr_aktual,
            ROUND(AVG(COALESCE(p.bjr_budget, 0))::numeric, 2) AS bjr_budget,
            ROUND(AVG(COALESCE(p.bjr_sensus, 0))::numeric, 2) AS bjr_sensus
        FROM trx_produksi_tbs p
        {prod_join}
        WHERE {" AND ".join(prod_where)}
    """
    prod_row = db.execute(text(sql_prod), trx_params).fetchone()
    prod_data = dict(prod_row._mapping) if prod_row else {}

    # Perhitungan KPI Produksi
    total_pokok_val = grand_total["total_pokok"]
    tbs_act = safe_float(prod_data.get("tbs_aktual"))
    tbs_bgt = safe_float(prod_data.get("tbs_budget"))
    jjg_act = safe_int(prod_data.get("janjang_aktual"))

    kg_pkk = round(tbs_act / total_pokok_val, 2) if total_pokok_val > 0 else 0.0
    jjg_pkk = round(jjg_act / total_pokok_val, 2) if total_pokok_val > 0 else 0.0
    gap_tbs = round(tbs_act - tbs_bgt, 2)

    if tbs_bgt > 0:
        pct_achievement = round((tbs_act / tbs_bgt) * 100, 2)
        if pct_achievement >= 100:
            kategori_yield = "HIGH YIELD"
        elif pct_achievement >= 85:
            kategori_yield = "MEDIUM YIELD"
        else:
            kategori_yield = "LOW YIELD"
    else:
        pct_achievement = 0.0
        kategori_yield = "NO TARGET"

    # 5. Query Riwayat Rotasi Pusingan (JOIN ke trx_areal_statement untuk memfilter tahun_tanam & ownership)
    rotasi_where = ["r.blok_id = :bid"]
    rotasi_join = ""

    if tahun_tanam is not None or ownership_clean:
        rotasi_join = "JOIN trx_areal_statement ast ON r.blok_id = ast.blok_id AND r.bulan = ast.bulan AND r.tahun = ast.tahun"
        if tahun_tanam is not None:
            rotasi_where.append("ast.tahun_tanam = :tt")
        if ownership_clean:
            rotasi_where.append("LOWER(ast.tipe_blok) = LOWER(:ownership)")

    sql_rotasi = f"""
        SELECT 
            r.id_rotasi_pusingan, r.tanggal, r.rotasi_ke, r.pusingan_hari, r.status_pusingan,
            COALESCE(r.luas, 0) AS luas, COALESCE(r.pokok, 0) AS pokok
        FROM trx_rotasi_pusingan r
        {rotasi_join}
        WHERE {" AND ".join(rotasi_where)}
        ORDER BY r.tanggal ASC, r.rotasi_ke ASC
    """
    rotasi_rows = db.execute(text(sql_rotasi), trx_params).fetchall()
    
    list_rotasi = [
        {
            "id_rotasi_pusingan": r.id_rotasi_pusingan,
            "tanggal": r.tanggal.isoformat() if r.tanggal else None,
            "rotasi_ke": r.rotasi_ke,
            "pusingan_hari": r.pusingan_hari,
            "status_pusingan": r.status_pusingan,
            "luas": safe_float(r.luas),
            "pokok": safe_int(r.pokok)
        }
        for r in rotasi_rows
    ]

    # 6. Response JSON Final
    effective_tahun_tanam = tahun_tanam if tahun_tanam is not None else master_data.get("tahun_tanam")
    effective_ownership = ownership_clean if ownership_clean else master_data.get("tipe_blok")
    periode_label = f"Tahun Tanam {effective_tahun_tanam}" if effective_tahun_tanam else "Semua Tahun Tanam"

    return {
        "status": "success",
        "message": f"Detail data blok {blok_id} periode {periode_label} berhasil dimuat.",
        "mode": "LATEST_TAHUN_TANAM" if is_latest_fallback else "SPESIFIK_TAHUN_TANAM",
        "periode": {
            "bulan": None,
            "tahun": effective_tahun_tanam,
            "label_periode": periode_label
        },
        "informasi_blok": {
            "blok_id": master_data["blok_id"],
            "nama_blok": master_data["nama_blok"],
            "kode_blok": master_data["kode_blok"],
            "tipe_blok": effective_ownership,
            "tahun_tanam": effective_tahun_tanam,
            "bulan_tanam": master_data.get("bulan_tanam"),
            "jenis_bibit": master_data["jenis_bibit"],
            "status_tanam": master_data["status_tanam"],
            "jenis_topografi": master_data["jenis_topografi"],
            "jenis_tanah": master_data["jenis_tanah"],
            "hierarki": {
                "nama_area": master_data["nama_area"],
                "kode_pt": master_data["kode_pt"],
                "nama_pt": master_data["nama_pt"],
                "kode_est": master_data["kode_est"],
                "nama_estate": master_data["nama_estate"],
                "kode_afd": master_data["kode_afd"],
                "nama_afd": master_data["nama_afd"]
            }
        },
        "areal_statement": areal_statement_response,
        "produksi_tbs": {
            "tbs": {
                "aktual": tbs_act,
                "budget": tbs_bgt,
                "sensus": safe_float(prod_data.get("tbs_sensus")),
                "gap": gap_tbs,
                "pct_achievement": pct_achievement,
                "kategori_yield": kategori_yield
            },
            "janjang": {
                "aktual": jjg_act,
                "budget": safe_int(prod_data.get("janjang_budget")),
                "sensus": safe_int(prod_data.get("janjang_sensus"))
            },
            "bjr": {
                "aktual": safe_float(prod_data.get("bjr_aktual")),
                "budget": safe_float(prod_data.get("bjr_budget")),
                "sensus": safe_float(prod_data.get("bjr_sensus"))
            },
            "kpi_per_pokok": {
                "kg_pkk": kg_pkk,
                "jjg_pkk": jjg_pkk
            }
        },
        "rotasi_pusingan": {
            "total_kegiatan": len(list_rotasi),
            "daftar_rotasi": list_rotasi
        }
    }

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
            "luas_tanam": _json_safe(r.luas_tanam),
            "luas_tanah": _json_safe(r.luas_tanah),
            "total_pokok": _json_safe(r.total_pokok),
            "sph": _json_safe(r.sph),
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
            "tbs_aktual": _json_safe(r.tbs_aktual),
            "tbs_budget": _json_safe(r.tbs_budget),
            "janjang_aktual": _json_safe(r.janjang_aktual),
            "bjr_aktual": _json_safe(r.bjr_aktual),
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