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
    # Pool koneksi per PROSES (satu engine bersama untuk app.core.database & app.db.session).
    # Hitungan horizontal scale: koneksi maks = (pod API + pod worker) x (DB_POOL_SIZE + DB_MAX_OVERFLOW).
    # Contoh langsung ke Postgres: 10 pod x (5+10) + 2 worker x 15 = 180 > max_connections bawaan 100.
    # Solusi: arahkan DB_HOST ke PgBouncer (transaction pooling) -> klien boleh banyak, koneksi server
    # dibatasi DEFAULT_POOL_SIZE PgBouncer (mis. 40), atau turunkan nilai di bawah. Lihat infra/README.md.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30            # detik menunggu koneksi bebas di pool sebelum error
    DB_POOL_RECYCLE_SECONDS: int = 1800  # tutup koneksi lebih tua dari ini (hindari putus diam-diam oleh LB/PgBouncer)
    # PgBouncer mode transaction: driver psycopg2 (sync) tidak memakai prepared statement di server dan
    # set_config audit memakai is_local=true (per transaksi), jadi tidak perlu flag khusus.
    # Jalankan DDL kecil saat start (trigger IP aktivitas, tabel versi data). Aman dijalankan banyak replica
    # (dikunci pg_advisory_xact_lock), tetapi bisa dimatikan bila user DB API tidak punya hak DDL.
    DB_STARTUP_DDL: bool = True
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
    # File yang di-touch worker tiap putaran antrian & tiap detak job (untuk livenessProbe K8s/healthcheck).
    # Kosong = mati. Contoh: /tmp/upload-worker.alive
    UPLOAD_WORKER_ALIVE_FILE: str = ""

    # Token akun layanan (sistem lain): masa berlaku bawaan & batas maksimum, dalam hari.
    SERVICE_TOKEN_DEFAULT_DAYS: int = 365
    SERVICE_TOKEN_MAX_DAYS: int = 1825

    SUPERADMIN_ROLE: str = "superadmin"

    # Konfigurasi seed admin (wajib dari .env)
    SEED_ADMIN_USERNAME: str = "superadmin"
    SEED_ADMIN_EMAIL: str = "superadmin@plantation.com"
    SEED_ADMIN_PASSWORD: str = ""  # tanpa default: seed menolak berjalan bila kosong

    # Basemap Foto Udara lewat proxy backend: token TIDAK pernah dikirim ke browser.
    # SERVER_LOCAL=false → digilink + FOTO_UDARA_WMS_TOKEN; true → IP_LOCAL_FOTO_UDARA tanpa token.
    SERVER_LOCAL: bool = False
    # Contoh lokal yang sudah jalan: http://192.168.1.23:8081/geoserver/tpgis/wms + layer tpgis_fu.
    IP_LOCAL_FOTO_UDARA: str = "http://192.168.1.23:8081/geoserver/tpgis/wms"
    FOTO_UDARA_WMS_URL: str = "https://digilink.teladanprima.com/fu/wms"
    FOTO_UDARA_WMS_TOKEN: str = ""
    # Layer WMS yang boleh diminta (dipisah koma). Lokal: tpgis_fu; digilink: tpgis:tpgis_fu (alias saling cocok).
    FOTO_UDARA_WMS_LAYERS: str = "tpgis:tpgis_fu"
    # Foto udara jarang berubah dan GeoServer merender tiap ubin ~0,6–1,4 dtk tanpa cache, jadi ubin disimpan lama.
    FOTO_UDARA_CACHE_SECONDS: int = 90 * 24 * 3600
    # Permintaan serentak ke GeoServer per proses backend. Uji 2 Nov 2026: GeoServer hanya sanggup ~5–7 ubin/dtk;
    # batas 4/6/8/12 memberi satu layar (30 ubin) rata-rata 6,6/6,0/5,0/5,7 dtk (beda tipis, beban server naik-turun),
    # sedangkan 30 serentak sempat 20 dtk. Batas ini mencegah lonjakan semacam itu dan menjaga thread pool.
    FOTO_UDARA_MAX_CONCURRENCY: int = 8
    # Lama status user (aktif/ada) di-cache per proses untuk endpoint bervolume tinggi (ubin foto udara), agar
    # puluhan ubin per layar tidak menjadi puluhan query DB. Logout tetap langsung lewat cek sesi Redis; user yang
    # dinonaktifkan tertolak paling lambat setelah nilai ini. 0 = tanpa cache.
    AUTH_USER_CACHE_SECONDS: int = 60

    # Origin yang boleh memanggil API, dipisah koma. "*" = semua (HANYA development — blocker prod)
    CORS_ORIGINS: str = "*"

    @property
    def CORS_ORIGIN_LIST(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()] or ["*"]

    # CIDR peer yang boleh memasok X-Forwarded-For / X-Real-IP (HAProxy). Kosong = ignore header.
    # Contoh Docker bridge: 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
    TRUSTED_PROXY_CIDRS: str = ""

    @property
    def TRUSTED_PROXY_CIDR_LIST(self) -> list[str]:
        return [c.strip() for c in self.TRUSTED_PROXY_CIDRS.split(",") if c.strip()]

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

    # Redis bersama: cache peta + registry sesi JWT (jti) untuk horizontal scaling.
    # Backend dengan network_mode: host menjangkau Redis publish :6379 via 127.0.0.1.
    # Semua replica API wajib memakai REDIS_URL + SECRET_KEY yang sama; sticky session tidak perlu.
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    # Opsional: Redis TERPISAH untuk cache (JSON peta + ubin Foto Udara, TTL hingga 90 hari) dengan
    # maxmemory + allkeys-lru, supaya cache tidak pernah mendesak/menggusur kunci sesi auth (gis:auth:*)
    # yang ada di REDIS_URL (noeviction + AOF). Kosong = cache memakai REDIS_URL (perilaku lama).
    REDIS_CACHE_URL: str = ""
    REDIS_MAP_ENABLED: bool = True
    # Koneksi maksimum pool Redis per proses (pool menunggu bila penuh, tidak error).
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_MAP_TTL_SECONDS: int = 900
    REDIS_MAP_MAX_BYTES: int = 64 * 1024 * 1024
    # Auth sesi (ADR-001): true = fail-closed; logout/password mencabut jti di semua instance.
    # Dev lokal tanpa Redis: false → JWT-only (revoke server-side tidak aktif).
    REDIS_AUTH_ENABLED: bool = False
    # 0 = pakai ACCESS_TOKEN_EXPIRE_MINUTES * 60
    REDIS_AUTH_TTL_SECONDS: int = 0

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
