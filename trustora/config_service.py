from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trustora.models import AuditLog, Config, ConfigHistory


DEFAULT_CONFIG = {
    "fee_flat": 5.0,
    "fee_percent": 0.02,
    "fee_threshold": 100.0,
    "pause_payouts": False,
}


def merge_config(base: dict, updates: dict) -> dict:
    merged = base.copy()
    merged.update(updates)
    return merged


async def get_config(session: AsyncSession) -> Config:
    result = await session.execute(select(Config).where(Config.id == 1))
    config = result.scalar_one_or_none()
    if config:
        return config
    config = Config(id=1, json=DEFAULT_CONFIG)
    session.add(config)
    return config


async def update_config(session: AsyncSession, actor_tg_id: int, updates: dict) -> Config:
    config = await get_config(session)
    old_json = config.json
    new_json = merge_config(old_json, updates)
    config.json = new_json
    session.add(config)
    session.add(
        ConfigHistory(
            changed_by=actor_tg_id,
            old_json=old_json,
            new_json=new_json,
            created_at=datetime.utcnow(),
        )
    )
    session.add(
        AuditLog(
            escrow_id=None,
            actor_tg_id=actor_tg_id,
            action="config.update",
            metadata_json={"updates": updates},
            created_at=datetime.utcnow(),
        )
    )
    return config
