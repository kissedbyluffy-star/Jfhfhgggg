from __future__ import annotations

from typing import Dict, Set

from trustora.enums import EscrowStatus


ALLOWED_TRANSITIONS: Dict[EscrowStatus, Set[EscrowStatus]] = {
    EscrowStatus.CREATED: {EscrowStatus.AWAITING_DEPOSIT, EscrowStatus.CANCELLED},
    EscrowStatus.AWAITING_DEPOSIT: {
        EscrowStatus.DEPOSIT_SEEN,
        EscrowStatus.EXPIRED,
        EscrowStatus.CANCELLED,
    },
    EscrowStatus.DEPOSIT_SEEN: {
        EscrowStatus.FUNDS_LOCKED,
        EscrowStatus.UNDERPAID,
        EscrowStatus.OVERPAID_REVIEW,
    },
    EscrowStatus.UNDERPAID: {EscrowStatus.AWAITING_DEPOSIT, EscrowStatus.CANCELLED},
    EscrowStatus.OVERPAID_REVIEW: {EscrowStatus.REVIEW},
    EscrowStatus.FUNDS_LOCKED: {
        EscrowStatus.RELEASE_REQUESTED,
        EscrowStatus.DISPUTED,
    },
    EscrowStatus.RELEASE_REQUESTED: {EscrowStatus.RELEASE_APPROVED, EscrowStatus.DISPUTED},
    EscrowStatus.RELEASE_APPROVED: {EscrowStatus.PAYOUT_QUEUED},
    EscrowStatus.PAYOUT_QUEUED: {EscrowStatus.PAYOUT_SENT, EscrowStatus.PAYOUT_FAILED},
    EscrowStatus.PAYOUT_SENT: {EscrowStatus.COMPLETED},
    EscrowStatus.COMPLETED: {EscrowStatus.REVIEW},
    EscrowStatus.DISPUTED: {EscrowStatus.REVIEW, EscrowStatus.RELEASE_APPROVED},
    EscrowStatus.REVIEW: {EscrowStatus.COMPLETED},
    EscrowStatus.EXPIRED: set(),
    EscrowStatus.CANCELLED: set(),
    EscrowStatus.PAYOUT_FAILED: {EscrowStatus.RELEASE_APPROVED},
}


def validate_transition(current: EscrowStatus, target: EscrowStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition {current} -> {target}")
