"""Alamat IP klien untuk kolom audit.user_activities.ip_address (tipe inet)."""
import ipaddress
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

_client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)
_FALLBACK = "127.0.0.1"


def current_client_ip() -> str:
    """IP permintaan yang sedang berjalan. 127.0.0.1 hanya jika socket tidak punya alamat."""
    return _client_ip.get() or _FALLBACK


def _parse_ip(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip()
    if not token or token.lower() == "unknown":
        return None
    if token.startswith("[") and "]" in token:
        token = token[1:token.index("]")]
    elif token.count(":") == 1 and "." in token:
        token = token.split(":", 1)[0]
    try:
        return str(ipaddress.ip_address(token))
    except ValueError:
        return None


def _is_routable(ip: str) -> bool:
    address = ipaddress.ip_address(ip)
    return not (address.is_loopback or address.is_private or address.is_link_local or address.is_unspecified)


def _header(scope: Scope, name: str) -> str | None:
    target = name.lower().encode("latin-1")
    for key, value in scope.get("headers") or []:
        if key.lower() == target:
            return value.decode("latin-1")
    return None


def resolve_client_ip(client_host: str | None, forwarded_for: str | None, real_ip: str | None) -> str:
    peer = _parse_ip(client_host)
    if peer and _is_routable(peer):
        return peer

    for part in (forwarded_for or "").split(","):
        parsed = _parse_ip(part)
        if parsed and _is_routable(parsed):
            return parsed

    real = _parse_ip(real_ip)
    if real and _is_routable(real):
        return real
    if peer:
        return peer
    if real:
        return real
    forwarded = _parse_ip((forwarded_for or "").split(",")[0])
    return forwarded or _FALLBACK


class ClientIpMiddleware:
    """Simpan IP klien di context agar endpoint sinkron tetap membacanya."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        host = client[0] if client else None
        ip = resolve_client_ip(host, _header(scope, "x-forwarded-for"), _header(scope, "x-real-ip"))
        token = _client_ip.set(ip)
        try:
            await self.app(scope, receive, send)
        finally:
            _client_ip.reset(token)
