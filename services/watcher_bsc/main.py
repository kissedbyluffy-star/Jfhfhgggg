from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy import select
from web3 import Web3
from web3.middleware import geth_poa_middleware

from trustora.enums import Chain, EscrowStatus
from trustora.escrow import get_escrow_for_update, transition_escrow
from trustora.idempotency import can_record_deposit
from trustora.db import create_engine, create_session_factory
from trustora.models import Escrow
from services.watcher_bsc.settings import load_settings

logging.basicConfig(level=logging.INFO)

TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()


def build_web3(rpc_url: str) -> Web3:
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return web3


def parse_transfer(log) -> tuple[str, str, int]:
    from_addr = "0x" + log["topics"][1].hex()[-40:]
    to_addr = "0x" + log["topics"][2].hex()[-40:]
    amount = int(log["data"], 16)
    return Web3.to_checksum_address(from_addr), Web3.to_checksum_address(to_addr), amount


async def scan_loop() -> None:
    settings = load_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    rpc_urls = settings.bsc_rpc_urls.split(",")

    while True:
        try:
            await scan_once(settings, session_factory, redis, rpc_urls)
        except Exception as exc:  # pragma: no cover
            logging.error("scan error: %s", exc)
        await asyncio.sleep(settings.scan_interval_seconds)


async def scan_once(settings, session_factory, redis: Redis, rpc_urls: list[str]) -> None:
    web3 = build_web3(rpc_urls[0])
    latest_block = web3.eth.block_number
    last_block = int(await redis.get("bsc:last_block") or 0)
    from_block = max(latest_block - 500, last_block + 1)
    to_block = latest_block

    async with session_factory() as session:
        result = await session.execute(
            select(Escrow).where(
                Escrow.chain == Chain.BEP20,
                Escrow.status.in_([EscrowStatus.AWAITING_DEPOSIT, EscrowStatus.UNDERPAID]),
            )
        )
        escrows = result.scalars().all()

    if not escrows:
        await redis.set("bsc:last_block", to_block)
        return

    addresses = {Web3.to_checksum_address(e.deposit_address) for e in escrows}
    logs = web3.eth.get_logs(
        {
            "fromBlock": from_block,
            "toBlock": to_block,
            "address": Web3.to_checksum_address(settings.bsc_usdt_contract),
            "topics": [TRANSFER_TOPIC],
        }
    )
    for log in logs:
        _, to_addr, amount = parse_transfer(log)
        if to_addr not in addresses:
            continue
        escrow = next(e for e in escrows if Web3.to_checksum_address(e.deposit_address) == to_addr)
        confirmations = latest_block - log["blockNumber"]
        if confirmations < settings.bsc_confirmations_required:
            continue
        await update_escrow(session_factory, escrow.id, log["transactionHash"].hex(), amount)

    await redis.set("bsc:last_block", to_block)


async def update_escrow(session_factory, escrow_id, tx_hash: str, amount_raw: int) -> None:
    amount = round(amount_raw / 1_000_000, 2)
    async with session_factory() as session:
        async with session.begin():
            escrow = await get_escrow_for_update(session, escrow_id)
            if not can_record_deposit(escrow, tx_hash):
                return
            escrow.deposit_tx_hash = tx_hash
            escrow.amount_received = amount
            escrow.deposit_confirmations = None
            if amount < escrow.amount_expected:
                await transition_escrow(session, escrow, EscrowStatus.UNDERPAID)
            elif amount > escrow.amount_expected:
                await transition_escrow(session, escrow, EscrowStatus.OVERPAID_REVIEW)
            else:
                await transition_escrow(session, escrow, EscrowStatus.FUNDS_LOCKED)


if __name__ == "__main__":
    asyncio.run(scan_loop())
