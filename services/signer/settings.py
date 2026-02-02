from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SignerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")
    key_encryption_key: str = Field(..., alias="KEY_ENCRYPTION_KEY")
    signer_hmac_secret: str = Field(..., alias="SIGNER_HMAC_SECRET")
    pause_payouts: bool = Field(False, alias="PAUSE_PAYOUTS")

    tron_rpc_urls: str = Field(..., alias="TRON_RPC_URLS")
    bsc_rpc_urls: str = Field(..., alias="BSC_RPC_URLS")

    tron_usdt_contract: str = Field(..., alias="TRON_USDT_CONTRACT")
    bsc_usdt_contract: str = Field(..., alias="BSC_USDT_CONTRACT")

    fee_wallet_tron: str = Field(..., alias="FEE_WALLET_TRON")
    fee_wallet_bsc: str = Field(..., alias="FEE_WALLET_BSC")

    tron_key_file: str = Field("./secrets/tron_keys.enc", alias="TRON_KEYS_FILE")
    bsc_key_file: str = Field("./secrets/bsc_keys.enc", alias="BSC_KEYS_FILE")

    tron_gas_key_file: str = Field("./secrets/tron_gas.enc", alias="TRON_GAS_KEY_FILE")
    bsc_gas_key_file: str = Field("./secrets/bsc_gas.enc", alias="BSC_GAS_KEY_FILE")
    tron_gas_amount: float = Field(1.0, alias="TRON_GAS_AMOUNT")
    bsc_gas_amount: float = Field(0.001, alias="BSC_GAS_AMOUNT")
    tron_gas_min_balance: float = Field(2.0, alias="TRON_GAS_MIN_BALANCE")
    bsc_gas_min_balance: float = Field(0.002, alias="BSC_GAS_MIN_BALANCE")

    auto_payout_max: float = Field(200, alias="AUTO_PAYOUT_MAX")
    hard_max_payout: float = Field(1000, alias="HARD_MAX_PAYOUT")
    daily_payout_max: float = Field(1000, alias="DAILY_PAYOUT_MAX")
    payouts_per_hour_max: int = Field(10, alias="PAYOUTS_PER_HOUR_MAX")


def load_settings() -> SignerSettings:
    return SignerSettings()
