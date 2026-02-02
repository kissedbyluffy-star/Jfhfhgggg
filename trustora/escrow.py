from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trustora.enums import EscrowStatus
from trustora.models import Escrow
from trustora.state_machine import validate_transition


async def get_escrow_for_update(session: AsyncSession, escrow_id) -> Escrow:
    result = await session.execute(
        select(Escrow).where(Escrow.id == escrow_id).with_for_update()
    )
    escrow = result.scalar_one()
    return escrow


async def transition_escrow(
    session: AsyncSession,
    escrow: Escrow,
    new_status: EscrowStatus,
) -> Escrow:
    validate_transition(escrow.status, new_status)
    escrow.status = new_status
    escrow.updated_at = datetime.utcnow()
    session.add(escrow)
    return escrow
