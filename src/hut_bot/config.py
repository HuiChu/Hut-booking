from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hike_username: str = Field(default="", description="hike.taiwan.gov.tw account")
    hike_password: str = Field(default="", description="hike.taiwan.gov.tw password")

    leader_name: str = Field(default="", description="領隊姓名")
    leader_id: str = Field(default="", description="領隊身分證字號")
    leader_phone: str = Field(default="", description="領隊手機")
    leader_birthday: date | None = Field(default=None, description="領隊生日 YYYY-MM-DD")

    ntp_server: str = Field(default="time.stdtime.gov.tw")
    log_level: str = Field(default="INFO")

    storage_dir: Path = Field(default=Path("storage"))
    logs_dir: Path = Field(default=Path("logs"))

    @property
    def auth_state_path(self) -> Path:
        return self.storage_dir / "auth_state.json"

    @property
    def fixtures_dir(self) -> Path:
        return self.storage_dir / "form_fixtures"

    def ensure_dirs(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
