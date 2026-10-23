"""mTLS untuk pemanggilan dari backend-external.

Uvicorn 0.29 tidak menaruh objek SSL di scope ASGI. `install_peer_cert_scope`
menyalin `ssl_object` ke scope sebelum aplikasi membaca sertifikat klien.
Mode verifikasi server adalah CERT_OPTIONAL: endpoint di luar prefix yang
dilindungi tetap bisa dipanggil tanpa sertifikat klien.
"""
from __future__ import annotations

import ssl
from pathlib import Path

from fastapi import HTTPException, Request, status
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.exceptions import error_body


def certificate_files_ready() -> bool:
    if not settings.MTLS_ENABLED:
        return False
    return all(
        Path(path).is_file()
        for path in (settings.MTLS_CERTFILE, settings.MTLS_KEYFILE, settings.MTLS_CA_FILE)
    )


def build_ssl_context(certfile: str, keyfile: str, ca_file: str) -> ssl.SSLContext:
    """Konteks TLS server: sertifikat backend-webgis, CA klien, verifikasi opsional."""
    for label, path in (("sertifikat server", certfile), ("kunci server", keyfile), ("CA", ca_file)):
        if not Path(path).is_file():
            raise FileNotFoundError(f"File {label} mTLS tidak ditemukan: {path}")

    context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    context.load_verify_locations(cafile=ca_file)
    context.verify_mode = ssl.CERT_OPTIONAL
    return context


def install_peer_cert_scope() -> None:
    """Salin sertifikat peer ke `scope['ssl_object']` untuk httptools dan h11."""
    from uvicorn.protocols.http.h11_impl import RequestResponseCycle as H11Cycle
    from uvicorn.protocols.http.httptools_impl import RequestResponseCycle as ToolsCycle

    def wrap(cycle_cls) -> None:
        if getattr(cycle_cls.run_asgi, "_mtls_wrapped", False):
            return
        original = cycle_cls.run_asgi

        async def run_asgi(self, app):
            ssl_object = self.transport.get_extra_info("ssl_object")
            if ssl_object is not None:
                self.scope["ssl_object"] = ssl_object
            return await original(self, app)

        run_asgi._mtls_wrapped = True  # type: ignore[attr-defined]
        cycle_cls.run_asgi = run_asgi

    wrap(H11Cycle)
    wrap(ToolsCycle)


def path_requires_client_cert(path: str, prefixes: list[str]) -> bool:
    for prefix in prefixes:
        normalized = prefix.strip().rstrip("/")
        if not normalized:
            continue
        if path == normalized or path.startswith(normalized + "/"):
            return True
    return False


def _denied(status_code: int, type_: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=error_body(message, type_=type_, field="client_certificate"),
    )


def assert_allowed_client(ssl_object, allowed_cns: list[str]) -> str:
    """Periksa HTTPS, keberadaan sertifikat klien, dan Common Name yang diizinkan."""
    if ssl_object is None:
        raise _denied(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Akses ditolak: Wajib menggunakan koneksi HTTPS.",
        )

    try:
        client_cert = ssl_object.getpeercert()
    except ssl.SSLError:
        client_cert = None
    if not client_cert:
        raise _denied(
            status.HTTP_401_UNAUTHORIZED,
            "unauthorized",
            "Akses ditolak: Sertifikat klien tidak ditemukan.",
        )

    subject = client_cert.get("subject", ())
    try:
        subject_dict = dict(item[0] for item in subject)
    except (TypeError, ValueError, IndexError):
        subject_dict = {}
    common_name = subject_dict.get("commonName")
    if common_name not in allowed_cns:
        raise _denied(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            f"Akses ditolak: Sertifikat dengan CN '{common_name}' tidak memiliki izin.",
        )
    return common_name


def verify_client_certificate(request: Request) -> str:
    """Dependency endpoint yang hanya boleh dipanggil backend-external."""
    return assert_allowed_client(request.scope.get("ssl_object"), settings.MTLS_ALLOWED_CN_LIST)


class MtlsGuardMiddleware:
    """Tolak path terdaftar pada listener HTTPS bila sertifikat klien tidak sah."""

    def __init__(
        self,
        app: ASGIApp,
        required_prefixes: list[str] | None = None,
        allowed_cns: list[str] | None = None,
    ) -> None:
        self.app = app
        self.required_prefixes = (
            settings.MTLS_REQUIRED_PATH_LIST if required_prefixes is None else required_prefixes
        )
        self.allowed_cns = settings.MTLS_ALLOWED_CN_LIST if allowed_cns is None else allowed_cns

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not path_requires_client_cert(
            scope.get("path", ""), self.required_prefixes
        ):
            await self.app(scope, receive, send)
            return
        try:
            assert_allowed_client(scope.get("ssl_object"), self.allowed_cns)
        except HTTPException as exc:
            response = JSONResponse(status_code=exc.status_code, content=exc.detail)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
