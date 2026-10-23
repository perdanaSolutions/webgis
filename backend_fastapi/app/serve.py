"""Jalankan API dashboard (HTTP) dan, bila sertifikat ada, listener mTLS (HTTPS).

Proses HTTP tidak memasang pemeriksaan sertifikat, jadi dashboard tetap memakai
http://127.0.0.1:8000. Proses HTTPS memasang MTLS_ENFORCE sebelum aplikasi dimuat.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def _https_enabled() -> bool:
    from app.core.mtls import certificate_files_ready

    return certificate_files_ready()


def run_http() -> None:
    import uvicorn

    from app.core.config import settings

    uvicorn.run(
        "app.main:app",
        host=settings.HTTP_HOST,
        port=settings.HTTP_PORT,
        proxy_headers=True,
    )


def run_https() -> None:
    os.environ["MTLS_ENFORCE"] = "true"
    import uvicorn

    from app.core.config import settings
    from app.core.mtls import build_ssl_context, install_peer_cert_scope
    from app.main import app

    if not _https_enabled():
        missing = ", ".join((settings.MTLS_CERTFILE, settings.MTLS_KEYFILE, settings.MTLS_CA_FILE))
        print(f"mTLS tidak dijalankan: file sertifikat belum lengkap ({missing}).", file=sys.stderr)
        raise SystemExit(1)

    install_peer_cert_scope()
    context = build_ssl_context(settings.MTLS_CERTFILE, settings.MTLS_KEYFILE, settings.MTLS_CA_FILE)
    config = uvicorn.Config(
        app,
        host=settings.MTLS_HOST,
        port=settings.MTLS_PORT,
        proxy_headers=False,
        lifespan="on",
    )
    server = _MtlsServer(config, context)
    server.run()


class _MtlsServer:
    """Pasang SSLContext setelah Uvicorn memuat aplikasi, tanpa cipher bawaan TLSv1."""

    def __init__(self, config, ssl_context) -> None:
        import uvicorn

        self._server = uvicorn.Server(config)
        self._ssl_context = ssl_context

    def run(self) -> None:
        original = self._server._serve

        async def _serve(sockets=None):
            if not self._server.config.loaded:
                self._server.config.load()
            self._server.config.ssl = self._ssl_context
            await original(sockets)

        self._server._serve = _serve
        self._server.run()


def _spawn(mode: str, enforce: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["MTLS_ENFORCE"] = enforce
    return subprocess.Popen([sys.executable, "-m", "app.serve", mode], env=env)


def _stop(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def supervise() -> None:
    processes = [_spawn("http", "false")]
    if _https_enabled():
        processes.append(_spawn("https", "true"))
    else:
        from app.core.config import settings

        print(
            "mTLS tidak dijalankan: sertifikat server belum ada. "
            f"Letakkan {settings.MTLS_CERTFILE}, {settings.MTLS_KEYFILE}, dan {settings.MTLS_CA_FILE} "
            "atau jalankan scripts/generate_mtls_certs.sh.",
            file=sys.stderr,
        )

    stopping = False

    def handle_exit(signum, _frame) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        _stop(processes)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    exit_code = 0
    while not stopping:
        finished = next((process for process in processes if process.poll() is not None), None)
        if finished is not None:
            exit_code = finished.returncode or 1
            stopping = True
            _stop(processes)
            break
        time.sleep(0.3)
    raise SystemExit(exit_code)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "supervise"
    if mode == "http":
        run_http()
        return
    if mode == "https":
        run_https()
        return
    supervise()


if __name__ == "__main__":
    main()
