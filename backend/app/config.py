import os
from datetime import timedelta


class Settings:
    PROJECT_NAME: str = "A-MCTP: Audio Morse Code Translation Platform"

    # --- Auth ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-.env")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # --- Storage ---
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/amctp_uploads")
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
    ALLOWED_EXTENSIONS = {".wav", ".mp3", ".ogg"}

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./amctp.db")

    # --- Redis / Celery ---
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

    # --- DSP defaults ---
    DEFAULT_LOW_HZ: float = float(os.getenv("DEFAULT_LOW_HZ", "700"))
    DEFAULT_HIGH_HZ: float = float(os.getenv("DEFAULT_HIGH_HZ", "800"))

    # --- CORS ---
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080,http://localhost:3000").split(",")


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
