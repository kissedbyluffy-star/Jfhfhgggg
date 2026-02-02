from trustora.chains import validate_address
from trustora.enums import Chain


def test_tron_address_validation():
    assert validate_address(Chain.TRC20, "T123") is False


def test_bsc_address_validation():
    assert validate_address(Chain.BEP20, "0x0000000000000000000000000000000000000000")
