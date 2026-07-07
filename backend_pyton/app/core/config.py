# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "GIS Plantation API"
    API_V1_STR: str = "/api/v1"

    # Konfigurasi Database (wajib disuplai lewat .env)
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # Konfigurasi Auth/JWT (wajib dari .env)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Konfigurasi seed admin (wajib dari .env)
    SEED_ADMIN_USERNAME: str = "superadmin"
    SEED_ADMIN_EMAIL: str = "superadmin@plantation.com"
    SEED_ADMIN_PASSWORD: str = "admin123"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
