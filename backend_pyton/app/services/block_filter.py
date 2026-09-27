"""
Potongan SQL bersama untuk query berbasis blok.

Semua query memakai alias tetap:
    bl = master.blocks, dv = master.divisions, es = master.estates,
    co = master.companies, bt = ref.block_types, la/ar = area terbaru blok.

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
"""

# Area tidak ada di hierarki master: diambil dari area statement terbaru blok.
LATEST_AREA_JOIN = """
    LEFT JOIN LATERAL (
        SELECT a.area_id FROM trx.area_statements a WHERE a.block_id = bl.id ORDER BY a.period DESC LIMIT 1
    ) la ON true
    LEFT JOIN master.areas ar ON ar.id = la.area_id
"""


def statement_as_of_join(as_of_param: str | None, extra_condition: str = "") -> str:
    """
    Area statement terbaru per blok (opsional dibatasi `period <= :as_of` dan
    kondisi tambahan atas alias `a`) + nama-nama referensinya.
    """
    period_filter = f"AND a.period <= :{as_of_param}" if as_of_param else ""
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


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


@dataclass
class BlockFilter:
    area: str | None = None
    kode_pt: str | None = None
    kode_est: str | None = None
    kode_afd: str | None = None
    blok: str | None = None
    ownership: str | None = None
    extra_where: list[str] = field(default_factory=list)
    extra_params: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in ("area", "kode_pt", "kode_est", "kode_afd", "blok", "ownership"):
            setattr(self, name, _clean(getattr(self, name)))

    @property
    def needs_area_join(self) -> bool:
        return self.area is not None

    def where(self) -> tuple[list[str], dict]:
        clauses, params = list(self.extra_where), dict(self.extra_params)
        if self.area:
            clauses.append("(ar.code = :f_area OR ar.id::text = :f_area OR upper(ar.name) = upper(:f_area))")
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
        return clauses, params

    def sql(self, with_area: bool = False) -> tuple[str, str, dict]:
        """(joins, where_sql, params) untuk ditempel setelah `FROM master.blocks bl`."""
        joins = BLOCK_JOINS + (LATEST_AREA_JOIN if (with_area or self.needs_area_join) else "")
        clauses, params = self.where()
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return joins, where_sql, params

    def block_ids_subquery(self) -> tuple[str, dict]:
        joins, where_sql, params = self.sql()
        return f"SELECT bl.id FROM master.blocks bl {joins} {where_sql}", params
