from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timezone


def derive_fernet_key(raw_key: str) -> bytes:
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plaintext: str, raw_key: str) -> bytes:
    from cryptography.fernet import Fernet

    fernet = Fernet(derive_fernet_key(raw_key))
    return fernet.encrypt(plaintext.encode("utf-8"))


def decrypt_secret(ciphertext: bytes, raw_key: str) -> str:
    from cryptography.fernet import Fernet

    fernet = Fernet(derive_fernet_key(raw_key))
    return fernet.decrypt(ciphertext).decode("utf-8")


def generate_nonce() -> str:
    return base64.urlsafe_b64encode(os.urandom(18)).decode("utf-8")


def sign_hmac(secret: str, message: str) -> str:
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac(secret: str, message: str, signature: str) -> bool:
    expected = sign_hmac(secret, message)
    return hmac.compare_digest(expected, signature)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SignedRequest:
    escrow_id: str
    chain: str
    payout_address: str
    amount: float
    timestamp: int
    nonce: str
    signature: str

    def message(self) -> str:
        return (
            f"{self.escrow_id}|{self.chain}|{self.payout_address}|"
            f"{self.amount}|{self.timestamp}|{self.nonce}"
        )
