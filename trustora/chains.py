from __future__ import annotations

import re

from trustora.enums import Chain


TRON_ADDRESS_RE = re.compile(r"^T[a-zA-Z0-9]{33}$")
BSC_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def validate_address(chain: Chain, address: str) -> bool:
    if chain == Chain.TRC20:
        return bool(TRON_ADDRESS_RE.match(address))
    if chain == Chain.BEP20:
        return bool(BSC_ADDRESS_RE.match(address))
    return False
