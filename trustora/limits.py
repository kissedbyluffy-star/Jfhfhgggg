from __future__ import annotations

from datetime import datetime, timezone

from decimal import Decimal

from redis.asyncio import Redis


async def check_and_track_limits(
    redis: Redis,
    amount: Decimal,
    auto_payout_max: float,
    hard_max_payout: float,
    daily_payout_max: float,
    payouts_per_hour_max: int,
) -> None:
    if amount > Decimal(str(hard_max_payout)):
        raise ValueError("Hard max payout exceeded")
    if amount > Decimal(str(auto_payout_max)):
        raise ValueError("Approval required")

    now = datetime.now(timezone.utc)
    day_key = f"payouts:day:{now:%Y%m%d}"
    hour_key = f"payouts:hour:{now:%Y%m%d%H}"

    amount_value = float(amount)
    day_total = await redis.incrbyfloat(day_key, amount_value)
    if day_total == amount_value:
        await redis.expire(day_key, 86400)
    if day_total > daily_payout_max:
        raise ValueError("Daily payout max exceeded")

    hour_count = await redis.incr(hour_key)
    if hour_count == 1:
        await redis.expire(hour_key, 3600)
    if hour_count > payouts_per_hour_max:
        raise ValueError("Hourly payout count exceeded")
