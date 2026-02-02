
def test_rescan_logic_present():
    tron = open("services/watcher_tron/main.py", "r", encoding="utf-8").read()
    bsc = open("services/watcher_bsc/main.py", "r", encoding="utf-8").read()
    assert "rescan_interval_seconds" in tron
    assert "rescan_interval_seconds" in bsc
    assert "last_rescan" in tron
    assert "last_rescan" in bsc
    assert "5000" in tron
    assert "5000" in bsc
