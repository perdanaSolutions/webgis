"""
Laporan tahap & hitungan proses upload GeoJSON.

Service upload menerima `progress` dan memanggil `stage` saat pindah tahap serta
`step` di dalam loop per fitur. Bawaannya `SILENT` (tidak melakukan apa pun), dipakai
endpoint sinkron. Worker antrian memakai implementasi yang menulis ke audit.upload_jobs
dan melempar `UploadCancelled` bila pengguna menekan batal.
"""
from uuid import UUID

# kode tahap -> pesan untuk pengguna; `{n}` diisi jumlah data bila tahapnya punya angka tetap
STAGES = {
    "membaca_file": "Membaca file GeoJSON",
    "validasi": "Memeriksa atribut & geometri",
    "mencocokkan_geometri": "Mencocokkan {n} data ke blok lewat posisi geometri",
    "menyusun_laporan": "Menyusun hasil analisis",
    "menyimpan": "Menyimpan data",
    "karantina": "Mencatat data yang ditolak",
    "menyelesaikan": "Menyelesaikan penyimpanan",
}


class UploadCancelled(Exception):
    """Pengguna membatalkan proses; transaksi simpan harus di-rollback."""

    def __init__(self) -> None:
        super().__init__("Dibatalkan oleh pengguna.")


class Progress:
    def stage(self, stage: str, total: int | None = None, n: int | None = None) -> None:
        """Mulai tahap baru. `total` = jumlah langkah yang akan dilaporkan lewat `step`."""

    def step(self, current: int) -> None:
        """Langkah ke-`current` dari `total` tahap berjalan. Boleh dipanggil per fitur."""

    def batch(self, batch_id: UUID) -> None:
        """Batch upload (audit.upload_batches) yang dibuat proses simpan."""


SILENT = Progress()


def stage_message(stage: str, n: int | None = None) -> str:
    template = STAGES[stage]
    return template.format(n=f"{n:,}".replace(",", ".")) if n is not None else template
