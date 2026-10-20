"""
Antrian upload GeoJSON (audit.upload_jobs).

Sisi API: `create`, `get`, `active`, `cancel` (memakai sesi request).
Sisi worker: `claim_next`, `JobProgress`, `Heartbeat`, `finish`, `fail_stale`, `purge_finished`.
Tulisan worker memakai koneksi sendiri (engine), terpisah dari sesi yang memegang transaksi
simpan, supaya progres langsung terlihat oleh FE walau data belum di-commit.
"""
import json
import threading
import time
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, conflict, not_found
from app.services.upload.progress import Progress, UploadCancelled, stage_message

QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED = "queued", "running", "succeeded", "failed", "cancelled"
STALE_MESSAGE = "Proses terhenti karena worker berhenti di tengah jalan. Silakan unggah ulang file."
CANCELLED_MESSAGE = "Dibatalkan oleh pengguna. Tidak ada data yang disimpan."

_VIEW = """
    SELECT j.id, j.status, j.kind, j.layer, j.bulan, j.tahun, j.filename, j.file_size, j.stage, j.message,
           j.progress_current, j.progress_total, j.error_message, j.batch_id, j.cancel_requested,
           j.upload_group_id, j.part_index, j.part_total,
           j.created_at, j.started_at, j.finished_at,
           EXTRACT(EPOCH FROM COALESCE(j.finished_at, now()) - COALESCE(j.started_at, j.created_at))::int AS elapsed,
           CASE WHEN j.status = 'queued' THEN (
               SELECT count(*) FROM audit.upload_jobs q WHERE q.status = 'queued' AND q.created_at < j.created_at
           ) END AS queue_ahead
           {extra}
    FROM audit.upload_jobs j
"""


