import os, sys
from common import *
S = load_stmt()
S["key"] = list(zip(S.UnitCode, S.DivisionCode, S.KodeBlok, S.Year, S.Month))
db = sql(f"""SELECT e.code est, d.code dv, bl.code blk, a.period,
  (SELECT string_agg(sv.name, ', ' ORDER BY sv.name) FROM trx.area_statement_seed_varieties x JOIN ref.seed_varieties sv ON sv.id=x.seed_variety_id WHERE x.area_statement_id=a.id) seeds
  {BJ} JOIN trx.area_statements a ON a.block_id=bl.id""")
db["key"] = list(zip(db.est, db.dv, db.blk, db.period.map(lambda d: d.year), db.period.map(lambda d: d.month)))
m = S.merge(db[["key", "seeds"]], on="key")
alias = {"CSTR": "COSTARIKA"}
def norm(v):
    parts = [alias.get(p.strip(), p.strip()) for p in str(v).split(",")]
    return ", ".join(sorted(parts))
m["exp"] = m.JenisBibit.map(norm)
bad = m[m.exp != m.seeds.fillna("")]
print("statement dicek:", len(m), "| bibit tidak cocok:", len(bad))
print(bad.groupby(["JenisBibit", "seeds"], dropna=False).size().head(10))
