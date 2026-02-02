from __future__ import annotations

import time
from typing import Protocol

from trustora.security import verify_hmac


def verify_timestamp(timestamp: int) -> None:
    now = int(time.time())
    if abs(now - timestamp) > 60:
        raise ValueError("Timestamp expired")


class RedisLike(Protocol):
    async def setnx(self, key: str, value: str) -> bool: ...
    async def expire(self, key: str, ttl: int) -> bool: ...


async def verify_nonce(redis: RedisLike, nonce: str) -> None:
    key = f"nonce:{nonce}"
    exists = await redis.setnx(key, "1")
    if not exists:
        raise ValueError("Replay detected")
    await redis.expire(key, 120)


def verify_signature(secret: str, message: str, signature: str) -> None:
    if not verify_hmac(secret, message, signature):
        raise ValueError("Invalid signature")