def _view(row, with_result: bool = False) -> dict:
    data = {
        "job_id": str(row["id"]),
        "status": row["status"],
        "kind": row["kind"],
        "layer": row["layer"],
        "bulan": row["bulan"],
        "tahun": row["tahun"],
        "filename": row["filename"],
        "file_size": row["file_size"],
        "stage": row["stage"],
        "message": row["message"],
        "current": row["progress_current"],
        "total": row["progress_total"],
        "elapsed_seconds": row["elapsed"],
        "queue_ahead": row["queue_ahead"],
        "cancel_requested": row["cancel_requested"],
        "error_message": row["error_message"],
        "batch_id": str(row["batch_id"]) if row["batch_id"] else None,
        "upload_group_id": str(row["upload_group_id"]) if row["upload_group_id"] else None,
        "part_index": row["part_index"],
        "part_total": row["part_total"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }
    if with_result:
        data["result"] = row["result"]
    return data


def _fetch(db: Session, job_id: UUID, user_id: UUID, with_result: bool = False) -> dict:
    sql = _VIEW.format(extra=", j.result" if with_result else "") + " WHERE j.id = :id AND j.user_id = :u"
    row = db.execute(text(sql), {"id": str(job_id), "u": str(user_id)}).mappings().first()
    if row is None:
        raise not_found("Proses upload tidak ditemukan.")
    return _view(row, with_result)


# =====================================================================
# SISI API
# =====================================================================

def create(db: Session, *, user_id: UUID, kind: str, layer: str, bulan: int, tahun: int, filename: str | None,
           content: bytes, upload_group_id: UUID | None = None, part_index: int | None = None,
           part_total: int | None = None) -> dict:
    """Antrekan satu file GeoJSON. FE boleh mengirim beberapa part Feature (≤1000/part) dengan
    `upload_group_id` + `part_index`/`part_total`; tiap part = satu job worker terpisah."""
    if (part_index is None) ^ (part_total is None):
        raise bad_request("part_index dan part_total harus diisi bersamaan.", field="part_index")
    if part_total is not None and part_total < 1:
        raise bad_request("part_total minimal 1.", field="part_total")
    if part_index is not None and not (1 <= part_index <= part_total):
        raise bad_request("part_index harus antara 1 dan part_total.", field="part_index")
    if part_total is not None and part_total > 1 and upload_group_id is None:
        raise bad_request("upload_group_id wajib bila part_total > 1.", field="upload_group_id")

    message = "Menunggu giliran diproses"
    if part_index is not None and part_total is not None and part_total > 1:
        message = f"Menunggu giliran diproses (part {part_index}/{part_total})"

    job_id = db.execute(text("""
        INSERT INTO audit.upload_jobs (
            user_id, kind, layer, bulan, tahun, filename, file_size, content, message,
            upload_group_id, part_index, part_total
        )
        VALUES (
            :u, :kind, :layer, :bulan, :tahun, :filename, :size, :content, :message,
            :group_id, :part_index, :part_total
        )
        RETURNING id
    """), {"u": str(user_id), "kind": kind, "layer": layer, "bulan": bulan, "tahun": tahun,
           "filename": (filename or "")[:255] or None, "size": len(content), "content": content,
           "message": message,
           "group_id": str(upload_group_id) if upload_group_id else None,
           "part_index": part_index, "part_total": part_total}).scalar_one()
    db.commit()
    return _fetch(db, job_id, user_id)


def get(db: Session, job_id: UUID, user_id: UUID) -> dict:
    """Status satu job milik user; `result` = respons lama upload-analyze/upload-execute bila sudah selesai."""
    return _fetch(db, job_id, user_id, with_result=True)


def active(db: Session, user_id: UUID) -> list[dict]:
    rows = db.execute(text(_VIEW.format(extra="") + """
        WHERE j.user_id = :u AND j.status IN ('queued', 'running') ORDER BY j.created_at
    """), {"u": str(user_id)}).mappings().all()
    return [_view(r) for r in rows]


def cancel(db: Session, job_id: UUID, user_id: UUID) -> dict:
    """Job antre langsung dibatalkan; job berjalan ditandai dan dihentikan worker sebelum commit."""
    updated = db.execute(text("""
        UPDATE audit.upload_jobs SET
            cancel_requested = true,
            status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
            error_message = CASE WHEN status = 'queued' THEN :msg ELSE error_message END,
            content = CASE WHEN status = 'queued' THEN NULL ELSE content END,
            finished_at = CASE WHEN status = 'queued' THEN now() ELSE finished_at END
        WHERE id = :id AND user_id = :u AND status IN ('queued', 'running')
        RETURNING id
    """), {"id": str(job_id), "u": str(user_id), "msg": CANCELLED_MESSAGE}).first()
    db.commit()
    job = _fetch(db, job_id, user_id)
    if updated is None:
        raise conflict(f"Proses upload sudah selesai (status: {job['status']}), tidak bisa dibatalkan.")
    return job


# =====================================================================
# SISI WORKER
# =====================================================================

def claim_next(engine: Engine) -> dict | None:
    """Ambil satu job antre tertua. SKIP LOCKED: beberapa worker tidak mengambil job yang sama."""
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE audit.upload_jobs SET status = 'running', started_at = now(), heartbeat_at = now(),
                   stage = 'membaca_file', message = :msg
            WHERE id = (
                SELECT id FROM audit.upload_jobs WHERE status = 'queued'
                ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
            )
            RETURNING id, user_id, kind, layer, bulan, tahun, filename, content
        """), {"msg": stage_message("membaca_file")}).mappings().first()
    return dict(row) if row else None


def finish(engine: Engine, job_id: UUID, status: str, *, result: Any = None, error: str | None = None) -> None:
    payload = json.dumps(jsonable_encoder(result)) if result is not None else None
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE audit.upload_jobs SET status = :status, result = CAST(:result AS jsonb), error_message = :error,
                   content = NULL, finished_at = now(), heartbeat_at = now(),
                   stage = CASE WHEN :status = 'succeeded' THEN 'selesai' ELSE stage END,
                   message = CASE WHEN :status = 'succeeded' THEN 'Selesai' ELSE message END
            WHERE id = :id
        """), {"id": str(job_id), "status": status, "result": payload, "error": error})


