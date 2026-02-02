import pytest

from trustora.signer_keys import select_private_key


def test_select_private_key():
    mapping = {"addr1": "key1", "addr2": "key2"}
    assert select_private_key("addr2", mapping) == "key2"
    with pytest.raises(KeyError):
        select_private_key("missing", mapping)
