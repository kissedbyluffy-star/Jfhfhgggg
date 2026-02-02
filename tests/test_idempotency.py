from trustora.idempotency import can_record_deposit, can_send_payout
class DummyEscrow:
    def __init__(self):
        self.deposit_tx_hash = None
        self.payout_tx_hash = None


def make_escrow():
    return DummyEscrow()


def test_deposit_idempotency():
    escrow = make_escrow()
    assert can_record_deposit(escrow, "tx1")
    escrow.deposit_tx_hash = "tx1"
    assert can_record_deposit(escrow, "tx1")
    assert not can_record_deposit(escrow, "tx2")


def test_payout_idempotency():
    escrow = make_escrow()
    assert can_send_payout(escrow)
    escrow.payout_tx_hash = "tx1"
    assert not can_send_payout(escrow)
