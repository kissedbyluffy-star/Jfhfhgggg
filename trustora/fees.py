from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeSnapshot:
    flat_fee: float
    percent_fee: float
    threshold: float


DEFAULT_FEE_SNAPSHOT = FeeSnapshot(flat_fee=5.0, percent_fee=0.02, threshold=100.0)


def calculate_fee(amount_received: float, snapshot: FeeSnapshot) -> float:
    if amount_received <= snapshot.threshold:
        return snapshot.flat_fee
    return round(amount_received * snapshot.percent_fee, 2)


def calculate_net(amount_received: float, snapshot: FeeSnapshot) -> float:
    fee = calculate_fee(amount_received, snapshot)
    return round(amount_received - fee, 2)
