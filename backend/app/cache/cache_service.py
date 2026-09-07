"""Cache service with TTL and invalidation helpers."""

import json
from typing import Any

from app.cache.redis import get_redis


class CacheService:
    @staticmethod
    async def get(key: str) -> Any | None:
        redis = await get_redis()
        value = await redis.get(key)
        if value:
            return json.loads(value)
        return None

    @staticmethod
    async def set(key: str, value: Any, ttl_seconds: int = 300) -> None:
        redis = await get_redis()
        await redis.set(key, json.dumps(value, default=str), ex=ttl_seconds)

    @staticmethod
    async def delete(key: str) -> None:
        redis = await get_redis()
        await redis.delete(key)

    @staticmethod
    async def delete_pattern(pattern: str) -> None:
        redis = await get_redis()
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)