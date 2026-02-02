from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class RpcClient:
    urls: list[str]
    timeout: float = 10.0
    max_retries: int = 3
    backoff_seconds: float = 0.5

    async def post(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            for url in self.urls:
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(url, json=payload)
                        response.raise_for_status()
                        return response.json()
                except Exception as exc:  # pragma: no cover - network behavior
                    last_exc = exc
            await asyncio.sleep(self.backoff_seconds * (attempt + 1))
        raise RuntimeError("RPC request failed") from last_exc
