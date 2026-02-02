from __future__ import annotations

import argparse
from pathlib import Path

from trustora.security import decrypt_secret


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify decryption without printing secrets.")
    parser.add_argument("--file", required=True, help="Encrypted blob file path.")
    parser.add_argument("--encryption-key", required=True, help="Encryption key from env.")
    args = parser.parse_args()

    data = Path(args.file).read_bytes()
    _ = decrypt_secret(data, args.encryption_key)
    print("Decryption succeeded.")


if __name__ == "__main__":
    main()
