"""Jalankan seluruh verifikasi Excel <-> database. Kode keluar != 0 bila lapis 2/3 (respons API) ada yang beda."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
INFO = ["l1_areal_statement.py", "l1_produksi.py", "l1_rotasi.py", "l1_bibit.py"]       # laporan, tidak menggagalkan
GATE = ["l2_history_produksi.py", "l2_history_areal_rotasi.py", "l2_detail.py", "l3_http.py"]

failed = []
for name in INFO + GATE:
    print(f"\n{'=' * 8} {name} {'=' * 8}", flush=True)
    code = subprocess.call([sys.executable, str(HERE / name)], cwd=HERE)
    if code != 0 and name in GATE:
        failed.append(name)
print("\nHASIL:", "SEMUA SESUAI" if not failed else f"ADA SELISIH di {failed}")
sys.exit(1 if failed else 0)
