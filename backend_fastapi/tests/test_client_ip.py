"""Trusted-proxy: XFF hanya dipercaya dari peer di TRUSTED_PROXY_CIDRS."""
from app.core.client_ip import resolve_client_ip
from app.core.config import settings


def test_ignore_xff_when_no_trusted_cidrs(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "")
    # Peer = HAProxy private; tanpa allowlist, jangan pakai XFF spoof
    assert resolve_client_ip("172.18.0.5", "8.8.8.8", None) == "172.18.0.5"


def test_trust_xff_from_docker_bridge_peer(monkeypatch):
    monkeypatch.setattr(
        settings, "TRUSTED_PROXY_CIDRS", "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    )
    assert resolve_client_ip("172.18.0.5", "203.0.113.9", None) == "203.0.113.9"


def test_untrusted_peer_ignores_xff(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    assert resolve_client_ip("203.0.113.50", "8.8.8.8", None) == "203.0.113.50"
