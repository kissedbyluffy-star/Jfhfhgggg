from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WatcherSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")
    tron_rpc_urls: str = Field(..., alias="TRON_RPC_URLS")
    tron_usdt_contract: str = Field(..., alias="TRON_USDT_CONTRACT")
    tron_confirmations_required: int = Field(20, alias="TRON_CONFIRMATIONS_REQUIRED")

    scan_interval_seconds: int = Field(30, alias="TRON_SCAN_INTERVAL")
    rescan_interval_seconds: int = Field(300, alias="TRON_RESCAN_INTERVAL")


def load_settings() -> WatcherSettings:
    return WatcherSettings()
