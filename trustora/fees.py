from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trustora.amounts import quantize_amount, to_decimal

@dataclass(frozen=True)
class FeeSnapshot:
    flat_fee: Decimal
    percent_fee: Decimal
    threshold: Decimal


DEFAULT_FEE_SNAPSHOT = FeeSnapshot(
    flat_fee=Decimal("5"),
    percent_fee=Decimal("0.02"),
    threshold=Decimal("100"),
)


def calculate_fee(amount_received: Decimal, snapshot: FeeSnapshot) -> Decimal:
    amount = to_decimal(amount_received)
    if amount <= snapshot.threshold:
        return quantize_amount(snapshot.flat_fee)
    return quantize_amount(amount * snapshot.percent_fee)


def calculate_net(amount_received: Decimal, snapshot: FeeSnapshot) -> Decimal:
    fee = calculate_fee(amount_received, snapshot)
    return quantize_amount(to_decimal(amount_received) - fee)
