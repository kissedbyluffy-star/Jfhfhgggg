from __future__ import annotations

from decimal import Decimal

from trustora.amounts import quantize_amount
from trustora.enums import EscrowStatus


def deposit_status_sequence(amount_received: Decimal, amount_expected: Decimal) -> list[EscrowStatus]:
    amount = quantize_amount(amount_received)
    expected = quantize_amount(amount_expected)
    if amount < expected:
        return [EscrowStatus.DEPOSIT_SEEN, EscrowStatus.UNDERPAID]
    if amount > expected:
        return [EscrowStatus.DEPOSIT_SEEN, EscrowStatus.OVERPAID_REVIEW]
    return [EscrowStatus.DEPOSIT_SEEN, EscrowStatus.FUNDS_LOCKED]
