import json
import uuid

import pytest
from sqlalchemy import text

from app.core.database import SessionLocal
from app.db.session import engine
from app.services.upload import jobs
from app.workers import upload_jobs as worker

BULAN, TAHUN = 2, 2031  # periode khusus test supaya tidak bentrok data asli
URL = "/api/v1/upload-jobs"


@pytest.fixture(autouse=True)
def empty_queue():
    """Worker mengambil job antre tertua; sisa job antre dari run lain jangan ikut terambil."""
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit.upload_jobs SET status = 'cancelled', finished_at = now() "
                          "WHERE status IN ('queued', 'running')"))
    yield


@pytest.fixture
def jembatan(sample_block) -> bytes:
    with engine.connect() as conn:
        x, y = conn.execute(text("""
            SELECT ST_X(c), ST_Y(c) FROM (SELECT ST_PointOnSurface(geom) c FROM spatial.block_boundaries
            WHERE block_id = :b ORDER BY period DESC LIMIT 1) s
        """), {"b": sample_block["id"]}).one()
    props = {"EstID": sample_block["estate"], "Afdeling": sample_block["division"], "Blok": sample_block["code"],
             "OBJECTID": 900101, "Kategori": "Kayu"}
    yield json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [x, y]}},
        {"type": "Feature", "properties": {"OBJECTID": 900102, "Blok": "X"}, "geometry": None},
    ]}).encode()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM spatial.bridges WHERE period = make_date(:t, :m, 1)"), {"t": TAHUN, "m": BULAN})


def _create(client, auth, kind, layer, content):
    return client.post(URL, headers=auth, data={"kind": kind, "layer": layer, "bulan": BULAN, "tahun": TAHUN},
                       files={"file": ("jembatan.geojson", content, "application/geo+json")})


def test_analyze_and_execute_through_queue(client, auth, jembatan):
    created = _create(client, auth, "analyze", "jembatan", jembatan)
    assert created.status_code == 202, created.text
    job = created.json()
    assert job["status"] == "queued" and job["file_size"] == len(jembatan)
    assert job["job_id"] in {j["job_id"] for j in client.get(f"{URL}/active", headers=auth).json()}

    assert worker.run_once() == jobs.SUCCEEDED
    done = client.get(f"{URL}/{job['job_id']}", headers=auth).json()
    assert done["status"] == "succeeded" and done["stage"] == "selesai"
    sync = client.post("/api/v1/spatial/jembatan/upload-analyze", headers=auth, params={"bulan": BULAN, "tahun": TAHUN},
                       files={"file": ("jembatan.geojson", jembatan, "application/geo+json")}).json()
    assert done["result"] == sync  # bentuk hasil sama dengan endpoint lama -> AnalysisResult.vue tidak berubah
    assert done["result"]["data"]["jembatan_siap_diunggah"] == 1

    job = _create(client, auth, "execute", "jembatan", jembatan).json()
    assert worker.run_once() == jobs.SUCCEEDED
    done = client.get(f"{URL}/{job['job_id']}", headers=auth).json()
    assert done["result"]["detail"]["status_proses"] == "PARTIAL_SUCCESS"
    assert done["batch_id"] == done["result"]["detail"]["batch_id"]
    with engine.connect() as conn:
        content = conn.execute(text("SELECT content FROM audit.upload_jobs WHERE id = :id"), {"id": job["job_id"]}).scalar()
    assert content is None  # file dibuang setelah selesai


def test_invalid_file_fails_with_api_message(client, auth):
    job = _create(client, auth, "analyze", "jembatan", b"bukan json").json()
    assert worker.run_once() == jobs.FAILED
    done = client.get(f"{URL}/{job['job_id']}", headers=auth).json()
    assert done["status"] == "failed" and done["error_message"] == "Format file tidak valid atau bukan JSON."


def test_unknown_layer_rejected_before_queue(client, auth, jembatan):
    assert _create(client, auth, "analyze", "tidak-ada", jembatan).status_code == 404
    assert _create(client, auth, "hapus", "jembatan", jembatan).status_code == 422


def test_cancel_queued_job(client, auth, jembatan):
    job = _create(client, auth, "analyze", "jembatan", jembatan).json()
    cancelled = client.post(f"{URL}/{job['job_id']}/cancel", headers=auth)
    assert cancelled.json()["status"] == "cancelled"
    assert worker.run_once() is None  # tidak ada lagi yang antre
    assert client.post(f"{URL}/{job['job_id']}/cancel", headers=auth).status_code == 409


def test_cancel_running_execute_rolls_back(client, auth, jembatan):
    job_id = _create(client, auth, "execute", "jembatan", jembatan).json()["job_id"]
    claimed = jobs.claim_next(engine)
    assert str(claimed["id"]) == job_id
    assert client.post(f"{URL}/{job_id}/cancel", headers=auth).json()["cancel_requested"] is True

    assert worker.run_job(claimed) == jobs.CANCELLED
    done = client.get(f"{URL}/{job_id}", headers=auth).json()
    assert done["status"] == "cancelled" and done["result"] is None
    with engine.connect() as conn:
        saved = conn.execute(text("SELECT count(*) FROM spatial.bridges WHERE period = make_date(:t, :m, 1)"),
                             {"t": TAHUN, "m": BULAN}).scalar()
        batch = conn.execute(text("SELECT status FROM audit.upload_batches WHERE id = :id"),
                             {"id": done["batch_id"]}).scalar()
    assert saved == 0 and batch == "FAILED"


def test_job_is_private_to_its_owner(client, auth, jembatan):
    job_id = _create(client, auth, "analyze", "jembatan", jembatan).json()["job_id"]
    db = SessionLocal()
    try:
        with pytest.raises(Exception) as exc:
            jobs.get(db, uuid.UUID(job_id), uuid.uuid4())
    finally:
        db.close()
    assert exc.value.status_code == 404


def test_stale_running_job_is_failed(client, auth, jembatan):
    job_id = _create(client, auth, "analyze", "jembatan", jembatan).json()["job_id"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit.upload_jobs SET status = 'running', heartbeat_at = now() - interval '10 minutes' "
                          "WHERE id = :id"), {"id": job_id})
    assert jobs.fail_stale(engine, 120) >= 1
    done = client.get(f"{URL}/{job_id}", headers=auth).json()
    assert done["status"] == "failed" and done["error_message"] == jobs.STALE_MESSAGE


def test_feature_part_metadata_is_stored(client, auth, jembatan):
    group_id = str(uuid.uuid4())
    created = client.post(
        URL,
        headers=auth,
        data={
            "kind": "analyze",
            "layer": "jembatan",
            "bulan": BULAN,
            "tahun": TAHUN,
            "upload_group_id": group_id,
            "part_index": 2,
            "part_total": 5,
        },
        files={"file": ("jembatan.part2of5.geojson", jembatan, "application/geo+json")},
    )
    assert created.status_code == 202, created.text
    job = created.json()
    assert job["upload_group_id"] == group_id
    assert job["part_index"] == 2 and job["part_total"] == 5
    assert "part 2/5" in (job["message"] or "")
    assert worker.run_once() == jobs.SUCCEEDED
