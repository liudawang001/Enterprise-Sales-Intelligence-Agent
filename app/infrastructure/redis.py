from __future__ import annotations


class RedisManager:
    def __init__(
        self,
        url: str,
        *,
        max_connections: int = 20,
        socket_timeout: float = 2.0,
        socket_connect_timeout: float = 2.0,
    ) -> None:
        self.url = url
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.client = None

    async def start(self):
        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise RuntimeError("redis package is not installed") from exc
        self.client = Redis.from_url(
            self.url,
            max_connections=self.max_connections,
            decode_responses=False,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            health_check_interval=15,
        )
        await self.client.ping()
        return self.client

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None
