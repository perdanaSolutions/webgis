"""sync_schema_to_mermaid_relations

Revision ID: f0a1b2c3d4e5
Revises: 634b338fa358
Create Date: 2026-07-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.engine import Connection


# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "634b338fa358"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn: Connection, table_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        ).scalar()
    )


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                      AND column_name = :column_name
                )
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar()
    )


def _constraint_exists(conn: Connection, table_name: str, constraint_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                      AND constraint_name = :constraint_name
                )
                """
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        ).scalar()
    )


def _index_exists(conn: Connection, index_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE schemaname = 'public' AND indexname = :index_name
                )
                """
            ),
            {"index_name": index_name},
        ).scalar()
    )


def _create_index_if_not_exists(
    conn: Connection,
    index_name: str,
    table_name: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    if not _index_exists(conn, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _create_perusahaan_table(conn: Connection) -> None:
    if not _table_exists(conn, "perusahaan"):
        op.create_table(
            "perusahaan",
            sa.Column("pt_id", sa.Integer(), nullable=False),
            sa.Column("nama_pt", sa.String(length=150), nullable=False),
            sa.Column("kode_pt", sa.String(length=50), nullable=False),
            sa.PrimaryKeyConstraint("pt_id", name="pk_perusahaan"),
            sa.UniqueConstraint("kode_pt", name="uq_perusahaan_kode_pt"),
        )
    _create_index_if_not_exists(conn, "ix_perusahaan_pt_id", "perusahaan", ["pt_id"])
    _create_index_if_not_exists(conn, "ix_perusahaan_kode_pt", "perusahaan", ["kode_pt"], unique=True)


def _sync_perusahaan_from_pts(conn: Connection) -> None:
    if _table_exists(conn, "pts") and _table_exists(conn, "perusahaan"):
        conn.execute(
            sa.text(
                """
                INSERT INTO perusahaan (pt_id, nama_pt, kode_pt)
                SELECT p.id, p.nama_pt, p.kode_pt
                FROM pts p
                ON CONFLICT (pt_id) DO UPDATE
                  SET nama_pt = EXCLUDED.nama_pt,
                      kode_pt = EXCLUDED.kode_pt
                """
            )
        )


def _create_estate_table(conn: Connection) -> None:
    if not _table_exists(conn, "estate"):
        op.create_table(
            "estate",
            sa.Column("est_id", sa.String(length=50), nullable=False),
            sa.Column("pt_id", sa.Integer(), nullable=False),
            sa.Column("nama_estate", sa.String(length=100), nullable=False),
            sa.Column("kode_est", sa.String(length=50), nullable=False),
            sa.PrimaryKeyConstraint("est_id", name="pk_estate"),
            sa.ForeignKeyConstraint(["pt_id"], ["perusahaan.pt_id"], ondelete="CASCADE", name="fk_estate_perusahaan"),
            sa.UniqueConstraint("kode_est", name="uq_estate_kode_est"),
        )
    _create_index_if_not_exists(conn, "ix_estate_pt_id", "estate", ["pt_id"])


def _sync_estate_from_estates(conn: Connection) -> None:
    if _table_exists(conn, "estates") and _table_exists(conn, "estate"):
        if _column_exists(conn, "estates", "id") and _column_exists(conn, "estates", "area_id"):
            # Mapping lewat areas.pt_id -> perusahaan.pt_id
            conn.execute(
                sa.text(
                    """
                    INSERT INTO estate (est_id, pt_id, nama_estate, kode_est)
                    SELECT
                        e.id::text AS est_id,
                        COALESCE(a.pt_id, 0) AS pt_id,
                        e.nama_estate,
                        e.kode_est
                    FROM estates e
                    LEFT JOIN areas a ON a.id = e.area_id
                    WHERE a.pt_id IS NOT NULL
                    ON CONFLICT (est_id) DO UPDATE
                      SET pt_id = EXCLUDED.pt_id,
                          nama_estate = EXCLUDED.nama_estate,
                          kode_est = EXCLUDED.kode_est
                    """
                )
            )


def _create_afdeling_table(conn: Connection) -> None:
    if not _table_exists(conn, "afdeling"):
        op.create_table(
            "afdeling",
            sa.Column("afd_id", sa.String(length=100), nullable=False),
            sa.Column("est_id", sa.String(length=50), nullable=False),
            sa.Column("kode_afd", sa.String(length=20), nullable=False),
            sa.PrimaryKeyConstraint("afd_id", name="pk_afdeling"),
            sa.ForeignKeyConstraint(["est_id"], ["estate.est_id"], ondelete="CASCADE", name="fk_afdeling_estate"),
        )
    _create_index_if_not_exists(conn, "ix_afdeling_est_id", "afdeling", ["est_id"])


def _sync_afdeling_from_afdelings(conn: Connection) -> None:
    if _table_exists(conn, "afdelings") and _table_exists(conn, "afdeling"):
        conn.execute(
            sa.text(
                """
                INSERT INTO afdeling (afd_id, est_id, kode_afd)
                SELECT
                    a.id::text AS afd_id,
                    a.estate_id::text AS est_id,
                    a.kode_afd
                FROM afdelings a
                JOIN estate e ON e.est_id = a.estate_id::text
                ON CONFLICT (afd_id) DO UPDATE
                  SET est_id = EXCLUDED.est_id,
                      kode_afd = EXCLUDED.kode_afd
                """
            )
        )


def _create_blok_table(conn: Connection) -> None:
    if not _table_exists(conn, "blok"):
        op.create_table(
            "blok",
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("afd_id", sa.String(length=100), nullable=False),
            sa.Column("nama_blok", sa.String(length=100), nullable=False),
            sa.Column("kode_blok", sa.String(length=50), nullable=False),
            sa.Column("tipe_blok", sa.String(length=50), nullable=True),
            sa.Column("jenis_topografi", sa.String(length=100), nullable=True),
            sa.Column("jenis_tanah", sa.String(length=100), nullable=True),
            sa.Column("jenis_bibit", sa.String(length=100), nullable=True),
            sa.Column("tahun_tanam", sa.Integer(), nullable=True),
            sa.Column("status_tanam", sa.String(length=20), nullable=True),
            sa.PrimaryKeyConstraint("global_id", name="pk_blok"),
            sa.ForeignKeyConstraint(["afd_id"], ["afdeling.afd_id"], ondelete="CASCADE", name="fk_blok_afdeling"),
            sa.UniqueConstraint("kode_blok", name="uq_blok_kode_blok"),
        )
    _create_index_if_not_exists(conn, "ix_blok_afd_id", "blok", ["afd_id"])


def _sync_blok_from_bloks(conn: Connection) -> None:
    if _table_exists(conn, "bloks") and _table_exists(conn, "blok"):
        conn.execute(
            sa.text(
                """
                INSERT INTO blok (
                    global_id, afd_id, nama_blok, kode_blok, tipe_blok,
                    jenis_topografi, jenis_tanah, jenis_bibit, tahun_tanam, status_tanam
                )
                SELECT
                    b.id::text AS global_id,
                    b.afdeling_id::text AS afd_id,
                    b.nama_blok,
                    b.kode_blok,
                    b.ownership AS tipe_blok,
                    b.topografi AS jenis_topografi,
                    b.jenis_tanah,
                    b.jenis_bibit,
                    b.tahun_tanam,
                    b.status_tanaman AS status_tanam
                FROM bloks b
                JOIN afdeling a ON a.afd_id = b.afdeling_id::text
                ON CONFLICT (global_id) DO UPDATE
                  SET afd_id = EXCLUDED.afd_id,
                      nama_blok = EXCLUDED.nama_blok,
                      kode_blok = EXCLUDED.kode_blok,
                      tipe_blok = EXCLUDED.tipe_blok,
                      jenis_topografi = EXCLUDED.jenis_topografi,
                      jenis_tanah = EXCLUDED.jenis_tanah,
                      jenis_bibit = EXCLUDED.jenis_bibit,
                      tahun_tanam = EXCLUDED.tahun_tanam,
                      status_tanam = EXCLUDED.status_tanam
                """
            )
        )


def _create_transaction_tables(conn: Connection) -> None:
    if not _table_exists(conn, "trx_areal_statement"):
        op.create_table(
            "trx_areal_statement",
            sa.Column("id_areal_statement", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("tahun", sa.Integer(), nullable=False),
            sa.Column("bulan", sa.Integer(), nullable=False),
            sa.Column("luas_tanam", sa.Numeric(14, 2), nullable=True),
            sa.Column("luas_tanah", sa.Numeric(14, 2), nullable=True),
            sa.Column("total_pokok", sa.Integer(), nullable=True),
            sa.Column("sph", sa.Numeric(10, 2), nullable=True),
            sa.Column("pct_tanah_datar", sa.Integer(), nullable=True),
            sa.Column("pct_berbukit", sa.Integer(), nullable=True),
            sa.Column("pct_gelombang", sa.Integer(), nullable=True),
            sa.Column("pct_curam", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_trx_areal_statement_blok"),
        )
    _create_index_if_not_exists(conn, "ix_trx_areal_statement_global_id", "trx_areal_statement", ["global_id"])
    _create_index_if_not_exists(conn, "ix_trx_areal_statement_tahun_bulan", "trx_areal_statement", ["tahun", "bulan"])

    if not _table_exists(conn, "trx_produksi_tbs"):
        op.create_table(
            "trx_produksi_tbs",
            sa.Column("id_produksi", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("tahun", sa.Integer(), nullable=False),
            sa.Column("bulan", sa.Integer(), nullable=False),
            sa.Column("tbs_aktual", sa.Numeric(14, 2), nullable=True),
            sa.Column("tbs_budget", sa.Numeric(14, 2), nullable=True),
            sa.Column("tbs_sensus", sa.Numeric(14, 2), nullable=True),
            sa.Column("janjang_aktual", sa.Integer(), nullable=True),
            sa.Column("janjang_budget", sa.Integer(), nullable=True),
            sa.Column("janjang_sensus", sa.Integer(), nullable=True),
            sa.Column("bjr_aktual", sa.Numeric(10, 2), nullable=True),
            sa.Column("bjr_budget", sa.Numeric(10, 2), nullable=True),
            sa.Column("bjr_sensus", sa.Numeric(10, 2), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_trx_produksi_tbs_blok"),
        )
    _create_index_if_not_exists(conn, "ix_trx_produksi_tbs_global_id", "trx_produksi_tbs", ["global_id"])
    _create_index_if_not_exists(conn, "ix_trx_produksi_tbs_tahun_bulan", "trx_produksi_tbs", ["tahun", "bulan"])

    if not _table_exists(conn, "trx_rotasi_pusingan"):
        op.create_table(
            "trx_rotasi_pusingan",
            sa.Column("id_rotasi_pusingan", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("tanggal", sa.Date(), nullable=False),
            sa.Column("tahun", sa.Integer(), nullable=False),
            sa.Column("bulan", sa.Integer(), nullable=False),
            sa.Column("rotasi_ke", sa.Numeric(10, 2), nullable=True),
            sa.Column("pusingan_hari", sa.Integer(), nullable=True),
            sa.Column("status_pusingan", sa.String(length=50), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_trx_rotasi_pusingan_blok"),
        )
    _create_index_if_not_exists(conn, "ix_trx_rotasi_pusingan_global_id", "trx_rotasi_pusingan", ["global_id"])
    _create_index_if_not_exists(conn, "ix_trx_rotasi_pusingan_tanggal", "trx_rotasi_pusingan", ["tanggal"])
    _create_index_if_not_exists(conn, "ix_trx_rotasi_pusingan_tahun_bulan", "trx_rotasi_pusingan", ["tahun", "bulan"])


def _create_spatial_tables(conn: Connection) -> None:
    if not _table_exists(conn, "geo_blok"):
        op.create_table(
            "geo_blok",
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("geom_polygon", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
            sa.PrimaryKeyConstraint("global_id", name="pk_geo_blok"),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_geo_blok_blok"),
        )

    if not _table_exists(conn, "geo_jalan"):
        op.create_table(
            "geo_jalan",
            sa.Column("id_jalan", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("objectid", sa.Float(), nullable=True),
            sa.Column("kategori", sa.String(length=100), nullable=True),
            sa.Column("lebar", sa.Float(), nullable=True),
            sa.Column("panjang", sa.Float(), nullable=True),
            sa.Column("ownership", sa.String(length=50), nullable=True),
            sa.Column("geom_line", Geometry("MULTILINESTRING", srid=4326), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_geo_jalan_blok"),
        )
    _create_index_if_not_exists(conn, "ix_geo_jalan_global_id", "geo_jalan", ["global_id"])

    if not _table_exists(conn, "geo_jembatan"):
        op.create_table(
            "geo_jembatan",
            sa.Column("id_jembatan", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("objectid", sa.Float(), nullable=True),
            sa.Column("kategori", sa.String(length=100), nullable=True),
            sa.Column("geom_point", Geometry("POINT", srid=4326), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_geo_jembatan_blok"),
        )
    _create_index_if_not_exists(conn, "ix_geo_jembatan_global_id", "geo_jembatan", ["global_id"])

    if not _table_exists(conn, "geo_landuse"):
        op.create_table(
            "geo_landuse",
            sa.Column("id_landuse", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("objectid", sa.Float(), nullable=True),
            sa.Column("landuse", sa.String(length=100), nullable=True),
            sa.Column("landuse_class", sa.String(length=100), nullable=True),
            sa.Column("luas", sa.Float(), nullable=True),
            sa.Column("shape_area", sa.Float(), nullable=True),
            sa.Column("geom_polygon", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_geo_landuse_blok"),
        )
    _create_index_if_not_exists(conn, "ix_geo_landuse_global_id", "geo_landuse", ["global_id"])

    if not _table_exists(conn, "geo_sawit"):
        op.create_table(
            "geo_sawit",
            sa.Column("id_sawit", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("objectid", sa.Float(), nullable=True),
            sa.Column("diameter", sa.Float(), nullable=True),
            sa.Column("jarak", sa.Float(), nullable=True),
            sa.Column("kategori", sa.String(length=100), nullable=True),
            sa.Column("geom_point", Geometry("POINT", srid=4326), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_geo_sawit_blok"),
        )
    _create_index_if_not_exists(conn, "ix_geo_sawit_global_id", "geo_sawit", ["global_id"])

    if not _table_exists(conn, "geo_slope"):
        op.create_table(
            "geo_slope",
            sa.Column("id_slope", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("objectid", sa.Float(), nullable=True),
            sa.Column("kategori", sa.String(length=100), nullable=True),
            sa.Column("kelerengan", sa.String(length=50), nullable=True),
            sa.Column("luas", sa.Float(), nullable=True),
            sa.Column("geom_polygon", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_geo_slope_blok"),
        )
    _create_index_if_not_exists(conn, "ix_geo_slope_global_id", "geo_slope", ["global_id"])

    if not _table_exists(conn, "geo_tph"):
        op.create_table(
            "geo_tph",
            sa.Column("id_tph", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("global_id", sa.String(length=150), nullable=False),
            sa.Column("kategori", sa.String(length=100), nullable=True),
            sa.Column("geom_point", Geometry("POINT", srid=4326), nullable=True),
            sa.ForeignKeyConstraint(["global_id"], ["blok.global_id"], ondelete="CASCADE", name="fk_geo_tph_blok"),
        )
    _create_index_if_not_exists(conn, "ix_geo_tph_global_id", "geo_tph", ["global_id"])


def upgrade() -> None:
    conn = op.get_bind()

    _create_perusahaan_table(conn)
    _sync_perusahaan_from_pts(conn)

    _create_estate_table(conn)
    _sync_estate_from_estates(conn)

    _create_afdeling_table(conn)
    _sync_afdeling_from_afdelings(conn)

    _create_blok_table(conn)
    _sync_blok_from_bloks(conn)

    _create_transaction_tables(conn)
    _create_spatial_tables(conn)


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "geo_tph"):
        op.drop_table("geo_tph")
    if _table_exists(conn, "geo_slope"):
        op.drop_table("geo_slope")
    if _table_exists(conn, "geo_sawit"):
        op.drop_table("geo_sawit")
    if _table_exists(conn, "geo_landuse"):
        op.drop_table("geo_landuse")
    if _table_exists(conn, "geo_jembatan"):
        op.drop_table("geo_jembatan")
    if _table_exists(conn, "geo_jalan"):
        op.drop_table("geo_jalan")
    if _table_exists(conn, "geo_blok"):
        op.drop_table("geo_blok")

    if _table_exists(conn, "trx_rotasi_pusingan"):
        op.drop_table("trx_rotasi_pusingan")
    if _table_exists(conn, "trx_produksi_tbs"):
        op.drop_table("trx_produksi_tbs")
    if _table_exists(conn, "trx_areal_statement"):
        op.drop_table("trx_areal_statement")

    if _table_exists(conn, "blok"):
        op.drop_table("blok")
    if _table_exists(conn, "afdeling"):
        op.drop_table("afdeling")
    if _table_exists(conn, "estate"):
        op.drop_table("estate")
    if _table_exists(conn, "perusahaan"):
        op.drop_table("perusahaan")
