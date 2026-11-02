"""
Klien Redis cache peta: pool penuh tidak boleh membuat Redis dianggap mati.

Dulu pool biasa (max 20) melempar "Too many connections" saat satu layar meminta ~30 ubin foto udara serentak;
mark_down lalu mematikan seluruh cache 30 dtk. Test memakai server Redis tiruan (RESP minimal) di port acak.
"""
import asyncio

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import redis_client
from app.core.config import settings


async def _fake_redis_server():
    store: dict[bytes, bytes] = {}

    async def handle(reader, writer):
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                args = []
                for _ in range(int(line[1:])):
                    size = int((await reader.readline())[1:])
                    args.append((await reader.readexactly(size + 2))[:-2])
                await asyncio.sleep(0.02)  # jawaban sedikit lambat, seperti lewat jaringan
                cmd = args[0].upper()
                if cmd == b"GET":
                    value = store.get(args[1])
                    writer.write(b"$-1\r\n" if value is None else b"$%d\r\n%s\r\n" % (len(value), value))
                elif cmd == b"SET":
                    store[args[1]] = args[2]
                    writer.write(b"+OK\r\n")
                else:
                    writer.write(b"+PONG\r\n" if cmd == b"PING" else b"+OK\r\n")
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


@pytest.fixture()
def fresh_client_state(monkeypatch):
    monkeypatch.setattr(redis_client, "_client", None)
    monkeypatch.setattr(redis_client, "_override", None)
    monkeypatch.setattr(redis_client, "_down_until", 0.0)
    monkeypatch.setattr(settings, "REDIS_MAP_ENABLED", True)


def test_pool_penuh_dikenali():
    assert redis_client.is_pool_busy(RedisConnectionError("Too many connections"))
    assert redis_client.is_pool_busy(RedisConnectionError("No connection available."))
    assert not redis_client.is_pool_busy(RedisConnectionError("Error 10061 connecting to 127.0.0.1:6379."))
    assert not redis_client.is_pool_busy(TimeoutError("timeout"))
    assert not redis_client.is_pool_busy(None)


def test_permintaan_serentak_melebihi_pool_tetap_lewat_cache(fresh_client_state, monkeypatch):
    asyncio.run(_serentak_melebihi_pool(monkeypatch))


async def _serentak_melebihi_pool(monkeypatch):
    server, port = await _fake_redis_server()
    monkeypatch.setattr(settings, "REDIS_URL", f"redis://127.0.0.1:{port}/0")
    monkeypatch.setattr(settings, "REDIS_MAX_CONNECTIONS", 5)
    try:
        client = await redis_client.get_client()
        assert client is not None
        await client.set(b"ubin", b"jpeg")
        # 30 GET serentak dengan pool 5: menunggu giliran, tidak ada "Too many connections".
        values = await asyncio.gather(*[client.get(b"ubin") for _ in range(30)])
        assert values == [b"jpeg"] * 30
        assert redis_client._client is client and redis_client._down_until == 0.0
    finally:
        await redis_client.shutdown()
        server.close()


def test_mark_down_pool_penuh_tidak_mematikan_cache(fresh_client_state):
    asyncio.run(_mark_down_pool_penuh())


async def _mark_down_pool_penuh():
    class FakeClient:
        closed = False

        async def aclose(self):
            self.closed = True

    client = FakeClient()
    redis_client._client = client
    await redis_client.mark_down(client, RedisConnectionError("No connection available."))
    assert redis_client._client is client and not client.closed and redis_client._down_until == 0.0

    await redis_client.mark_down(client, RedisConnectionError("Connection reset by peer"))
    assert redis_client._client is None and client.closed and redis_client._down_until > 0