def close_open_batch(engine: Engine, batch_id: UUID | None, error: str) -> None:
    """Batch simpan yang masih IN_PROGRESS (proses terputus/dibatalkan sebelum service menutupnya) -> FAILED."""
    if batch_id is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE audit.upload_batches SET status = 'FAILED', error_message = :error, finished_at = now()
            WHERE id = :id AND status = 'IN_PROGRESS'
        """), {"id": str(batch_id), "error": error[:2000]})


def fail_stale(engine: Engine, stale_seconds: int) -> int:
    """Job 'running' yang heartbeat-nya berhenti (worker mati/di-restart) -> failed."""
    with engine.begin() as conn:
        rows = conn.execute(text("""
            UPDATE audit.upload_jobs SET status = 'failed', error_message = :msg, content = NULL, finished_at = now()
            WHERE status = 'running' AND heartbeat_at < now() - make_interval(secs => :s)
            RETURNING batch_id
        """), {"msg": STALE_MESSAGE, "s": stale_seconds}).all()
    for (batch_id,) in rows:
        close_open_batch(engine, batch_id, STALE_MESSAGE)
    return len(rows)


def purge_finished(engine: Engine, keep_days: int) -> int:
    with engine.begin() as conn:
        return conn.execute(text("""
            DELETE FROM audit.upload_jobs
            WHERE status IN ('succeeded', 'failed', 'cancelled') AND finished_at < now() - make_interval(days => :d)
        """), {"d": keep_days}).rowcount


class JobProgress(Progress):
    """Tulis tahap & hitungan ke baris job (maks. sekali per `interval` detik untuk `step`) dan cek pembatalan."""

    def __init__(self, engine: Engine, job_id: UUID, interval: float = 1.0):
        self.engine, self.job_id, self.interval = engine, job_id, interval
        self.batch_id: UUID | None = None
        self._total: int | None = None
        self._last_write = 0.0

    def _write(self, values: dict) -> None:
        sets = ", ".join(f"{column} = :{column}" for column in values)
        with self.engine.begin() as conn:
            cancel_requested = conn.execute(
                text(f"UPDATE audit.upload_jobs SET {sets}, heartbeat_at = now() WHERE id = :id RETURNING cancel_requested"),
                {**values, "id": str(self.job_id)},
            ).scalar()
        self._last_write = time.monotonic()
        if cancel_requested:
            raise UploadCancelled()

    def stage(self, stage: str, total: int | None = None, n: int | None = None) -> None:
        self._total = total
        self._write({"stage": stage, "message": stage_message(stage, n),
                     "progress_current": 0 if total is not None else None, "progress_total": total})

    def step(self, current: int) -> None:
        if current != self._total and time.monotonic() - self._last_write < self.interval:
            return
        self._write({"progress_current": current})

    def batch(self, batch_id: UUID) -> None:
        self.batch_id = batch_id
        self._write({"batch_id": str(batch_id)})


class Heartbeat:
    """
    Detak jantung berkala di thread terpisah. Tahap tanpa `step` (mis. query pencocokan geometri)
    bisa berjalan lama tanpa menulis progres; detak ini membedakannya dari worker yang mati.
    """

    def __init__(self, engine: Engine, job_id: UUID, interval: float):
        self.engine, self.job_id, self.interval = engine, job_id, interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"heartbeat-{job_id}", daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                with self.engine.begin() as conn:
                    conn.execute(text("UPDATE audit.upload_jobs SET heartbeat_at = now() WHERE id = :id"),
                                 {"id": str(self.job_id)})
            except Exception:  # koneksi putus sesaat: detak berikutnya mencoba lagi
                pass

    def __enter__(self) -> "Heartbeat":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._stop.set()
        self._thread.join(timeout=self.interval)
