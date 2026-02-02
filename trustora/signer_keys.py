from __future__ import annotations

from collections.abc import Callable


def build_address_key_map(keys: list[str], address_from_key: Callable[[str], str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for key in keys:
        address = address_from_key(key)
        mapping[address] = key
    return mapping


def select_private_key(address: str, mapping: dict[str, str]) -> str:
    if address not in mapping:
        raise KeyError(f"No key for address {address}")
    return mapping[address]
