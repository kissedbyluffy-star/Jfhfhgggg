def test_bot_does_not_set_payout_sent_or_completed():
    content = open("app/main.py", "r", encoding="utf-8").read()
    start = content.index("async def approve_and_send_payout")
    section = content[start:]
    next_index = section.find("async def ", len("async def "))
    if next_index != -1:
        section = section[:next_index]
    assert "PAYOUT_SENT" not in section
    assert "COMPLETED" not in section
