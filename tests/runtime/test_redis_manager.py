from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from app.infrastructure.redis import RedisManager


@pytest.mark.asyncio
async def test_redis_manager_configures_bounded_socket_timeouts(monkeypatch) -> None:
    captured: dict = {}
    client = AsyncMock()

    def fake_from_url(url: str, **kwargs):
        captured.update({"url": url, **kwargs})
        return client

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    manager = RedisManager(
        "redis://127.0.0.1:6380/15",
        max_connections=7,
        socket_timeout=1.25,
        socket_connect_timeout=0.75,
    )

    assert await manager.start() is client
    client.ping.assert_awaited_once()
    assert captured == {
        "url": "redis://127.0.0.1:6380/15",
        "max_connections": 7,
        "decode_responses": False,
        "socket_timeout": 1.25,
        "socket_connect_timeout": 0.75,
        "health_check_interval": 15,
    }
