from __future__ import annotations

import argparse
from pathlib import Path

from trustora.security import encrypt_secret


def main() -> None:
    parser = argparse.ArgumentParser(description="Encrypt a private key into a blob file.")
    parser.add_argument("--key", required=True, help="Plaintext private key or JSON list of keys.")
    parser.add_argument("--out", required=True, help="Output path for encrypted blob.")
    parser.add_argument("--encryption-key", required=True, help="Encryption key from env.")
    args = parser.parse_args()

    encrypted = encrypt_secret(args.key, args.encryption_key)
    Path(args.out).write_bytes(encrypted)
    print(f"Encrypted key written to {args.out}")


if __name__ == "__main__":
    main()
