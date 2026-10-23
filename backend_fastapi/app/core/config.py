# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    PROJECT_NAME: str = "GIS Plantation API"
    API_V1_STR: str = "/api/v1"

    # Konfigurasi Database (wajib disuplai lewat .env)
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    APP_NAME_IN_DB: str = "webgis-api"

    # Konfigurasi Auth/JWT (wajib dari .env)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    # 1440 menit = 1 hari, sama dengan cookie sesi di gis-dashboard.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    UPLOAD_MAX_MB: int = 50

    # Worker antrian upload GeoJSON (python -m app.workers.upload_jobs).
    UPLOAD_JOB_POLL_SECONDS: float = 2.0       # jeda cek antrian saat kosong
    UPLOAD_JOB_HEARTBEAT_SECONDS: float = 10.0
    UPLOAD_JOB_STALE_SECONDS: int = 120        # job 'running' tanpa detak selama ini dianggap worker mati
    UPLOAD_JOB_KEEP_DAYS: int = 7              # job selesai lebih tua dari ini dihapus

    # Token akun layanan (sistem lain): masa berlaku bawaan & batas maksimum, dalam hari.
    SERVICE_TOKEN_DEFAULT_DAYS: int = 365
    SERVICE_TOKEN_MAX_DAYS: int = 1825

    SUPERADMIN_ROLE: str = "superadmin"

    # Konfigurasi seed admin (wajib dari .env)
    SEED_ADMIN_USERNAME: str = "superadmin"
    SEED_ADMIN_EMAIL: str = "superadmin@plantation.com"
    SEED_ADMIN_PASSWORD: str = ""  # tanpa default: seed menolak berjalan bila kosong

    # Origin yang boleh memanggil API, dipisah koma. "*" = semua (hanya untuk development)
    CORS_ORIGINS: str = "*"

    @property
    def CORS_ORIGIN_LIST(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()] or ["*"]

    # HTTP untuk dashboard. Tidak diubah saat mTLS dinyalakan.
    HTTP_HOST: str = "127.0.0.1"
    HTTP_PORT: int = 8000

    # mTLS untuk backend-external. Listener HTTPS hanya naik bila ketiga file sertifikat ada
    # dan MTLS_ENABLED=true. MTLS_ENFORCE dipasang proses HTTPS saja, bukan proses HTTP dashboard.
    MTLS_ENABLED: bool = True
    MTLS_ENFORCE: bool = False
    MTLS_HOST: str = "0.0.0.0"
    MTLS_PORT: int = 8443
    MTLS_CERTFILE: str = "certs/runtime/server.crt"
    MTLS_KEYFILE: str = "certs/runtime/server.key"
    MTLS_CA_FILE: str = "certs/runtime/ca.crt"
    MTLS_ALLOWED_CNS: str = "backend-external"
    # Prefix pada listener HTTPS yang menolak permintaan tanpa sertifikat klien.
    # /health tetap terbuka. Kosongkan untuk tidak mewajibkan sertifikat pada path mana pun.
    MTLS_REQUIRED_PATHS: str = "/api/"

    @property
    def MTLS_ALLOWED_CN_LIST(self) -> list[str]:
        return [name.strip() for name in self.MTLS_ALLOWED_CNS.split(",") if name.strip()]

    @property
    def MTLS_REQUIRED_PATH_LIST(self) -> list[str]:
        return [path.strip() for path in self.MTLS_REQUIRED_PATHS.split(",") if path.strip()]

    # Cache Redis untuk API baca halaman peta / blok profile.
    # Backend jalan dengan network_mode: host, jadi Redis di container
    # yang mem-publish port 6379 dijangkau lewat 127.0.0.1.
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_MAP_ENABLED: bool = True
    REDIS_MAP_TTL_SECONDS: int = 900
    REDIS_MAP_MAX_BYTES: int = 64 * 1024 * 1024

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
