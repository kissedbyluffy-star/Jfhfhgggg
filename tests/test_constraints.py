def test_deposit_address_unique_constraint():
    content = open("trustora/models.py", "r", encoding="utf-8").read()
    assert "uq_chain_deposit_address" in content
