from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

SCALE = Decimal("0.000001")


def to_decimal(value: str | float | int | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_amount(value: str | float | int | Decimal) -> Decimal:
    return to_decimal(value).quantize(SCALE, rounding=ROUND_DOWN)


def format_amount(value: str | float | int | Decimal) -> str:
    return f"{quantize_amount(value):.6f}"


def to_micro_units(value: str | float | int | Decimal) -> int:
    quantized = quantize_amount(value)
    return int((quantized * Decimal("1000000")).to_integral_value(rounding=ROUND_DOWN))
