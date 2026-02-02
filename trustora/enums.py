from enum import Enum


class Chain(str, Enum):
    TRC20 = "TRC20"
    BEP20 = "BEP20"


class Token(str, Enum):
    USDT = "USDT"


class EscrowStatus(str, Enum):
    CREATED = "CREATED"
    AWAITING_DEPOSIT = "AWAITING_DEPOSIT"
    DEPOSIT_SEEN = "DEPOSIT_SEEN"
    FUNDS_LOCKED = "FUNDS_LOCKED"
    RELEASE_REQUESTED = "RELEASE_REQUESTED"
    RELEASE_APPROVED = "RELEASE_APPROVED"
    PAYOUT_QUEUED = "PAYOUT_QUEUED"
    PAYOUT_SENT = "PAYOUT_SENT"
    COMPLETED = "COMPLETED"
    DISPUTED = "DISPUTED"
    REVIEW = "REVIEW"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    UNDERPAID = "UNDERPAID"
    OVERPAID_REVIEW = "OVERPAID_REVIEW"
    PAYOUT_FAILED = "PAYOUT_FAILED"


class MessageRole(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"
    SYSTEM = "system"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"


class DisputeStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ReviewRating(int, Enum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
