from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import web
from redis.asyncio import Redis
from sqlalchemy import select
from web3 import Web3
from web3.middleware import geth_poa_middleware
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import PrivateKey as TronPrivateKey

from trustora.amounts import quantize_amount, to_micro_units
from trustora.chains import validate_address
from trustora.db import create_engine, create_session_factory
from trustora.enums import Chain, EscrowStatus
from trustora.escrow import get_escrow_for_update, transition_escrow
from trustora.config_service import get_config
from trustora.idempotency import can_send_payout
from trustora.limits import check_and_track_limits
from trustora.models import Escrow
from trustora.security import decrypt_secret
from trustora.signer_keys import build_address_key_map, select_private_key
from trustora.signer_security import verify_nonce, verify_signature, verify_timestamp
from trustora.state_machine import validate_transition
from services.signer.settings import load_settings

logging.basicConfig(level=logging.INFO)


def load_key_list(path: str, encryption_key: str) -> list[str]:
    data = Path(path).read_bytes()
    decrypted = decrypt_secret(data, encryption_key)
    return json.loads(decrypted)


def tron_address_from_key(private_key: str) -> str:
    key = TronPrivateKey(bytes.fromhex(private_key))
    return key.public_key.to_base58check_address()


def bsc_address_from_key(private_key: str) -> str:
    return Web3().eth.account.from_key(private_key).address




async def handle_address(request: web.Request) -> web.Response:
    app = request.app
    payload = await request.json()
    chain = payload.get("chain")
    timestamp = int(payload.get("timestamp", 0))
    nonce = payload.get("nonce", "")
    signature = payload.get("signature", "")
    try:
        verify_timestamp(timestamp)
        await verify_nonce(app["redis"], nonce)
        message = f"address|{chain}|{timestamp}|{nonce}"
        verify_signature(app["settings"].signer_hmac_secret, message, signature)
    except ValueError as exc:
        raise web.HTTPUnauthorized(text=str(exc)) from exc

    if chain not in {Chain.TRC20.value, Chain.BEP20.value}:
        raise web.HTTPBadRequest(text="Unsupported chain")

    if chain == Chain.TRC20.value:
        address = await pick_address(app, Chain.TRC20)
        await fund_tron_gas(app, address)
    else:
        address = await pick_address(app, Chain.BEP20)
        await fund_bsc_gas(app, address)

    return web.json_response({"address": address})


async def pick_address(app: web.Application, chain: Chain) -> str:
    address_map = app["tron_address_map"] if chain == Chain.TRC20 else app["bsc_address_map"]
    async with app["session_factory"]() as session:
        result = await session.execute(select(Escrow.deposit_address).where(Escrow.chain == chain))
        used = {row[0] for row in result.fetchall()}
    for address in address_map.keys():
        if address not in used:
            return address
    raise web.HTTPServiceUnavailable(text="No deposit addresses available")


async def handle_payout(request: web.Request) -> web.Response:
    app = request.app
    payload: dict[str, Any] = await request.json()
    escrow_id = payload.get("escrow_id")
    chain = payload.get("chain")
    payout_address = payload.get("payout_address")
    amount_str = str(payload.get("amount"))
    amount = quantize_amount(amount_str)
    timestamp = int(payload.get("timestamp"))
    nonce = payload.get("nonce")
    signature = payload.get("signature")

    try:
        verify_timestamp(timestamp)
        await verify_nonce(app["redis"], nonce)
        message = f"{escrow_id}|{chain}|{payout_address}|{amount_str}|{timestamp}|{nonce}"
        verify_signature(app["settings"].signer_hmac_secret, message, signature)
    except ValueError as exc:
        raise web.HTTPUnauthorized(text=str(exc)) from exc

    if chain not in {Chain.TRC20.value, Chain.BEP20.value}:
        raise web.HTTPBadRequest(text="Unsupported chain")

    chain_enum = Chain(chain)
    if not validate_address(chain_enum, payout_address):
        raise web.HTTPBadRequest(text="Invalid payout address")

    await check_kill_switch(app)
    await check_and_track_limits(
        app["redis"],
        amount,
        app["settings"].auto_payout_max,
        app["settings"].hard_max_payout,
        app["settings"].daily_payout_max,
        app["settings"].payouts_per_hour_max,
    )

    async with app["session_factory"]() as session:
        async with session.begin():
            escrow = await get_escrow_for_update(session, escrow_id)
            if escrow.status not in {EscrowStatus.RELEASE_APPROVED, EscrowStatus.PAYOUT_QUEUED}:
                raise web.HTTPConflict(text="Escrow not approved")
            if not can_send_payout(escrow):
                return web.json_response(
                    {"seller_tx_hash": escrow.payout_tx_hash, "fee_tx_hash": escrow.fee_tx_hash}
                )
            if quantize_amount(escrow.net_amount) != amount:
                raise web.HTTPBadRequest(text="Amount mismatch")
            validate_transition(escrow.status, EscrowStatus.PAYOUT_QUEUED)
            await transition_escrow(session, escrow, EscrowStatus.PAYOUT_QUEUED)

    deposit_address = escrow.deposit_address
    if chain_enum == Chain.TRC20:
        private_key = select_private_key(deposit_address, app["tron_address_map"])
        seller_tx_hash = await send_tron_usdt(app, payout_address, escrow.net_amount, private_key)
        fee_tx_hash = None
        if quantize_amount(escrow.fee_amount) > 0:
            fee_tx_hash = await send_tron_usdt(
                app,
                app["settings"].fee_wallet_tron,
                escrow.fee_amount,
                private_key,
            )
    else:
        private_key = select_private_key(deposit_address, app["bsc_address_map"])
        seller_tx_hash = await send_bsc_usdt(app, payout_address, escrow.net_amount, private_key)
        fee_tx_hash = None
        if quantize_amount(escrow.fee_amount) > 0:
            fee_tx_hash = await send_bsc_usdt(
                app,
                app["settings"].fee_wallet_bsc,
                escrow.fee_amount,
                private_key,
            )

    async with app["session_factory"]() as session:
        async with session.begin():
            escrow = await get_escrow_for_update(session, escrow_id)
            escrow.payout_tx_hash = seller_tx_hash
            escrow.fee_tx_hash = fee_tx_hash
            await transition_escrow(session, escrow, EscrowStatus.PAYOUT_SENT)

    return web.json_response({"seller_tx_hash": seller_tx_hash, "fee_tx_hash": fee_tx_hash})


