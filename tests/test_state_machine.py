import pytest

from trustora.enums import EscrowStatus
from trustora.state_machine import validate_transition


def test_valid_transition():
    validate_transition(EscrowStatus.CREATED, EscrowStatus.AWAITING_DEPOSIT)


def test_invalid_transition():
    with pytest.raises(ValueError):
        validate_transition(EscrowStatus.CREATED, EscrowStatus.COMPLETED)
