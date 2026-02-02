from decimal import Decimal

from trustora.fees import DEFAULT_FEE_SNAPSHOT, calculate_fee, calculate_net


def test_fee_calc_flat():
    assert calculate_fee(Decimal("50"), DEFAULT_FEE_SNAPSHOT) == Decimal("5.000000")
    assert calculate_net(Decimal("50"), DEFAULT_FEE_SNAPSHOT) == Decimal("45.000000")


def test_fee_calc_percent():
    assert calculate_fee(Decimal("200"), DEFAULT_FEE_SNAPSHOT) == Decimal("4.000000")
    assert calculate_net(Decimal("200"), DEFAULT_FEE_SNAPSHOT) == Decimal("196.000000")
