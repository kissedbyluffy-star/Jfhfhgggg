from decimal import Decimal

from trustora.deposits import deposit_status_sequence
from trustora.enums import EscrowStatus


def test_deposit_sequence_includes_seen():
    sequence = deposit_status_sequence(Decimal("10"), Decimal("10"))
    assert sequence[0] == EscrowStatus.DEPOSIT_SEEN
    assert sequence[1] == EscrowStatus.FUNDS_LOCKED
