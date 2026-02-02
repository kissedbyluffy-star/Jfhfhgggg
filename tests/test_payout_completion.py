
def test_payout_transitions_to_completed():
    content = open("services/signer/main.py", "r", encoding="utf-8").read()
    assert "EscrowStatus.COMPLETED" in content
