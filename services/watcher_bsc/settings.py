from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WatcherSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")
    bsc_rpc_urls: str = Field(..., alias="BSC_RPC_URLS")
    bsc_usdt_contract: str = Field(..., alias="BSC_USDT_CONTRACT")
    bsc_confirmations_required: int = Field(12, alias="BSC_CONFIRMATIONS_REQUIRED")

    scan_interval_seconds: int = Field(30, alias="BSC_SCAN_INTERVAL")
    rescan_interval_seconds: int = Field(300, alias="BSC_RESCAN_INTERVAL")


def load_settings() -> WatcherSettings:
    return WatcherSettings()
