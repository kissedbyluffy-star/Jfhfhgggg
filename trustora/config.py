from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_ids: str = Field("", alias="ADMIN_IDS")
    admin_secret_command: str = Field(..., alias="ADMIN_SECRET_COMMAND")
    reviews_channel_id: int = Field(0, alias="REVIEWS_CHANNEL_ID")
    public_hash_salt: str = Field(..., alias="PUBLIC_HASH_SALT")

    tron_rpc_urls: str = Field(..., alias="TRON_RPC_URLS")
    bsc_rpc_urls: str = Field(..., alias="BSC_RPC_URLS")

    tron_usdt_contract: str = Field(..., alias="TRON_USDT_CONTRACT")
    bsc_usdt_contract: str = Field(..., alias="BSC_USDT_CONTRACT")

    tron_confirmations_required: int = Field(20, alias="TRON_CONFIRMATIONS_REQUIRED")
    bsc_confirmations_required: int = Field(12, alias="BSC_CONFIRMATIONS_REQUIRED")

    tron_gas_wallet: str = Field(..., alias="TRON_GAS_WALLET")
    bsc_gas_wallet: str = Field(..., alias="BSC_GAS_WALLET")

    fee_wallet_tron: str = Field(..., alias="FEE_WALLET_TRON")
    fee_wallet_bsc: str = Field(..., alias="FEE_WALLET_BSC")

    key_encryption_key: str = Field(..., alias="KEY_ENCRYPTION_KEY")
    signer_hmac_secret: str = Field(..., alias="SIGNER_HMAC_SECRET")

    auto_payout_max: float = Field(200, alias="AUTO_PAYOUT_MAX")
    hard_max_payout: float = Field(1000, alias="HARD_MAX_PAYOUT")
    daily_payout_max: float = Field(1000, alias="DAILY_PAYOUT_MAX")
    payouts_per_hour_max: int = Field(10, alias="PAYOUTS_PER_HOUR_MAX")
    pause_payouts: bool = Field(False, alias="PAUSE_PAYOUTS")

    signer_base_url: str = Field("http://signer:8080", alias="SIGNER_BASE_URL")


def load_settings() -> Settings:
    return Settings()
