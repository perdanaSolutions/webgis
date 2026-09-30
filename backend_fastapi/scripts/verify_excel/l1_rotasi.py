import os, sys
from common import *
pd.set_option("display.width", 250)
x = load_rot()
print(x.shape, x.columns.tolist())
print("Periode:", x.Periode.value_counts().sort_index().to_dict())
print("Bulan uniq:", sorted(x.Bulan.unique()))
print("Status:", x["Status Pusingan"].value_counts(dropna=False).to_dict())
print("Rotasi uniq:", sorted(x.Rotasi.unique())[:20], "Pusingan uniq:", sorted(x.Pusingan.unique())[:15])
x["tgl"] = pd.to_datetime(x.Tanggal)
print("Tanggal != Periode/Bulan:", int(((x.tgl.dt.year != x.Periode) | (x.tgl.dt.month != x.Bulan)).sum()))
print(x.groupby("Blok").size().describe().to_dict())

# blok unik: estate nama + afdeling + blok
db = sql(f"""SELECT bl.id block_id, e.name est_name, e.code est, d.code dv, bl.code blk, h.period, h.area_ha, h.tree_count, h.rotation_no, h.interval_days, rs.name status
 {BJ} JOIN trx.harvest_rotations h ON h.block_id=bl.id LEFT JOIN ref.rotation_statuses rs ON rs.id=h.rotation_status_id""")
print("DB rows", len(db))
x["key"] = list(zip(x.Estate.str.strip().str.upper(), x.Afdeling, x.Blok, x.tgl.dt.year, x.tgl.dt.month))
db["key"] = list(zip(db.est_name.str.strip().str.upper(), db.dv, db.blk, db.period.map(lambda d: d.year), db.period.map(lambda d: d.month)))
print("dup keys excel:", int(x.key.duplicated().sum()), " dup db:", int(db.key.duplicated().sum()))
ek, dk = set(x.key), set(db.key)
print("excel not in db:", len(ek - dk), list(ek - dk)[:3], "| db not in excel:", len(dk - ek), list(dk - ek)[:3])
m = x.merge(db, on="key", suffixes=("_x", "_d"))
print("matched", len(m))

def cmp(n, a, b, tol=0.01):
    a = pd.to_numeric(a, errors="coerce"); b = pd.to_numeric(b, errors="coerce")
    bad = ~((a - b).abs() <= tol) & ~(a.isna() & b.isna())
    print(f"{n:10s} mismatch={int(bad.sum())}", m.loc[bad, ["key"]].head(2).values.tolist() if bad.any() else "")

cmp("Luas", m.Luas, m.area_ha); cmp("Pokok", m.Pokok, m.tree_count, 0.5)
cmp("Rotasi", m.Rotasi, m.rotation_no); cmp("Pusingan", m.Pusingan, m.interval_days, 0.5)
bad = m["Status Pusingan"].astype(str).str.strip() != m.status.astype(str)
print("Status mismatch:", int(bad.sum()), m.loc[bad, ["Status Pusingan", "status"]].drop_duplicates().head(6).values.tolist())
print("Estate nama di excel:", sorted(x.Estate.unique()))
