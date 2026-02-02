from __future__ import annotations

import hashlib


def user_public_hash(tg_id: int, salt: str) -> str:
    digest = hashlib.sha256(f"{tg_id}:{salt}".encode("utf-8")).hexdigest()
    return f"U#{digest[:4].upper()}"


def mask_room_code(room_code: str) -> str:
    if len(room_code) < 4:
        return room_code
    if "-" in room_code:
        prefix = room_code.split("-", 1)[0]
        return f"{prefix}-****{room_code[-2:]}"
    return f"{room_code[:2]}-****{room_code[-2:]}"


def amount_bucket(amount: float) -> str:
    if amount < 50:
        return "<50"
    if amount <= 100:
        return "50-100"
    if amount <= 250:
        return "100-250"
    if amount <= 500:
        return "250-500"
    return "500+"


def build_review_post(room_code: str, chain: str, amount: float, reviewer_hash: str, rating: int, comment: str) -> str:
    masked_code = mask_room_code(room_code)
    bucket = amount_bucket(amount)
    stars = "⭐" * rating
    return (
        "🛡 Trustora Verified Escrow ✅\n"
        f"Deal: {masked_code} | Chain: {chain} | Size: {bucket}\n"
        f"Reviewer: {reviewer_hash}\n"
        f"Rating: {stars}\n"
        f"Comment: \"{comment}\""
    )
