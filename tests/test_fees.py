from trustora.fees import DEFAULT_FEE_SNAPSHOT, calculate_fee, calculate_net


def test_fee_calc_flat():
    assert calculate_fee(50, DEFAULT_FEE_SNAPSHOT) == 5.0
    assert calculate_net(50, DEFAULT_FEE_SNAPSHOT) == 45.0


def test_fee_calc_percent():
    assert calculate_fee(200, DEFAULT_FEE_SNAPSHOT) == 4.0
    assert calculate_net(200, DEFAULT_FEE_SNAPSHOT) == 196.0
