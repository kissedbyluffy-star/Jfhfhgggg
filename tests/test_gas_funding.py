
def test_address_endpoint_does_not_fund_gas():
    content = open("services/signer/main.py", "r", encoding="utf-8").read()
    start = content.index("async def handle_address")
    section = content[start:]
    next_index = section.find("async def ", len("async def "))
    if next_index != -1:
        section = section[:next_index]
    assert "fund_tron_gas" not in section
    assert "fund_bsc_gas" not in section


def test_payout_uses_gas_funded_key():
    content = open("services/signer/main.py", "r", encoding="utf-8").read()
    assert "gas_funded" in content
