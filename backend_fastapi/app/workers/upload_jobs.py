"""
Worker antrian upload GeoJSON (audit.upload_jobs). Proses terpisah dari API:

    python -m app.workers.upload_jobs

Satu worker mengerjakan satu job pada satu waktu. SIGTERM/SIGINT menunggu job berjalan selesai
(atur stop_grace_period container cukup panjang); worker yang mati mendadak dideteksi lewat
heartbeat oleh worker berikutnya dan job-nya ditandai gagal.
"""
import logging
import signal
import time

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.db.session import set_audit_actor
from app.services.upload import jobs, runner
from app.services.upload.progress import UploadCancelled

logger = logging.getLogger("app.workers.upload_jobs")

_stopping = False


def _request_stop(signum, _frame) -> None:
    global _stopping
    _stopping = True
    logger.info("Sinyal %s diterima, worker berhenti setelah job berjalan selesai", signum)


def error_message(exc: Exception) -> str:
    """Pesan untuk pengguna, setara dengan yang dikirim API sinkron untuk error yang sama."""
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict) and detail.get("errors"):
        return str(detail["errors"][0].get("msg"))
    if isinstance(exc, HTTPException):
        return str(detail)
    if isinstance(exc, DBAPIError):
        return f"Kesalahan database: {exc.orig}".strip()[:2000]
    return "Terjadi kesalahan pada server saat memproses file."


def run_job(job: dict) -> str:
    """Kerjakan satu job yang sudah diklaim. Mengembalikan status akhirnya."""
    job_id = job["id"]
    progress = jobs.JobProgress(engine, job_id)
    data = runner.UploadInput(
        bytes(job["content"]), job["filename"], job["bulan"], job["tahun"], job["user_id"],
        part_index=job.get("part_index") or 1, part_total=job.get("part_total") or 1,
        feature_offset=job.get("feature_offset") or 0,
        protected_batch_ids=tuple(jobs.group_batch_ids(engine, job.get("upload_group_id"), job_id))
        if job["kind"] == runner.EXECUTE else (),
    )
    db = SessionLocal()
    set_audit_actor(db, job["user_id"])
    try:
        with jobs.Heartbeat(engine, job_id, settings.UPLOAD_JOB_HEARTBEAT_SECONDS):
            result = runner.run_for_job(db, job["kind"], job["layer"], data, progress)
    except UploadCancelled:
        db.rollback()
        jobs.close_open_batch(engine, progress.batch_id, jobs.CANCELLED_MESSAGE)
        jobs.finish(engine, job_id, jobs.CANCELLED, error=jobs.CANCELLED_MESSAGE)
        return jobs.CANCELLED
    except Exception as exc:
        db.rollback()
        if not isinstance(exc, HTTPException):
            logger.exception("Job upload %s gagal", job_id)
        message = error_message(exc)
        jobs.close_open_batch(engine, progress.batch_id, message)
        jobs.finish(engine, job_id, jobs.FAILED, error=message)
        return jobs.FAILED
    finally:
        db.close()
    jobs.finish(engine, job_id, jobs.SUCCEEDED, result=result)
    return jobs.SUCCEEDED


def run_once() -> str | None:
    """Ambil & kerjakan satu job bila ada. Mengembalikan status akhirnya, atau None bila antrian kosong."""
    job = jobs.claim_next(engine)
    if job is None:
        return None
    logger.info("Mulai job %s (%s %s, %s)", job["id"], job["kind"], job["layer"], job["filename"])
    started = time.monotonic()
    status = run_job(job)
    logger.info("Job %s selesai: %s dalam %.1f detik", job["id"], status, time.monotonic() - started)
    return status


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    logger.info("Worker upload GeoJSON berjalan")
    last_housekeeping = 0.0
    while not _stopping:
        try:
            if time.monotonic() - last_housekeeping > 60:
                if failed := jobs.fail_stale(engine, settings.UPLOAD_JOB_STALE_SECONDS):
                    logger.warning("%s job berjalan tanpa heartbeat ditandai gagal", failed)
                jobs.purge_finished(engine, settings.UPLOAD_JOB_KEEP_DAYS)
                last_housekeeping = time.monotonic()
            if run_once() is None:
                time.sleep(settings.UPLOAD_JOB_POLL_SECONDS)
        except Exception:
            logger.exception("Kesalahan worker, mencoba lagi")
            time.sleep(settings.UPLOAD_JOB_POLL_SECONDS)
    logger.info("Worker upload GeoJSON berhenti")


if __name__ == "__main__":
    main()
