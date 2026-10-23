"""Sertifikat klien hanya diwajibkan pada path yang dilindungi, lewat HTTPS."""
import json
import shutil
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from starlette.requests import Request

from app.core.mtls import (
    MtlsGuardMiddleware,
    assert_allowed_client,
    build_ssl_context,
    install_peer_cert_scope,
    path_requires_client_cert,
)


class _Peer:
    def __init__(self, cert):
        self._cert = cert

    def getpeercert(self):
        return self._cert


def _request(scope_ssl=None):
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https" if scope_ssl is not None else "http",
        "path": "/api/v1/mtls/identity",
        "raw_path": b"/api/v1/mtls/identity",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 8443),
    }
    if scope_ssl is not None:
        scope["ssl_object"] = scope_ssl
    return Request(scope)


def test_path_guard_matches_prefix_boundary():
    assert path_requires_client_cert("/api/v1/spatial/grup", ["/api/"])
    assert path_requires_client_cert("/health", ["/api/"]) is False
    assert path_requires_client_cert("/api/v1/spatial-lain", ["/api/v1/spatial"]) is False


def test_missing_https_and_certificate_are_rejected():
    with pytest.raises(Exception) as missing_tls:
        assert_allowed_client(None, ["backend-external"])
    assert missing_tls.value.status_code == 403

    with pytest.raises(Exception) as missing_cert:
        assert_allowed_client(_Peer(None), ["backend-external"])
    assert missing_cert.value.status_code == 401


def test_common_name_must_be_allowed():
    subject = ((("commonName", "orang-lain"),),)
    with pytest.raises(Exception) as denied:
        assert_allowed_client(_Peer({"subject": subject}), ["backend-external"])
    assert denied.value.status_code == 403
    assert "orang-lain" in denied.value.detail["errors"][0]["msg"]

    allowed = assert_allowed_client(
        _Peer({"subject": ((("commonName", "backend-external"),),)}),
        ["backend-external"],
    )
    assert allowed == "backend-external"


def _fetch(url: str, ca_file: Path, cert: tuple[Path, Path] | None = None):
    context = ssl.create_default_context(cafile=str(ca_file))
    if cert is not None:
        context.load_cert_chain(certfile=str(cert[0]), keyfile=str(cert[1]))
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, context=context, timeout=5) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def test_tls_listener_accepts_only_backend_external(tmp_path: Path):
    if shutil.which("openssl") is None:
        pytest.skip("openssl tidak tersedia")

    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_mtls_certs.sh"
    subprocess.run(["bash", str(script), str(tmp_path)], check=True, capture_output=True, text=True)

    runtime = tmp_path / "runtime"
    client = tmp_path / "client"
    other_key = tmp_path / "other.key"
    other_csr = tmp_path / "other.csr"
    other_crt = tmp_path / "other.crt"
    other_ext = tmp_path / "other_ext.cnf"
    other_ext.write_text(
        "basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=clientAuth\n"
    )
    subprocess.run(["openssl", "genrsa", "-out", str(other_key), "2048"], check=True, capture_output=True)
    subprocess.run(
        ["openssl", "req", "-new", "-key", str(other_key), "-out", str(other_csr), "-subj", "/CN=orang-lain"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "openssl", "x509", "-req", "-in", str(other_csr),
            "-CA", str(tmp_path / "private" / "ca.crt"),
            "-CAkey", str(tmp_path / "private" / "ca.key"),
            "-CAcreateserial", "-out", str(other_crt), "-days", "1", "-sha256",
            "-extfile", str(other_ext),
        ],
        check=True,
        capture_output=True,
    )

    app = FastAPI()
    app.add_middleware(MtlsGuardMiddleware, required_prefixes=["/api/"], allowed_cns=["backend-external"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def require_external(request: Request) -> str:
        return assert_allowed_client(request.scope.get("ssl_object"), ["backend-external"])

    @app.get("/api/v1/gis/spatial-data")
    def spatial(client_cn: str = Depends(require_external)):
        return {"status": "success", "authorized_client": client_cn}

    install_peer_cert_scope()
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=0, lifespan="off", log_level="warning")
    server = uvicorn.Server(config)
    context = build_ssl_context(
        str(runtime / "server.crt"), str(runtime / "server.key"), str(runtime / "ca.crt")
    )

    async def _serve(sockets=None):
        if not server.config.loaded:
            server.config.load()
        server.config.ssl = context
        await original_serve(sockets)

    original_serve = server._serve
    server._serve = _serve
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "listener mTLS tidak naik"
    port = server.servers[0].sockets[0].getsockname()[1]
    base = f"https://127.0.0.1:{port}"
    ca = runtime / "ca.crt"
    try:
        health_status, health_body = _fetch(f"{base}/health", ca)
        assert health_status == 200
        assert health_body["status"] == "ok"

        denied_status, denied_body = _fetch(f"{base}/api/v1/gis/spatial-data", ca)
        assert denied_status == 401
        assert denied_body["errors"][0]["field"] == "client_certificate"

        ok_status, ok_body = _fetch(
            f"{base}/api/v1/gis/spatial-data", ca, (client / "client.crt", client / "client.key")
        )
        assert ok_status == 200
        assert ok_body["authorized_client"] == "backend-external"

        foreign_status, foreign_body = _fetch(
            f"{base}/api/v1/gis/spatial-data", ca, (other_crt, other_key)
        )
        assert foreign_status == 403
        assert "orang-lain" in foreign_body["errors"][0]["msg"]
    finally:
        server.should_exit = True
        thread.join(timeout=5)
