from __future__ import annotations

import asyncio
import logging
import time

from redis.asyncio import Redis
from sqlalchemy import select
from tronpy import Tron
from tronpy.providers import HTTPProvider

from trustora.amounts import quantize_amount
from trustora.deposits import deposit_status_sequence
from trustora.enums import Chain, EscrowStatus
from trustora.escrow import get_escrow_for_update, transition_escrow
from trustora.idempotency import can_record_deposit
from trustora.db import create_engine, create_session_factory
from trustora.models import Escrow
from services.watcher_tron.settings import load_settings

logging.basicConfig(level=logging.INFO)


async def scan_loop() -> None:
    settings = load_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    rpc_urls = settings.tron_rpc_urls.split(",")

    while True:
        try:
            await scan_once(settings, session_factory, redis, rpc_urls)
        except Exception as exc:  # pragma: no cover
            logging.error("scan error: %s", exc)
        await asyncio.sleep(settings.scan_interval_seconds)


async def scan_once(settings, session_factory, redis: Redis, rpc_urls: list[str]) -> None:
    client = Tron(provider=HTTPProvider(rpc_urls[0]))
    latest_block = client.get_latest_block_number()
    last_block = int(await redis.get("tron:last_block") or 0)
    last_rescan = float(await redis.get("tron:last_rescan") or 0)
    now = time.time()
    if now - last_rescan >= settings.rescan_interval_seconds:
        from_block = max(latest_block - 5000, 0)
        await redis.set("tron:last_rescan", now)
    else:
        from_block = max(latest_block - 500, last_block + 1)
    to_block = latest_block

    async with session_factory() as session:
        result = await session.execute(
            select(Escrow).where(
                Escrow.chain == Chain.TRC20,
                Escrow.status.in_([EscrowStatus.AWAITING_DEPOSIT, EscrowStatus.UNDERPAID]),
            )
        )
        escrows = result.scalars().all()

    if not escrows:
        await redis.set("tron:last_block", to_block)
        return

    contract = client.get_contract(settings.tron_usdt_contract)
    logs = contract.get_event_logs(event_name="Transfer", since=from_block, stop=to_block)
    addresses = {e.deposit_address for e in escrows}

    for log in logs:
        to_addr = log["result"]["to"]
        amount = int(log["result"]["value"]) / 1_000_000
        if to_addr not in addresses:
            continue
        confirmations = latest_block - log["block_number"]
        if confirmations < settings.tron_confirmations_required:
            continue
        escrow = next(e for e in escrows if e.deposit_address == to_addr)
        await update_escrow(
            session_factory,
            escrow.id,
            log["transaction_id"],
            amount,
            confirmations,
        )

    await redis.set("tron:last_block", to_block)


async def update_escrow(
    session_factory,
    escrow_id,
    tx_hash: str,
    amount: float,
    confirmations: int,
) -> None:
    amount = quantize_amount(amount)
    async with session_factory() as session:
        async with session.begin():
            escrow = await get_escrow_for_update(session, escrow_id)
            if not can_record_deposit(escrow, tx_hash):
                return
            escrow.deposit_tx_hash = tx_hash
            escrow.amount_received = amount
            escrow.deposit_confirmations = confirmations
            for status in deposit_status_sequence(amount, escrow.amount_expected):
                await transition_escrow(session, escrow, status)


if __name__ == "__main__":
    asyncio.run(scan_loop())
