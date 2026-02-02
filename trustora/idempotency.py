from __future__ import annotations

from typing import Protocol


class EscrowLike(Protocol):
    deposit_tx_hash: str | None
    payout_tx_hash: str | None


def can_record_deposit(escrow: EscrowLike, tx_hash: str) -> bool:
    return escrow.deposit_tx_hash is None or escrow.deposit_tx_hash == tx_hash


def can_send_payout(escrow: EscrowLike) -> bool:
    return escrow.payout_tx_hash is None
