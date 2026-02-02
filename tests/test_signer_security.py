import asyncio
import time

from trustora.signer_security import verify_nonce, verify_timestamp
from trustora.security import sign_hmac, verify_hmac


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def setnx(self, key, value):
        if key in self.store:
            return False
        self.store[key] = value
        return True

    async def expire(self, key, ttl):
        return True


def test_hmac_roundtrip():
    message = "payload"
    secret = "secret"
    signature = sign_hmac(secret, message)
    assert verify_hmac(secret, message, signature)


def test_timestamp_fresh():
    now = int(time.time())
    verify_timestamp(now)


def test_timestamp_stale():
    stale = int(time.time()) - 120
    try:
        verify_timestamp(stale)
    except Exception:
        return
    raise AssertionError("Expected stale timestamp failure")


def test_nonce_replay_protection():
    redis = FakeRedis()

    async def run():
        await verify_nonce(redis, "abc")
        try:
            await verify_nonce(redis, "abc")
        except Exception:
            return True
        return False

    assert asyncio.run(run())
