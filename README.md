# Trustora Escrow

Trustora Escrow is a production-focused Telegram escrow system for USDT on TRC20 (default) and BEP20. It is designed for custodial safety, network isolation, and strict escrow state transitions.

## Architecture Summary
- **bot-api**: Telegram UI + business logic. No private keys.
- **watcher-tron**: TRC20 deposit detection. No private keys.
- **watcher-bsc**: BEP20 deposit detection. No private keys.
- **signer**: Only component with encrypted keys; signs & broadcasts payouts and funds gas.
- **postgres**: Persistent storage.
- **redis**: Cache, rate-limits, nonce replay protection.

Network isolation:
- `signer` has no public ports.
- `postgres`/`redis` are internal only.
- `bot-api` communicates with `signer` via internal Docker network.

## Repo Layout
```
app/                    # bot-api
services/watcher_tron/  # TRON watcher
services/watcher_bsc/   # BSC watcher
services/signer/        # signer service
scripts/                # key encryption utilities
alembic/                # DB migrations
trustora/               # shared modules
```

## Quick Start
### 1) Get Telegram Bot Token
1. Open Telegram and chat with @BotFather.
2. Create a bot and copy the token.
3. Set `BOT_TOKEN` in `.env`.

### 2) Configure Providers
Set RPC endpoints in `.env`:
- `TRON_RPC_URLS` (comma-separated if multiple)
- `BSC_RPC_URLS` (comma-separated if multiple)

### 3) Generate & Encrypt Keys
**Never store plaintext keys in the repo.**

Example for a list of private keys (JSON array):
```bash
python scripts/encrypt_key.py \
  --key '["<private_key_1>", "<private_key_2>"]' \
  --out ./secrets/tron_keys.enc \
  --encryption-key "$KEY_ENCRYPTION_KEY"
```

Create gas wallet keys:
```bash
python scripts/encrypt_key.py \
  --key '["<tron_gas_private_key>"]' \
  --out ./secrets/tron_gas.enc \
  --encryption-key "$KEY_ENCRYPTION_KEY"

python scripts/encrypt_key.py \
  --key '["<bsc_gas_private_key>"]' \
  --out ./secrets/bsc_gas.enc \
  --encryption-key "$KEY_ENCRYPTION_KEY"
```

Verify decryption:
```bash
python scripts/decrypt_test.py --file ./secrets/tron_keys.enc --encryption-key "$KEY_ENCRYPTION_KEY"
```

### 4) Configure `.env`
Copy `.env.example` to `.env` and fill in values.

### 5) Run with Docker Compose
```bash
docker compose up -d --build
```

### 6) Run Migrations
```bash
docker compose exec bot-api alembic upgrade head
```

### 7) Run Tests & Lint
```bash
pytest
ruff check .
black --check .
mypy .
```

## VPS Deployment Checklist
- **SSH hardening**: Use SSH keys only; disable password login.
- **Firewall**: UFW allow 22/tcp; deny all else.
- **Fail2ban**: Protect SSH.
- **Auto updates**: Enable unattended upgrades.
- **Log rotation**: Configure logrotate for docker logs.

## Monitoring Playbook
- **Kill switch**: Set `PAUSE_PAYOUTS=true` in `.env` or toggle in admin panel.
- **Rotate secrets**: Re-encrypt keys and restart signer.
- **Emergency response**:
  1) Enable kill switch
  2) Freeze chats for disputes
  3) Snapshot DB

## Backups
- Schedule daily backups:
  ```bash
  docker compose exec postgres pg_dump -U trustora trustora > backup.sql
  ```
- Restore:
  ```bash
  psql -U trustora -d trustora < backup.sql
  ```

## Admin Panel
- Trigger with `ADMIN_SECRET_COMMAND` (not `/admin`).
- Session TTL is 10 minutes (stored in Redis).
- All sensitive actions require double-confirmation.

## Notes
- Only TRC20 and BEP20 are automated in V1.
- Other chains must be manually approved in V2 with feature flags.
- Amounts are stored with 6-decimal precision and signer returns both seller and fee transaction hashes.
