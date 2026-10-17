"""
Potongan SQL bersama untuk query berbasis blok.

Semua query memakai alias tetap:
    bl = master.blocks, dv = master.divisions, es = master.estates,
    co = master.companies, bt = ref.block_types,
    est_area = area saat ini estate, co_group = grup PT.
Struktur v2: grup melekat ke PT (co.group_id), area saat ini melekat ke estate (es.area_id).
Riwayat area per bulan tetap ada di trx.area_statements (dipakai detail & histori per periode).

Filter menerima id numerik v3 ATAU kode (dan untuk blok: id string lama v2
seperti 'PT_TELEN_E006_AFDI02_G018' lewat audit.legacy_id_maps), sehingga
nilai lama yang tersimpan di FE tetap bisa dipakai.
"""
from dataclasses import dataclass, field

BLOCK_JOINS = """
    JOIN master.divisions dv ON dv.id = bl.division_id
    JOIN master.estates es ON es.id = dv.estate_id
    JOIN master.companies co ON co.id = es.company_id
    LEFT JOIN ref.block_types bt ON bt.id = bl.block_type_id
    LEFT JOIN master.areas est_area ON est_area.id = es.area_id
    LEFT JOIN master.groups co_group ON co_group.id = co.group_id
"""



def statement_as_of_join(as_of_param: str | None, extra_condition: str = "", *, exact: bool = False) -> str:
    """
    Area statement per blok + nama-nama referensinya.

    `exact` memakai `period = :as_of` (bulan+tahun filter). Tanpa itu, baris
    terbaru dengan `period <= :as_of` bila parameter periode diisi.
    """
    if as_of_param and exact:
        period_filter = f"AND a.period = :{as_of_param}"
    elif as_of_param:
        period_filter = f"AND a.period <= :{as_of_param}"
    else:
        period_filter = ""
    extra = f"AND {extra_condition}" if extra_condition else ""
    return f"""
    LEFT JOIN LATERAL (
        SELECT a.* FROM trx.area_statements a
        WHERE a.block_id = bl.id {period_filter} {extra}
        ORDER BY a.period DESC LIMIT 1
    ) st ON true
    LEFT JOIN ref.planting_statuses ps ON ps.id = st.planting_status_id
    LEFT JOIN ref.soil_types so ON so.id = st.soil_type_id
    LEFT JOIN ref.topography_types tp ON tp.id = st.topography_type_id
    LEFT JOIN master.areas sar ON sar.id = st.area_id
    """


SEED_VARIETIES_OF_STATEMENT = """
    (SELECT string_agg(sv.name, ', ' ORDER BY sv.name)
       FROM trx.area_statement_seed_varieties x JOIN ref.seed_varieties sv ON sv.id = x.seed_variety_id
      WHERE x.area_statement_id = st.id)
"""

BLOCK_REF_MATCH = """(
    bl.id::text = :{p} OR upper(bl.code) = upper(:{p})
    OR bl.id::text IN (SELECT new_id FROM audit.legacy_id_maps WHERE table_name = 'master.blocks' AND legacy_id = :{p})
)"""


# Grup (lewat PT, alias `co`) dan area (lewat estate, alias `es`) dicocokkan dengan kode, id, atau nama.
# Dipakai juga oleh daftar dropdown. Area menerima id lama v2 berawalan 'AR_' (dibuang sebelum dipakai).
GROUP_MATCH = "co.group_id IN (SELECT gr.id FROM master.groups gr WHERE upper(gr.code) = upper(:{p}) OR gr.id::text = :{p})"
AREA_MATCH = ("es.area_id IN (SELECT ar.id FROM master.areas ar "
              "WHERE ar.code = :{p} OR ar.id::text = :{p} OR upper(ar.name) = upper(:{p}))")


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


# Tahun tanam = planting_year di area statement TERBARU blok (bukan tahun kalender periode).
# planting_year kosong = belum ditanam, dicocokkan dengan tahun tanam 0.
_LATEST_PLANTING_YEAR = """EXISTS (
    SELECT 1 FROM (
        SELECT a.planting_year FROM trx.area_statements a
        WHERE a.block_id = bl.id ORDER BY a.period DESC LIMIT 1
    ) latest WHERE COALESCE(latest.planting_year, 0) = :f_tt
)"""


@dataclass
class BlockFilter:
    grup: str | None = None
    area: str | None = None
    kode_pt: str | None = None
    kode_est: str | None = None
    kode_afd: str | None = None
    blok: str | None = None
    ownership: str | None = None
    tahun_tanam: str | None = None
    extra_where: list[str] = field(default_factory=list)
    extra_params: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in ("grup", "area", "kode_pt", "kode_est", "kode_afd", "blok", "ownership", "tahun_tanam"):
            setattr(self, name, _clean(getattr(self, name)))
        if self.tahun_tanam is not None and not self.tahun_tanam.isdigit():
            self.tahun_tanam = None

    def where(self) -> tuple[list[str], dict]:
        clauses, params = list(self.extra_where), dict(self.extra_params)
        if self.grup:
            clauses.append(GROUP_MATCH.format(p="f_grup"))
            params["f_grup"] = self.grup
        if self.area:
            clauses.append(AREA_MATCH.format(p="f_area"))
            params["f_area"] = self.area.removeprefix("AR_")  # id area lama v2: 'AR_BERAU'
        if self.kode_pt:
            clauses.append("(co.code = :f_pt OR co.id::text = :f_pt OR upper(co.name) = upper(:f_pt))")
            params["f_pt"] = self.kode_pt
        if self.kode_est:
            clauses.append("(upper(es.code) = upper(:f_est) OR es.id::text = :f_est OR upper(es.short_name) = upper(:f_est))")
            params["f_est"] = self.kode_est
        if self.kode_afd:
            clauses.append("(upper(dv.code) = upper(:f_afd) OR dv.id::text = :f_afd)")
            params["f_afd"] = self.kode_afd
        if self.blok:
            clauses.append(BLOCK_REF_MATCH.format(p="f_blok"))
            params["f_blok"] = self.blok
        if self.ownership:
            clauses.append("lower(bt.name) = lower(:f_owner)")
            params["f_owner"] = self.ownership
        if self.tahun_tanam:
            clauses.append(_LATEST_PLANTING_YEAR)
            params["f_tt"] = int(self.tahun_tanam)
        return clauses, params

    def sql(self) -> tuple[str, str, dict]:
        """(joins, where_sql, params) untuk ditempel setelah `FROM master.blocks bl`."""
        joins = BLOCK_JOINS
        clauses, params = self.where()
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return joins, where_sql, params

    def block_ids_subquery(self) -> tuple[str, dict]:
        joins, where_sql, params = self.sql()
        return f"SELECT bl.id FROM master.blocks bl {joins} {where_sql}", params
