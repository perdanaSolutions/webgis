# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Tambahkan ini agar tidak error di main.py
    PROJECT_NAME: str = "GIS Plantation API"
    API_V1_STR: str = "/api/v1"
    
    # Konfigurasi Database (Menyesuaikan dengan file .env kamu)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "gis_db"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Mengabaikan variabel lain di .env jika tidak didefinisikan di sini

settings = Settings()