async def check_kill_switch(app: web.Application) -> None:
    if app["settings"].pause_payouts:
        raise web.HTTPServiceUnavailable(text="Payouts paused")
    async with app["session_factory"]() as session:
        async with session.begin():
            config = await get_config(session)
            if config.json.get("pause_payouts", False):
                raise web.HTTPServiceUnavailable(text="Payouts paused")


async def fund_tron_gas(app: web.Application, address: str) -> None:
    client = Tron(network="mainnet", provider=HTTPProvider(app["tron_rpc"][0]))
    gas_key = TronPrivateKey(bytes.fromhex(app["tron_gas_key"]))
    amount = to_micro_units(app["settings"].tron_gas_amount)
    txn = client.trx.transfer(gas_key.public_key.to_base58check_address(), address, amount).build().sign(gas_key)
    txn.broadcast()


async def fund_bsc_gas(app: web.Application, address: str) -> None:
    web3 = Web3(Web3.HTTPProvider(app["bsc_rpc"][0]))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    acct = web3.eth.account.from_key(app["bsc_gas_key"])
    nonce = web3.eth.get_transaction_count(acct.address)
    txn = {
        "to": address,
        "value": web3.to_wei(app["settings"].bsc_gas_amount, "ether"),
        "gas": 21000,
        "gasPrice": web3.eth.gas_price,
        "nonce": nonce,
        "chainId": web3.eth.chain_id,
    }
    signed = acct.sign_transaction(txn)
    web3.eth.send_raw_transaction(signed.rawTransaction)


async def send_tron_usdt(app: web.Application, address: str, amount: float, private_key: str) -> str:
    client = Tron(network="mainnet", provider=HTTPProvider(app["tron_rpc"][0]))
    contract = client.get_contract(app["settings"].tron_usdt_contract)
    key = TronPrivateKey(bytes.fromhex(private_key))
    txn = (
        contract.functions.transfer(address, to_micro_units(amount))
        .with_owner(key.public_key.to_base58check_address())
        .fee_limit(10_000_000)
        .build()
        .sign(key)
    )
    result = txn.broadcast()
    return result["txid"]


async def send_bsc_usdt(app: web.Application, address: str, amount: float, private_key: str) -> str:
    web3 = Web3(Web3.HTTPProvider(app["bsc_rpc"][0]))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    acct = web3.eth.account.from_key(private_key)
    contract = web3.eth.contract(address=app["settings"].bsc_usdt_contract, abi=[
        {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        }
    ])
    nonce = web3.eth.get_transaction_count(acct.address)
    txn = contract.functions.transfer(address, to_micro_units(amount)).build_transaction(
        {
            "from": acct.address,
            "nonce": nonce,
            "gas": 120000,
            "gasPrice": web3.eth.gas_price,
        }
    )
    signed = acct.sign_transaction(txn)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
    return tx_hash.hex()


def create_app() -> web.Application:
    settings = load_settings()
    app = web.Application()
    app["settings"] = settings
    app["redis"] = Redis.from_url(settings.redis_url, decode_responses=True)
    app["session_factory"] = create_session_factory(create_engine(settings.database_url))
    tron_keys = load_key_list(settings.tron_key_file, settings.key_encryption_key)
    bsc_keys = load_key_list(settings.bsc_key_file, settings.key_encryption_key)
    app["tron_address_map"] = build_address_key_map(tron_keys, tron_address_from_key)
    app["bsc_address_map"] = build_address_key_map(bsc_keys, bsc_address_from_key)
    app["tron_gas_key"] = load_key_list(settings.tron_gas_key_file, settings.key_encryption_key)[0]
    app["bsc_gas_key"] = load_key_list(settings.bsc_gas_key_file, settings.key_encryption_key)[0]
    app["tron_rpc"] = settings.tron_rpc_urls.split(",")
    app["bsc_rpc"] = settings.bsc_rpc_urls.split(",")

    app.router.add_post("/address", handle_address)
    app.router.add_post("/payout", handle_payout)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080)
