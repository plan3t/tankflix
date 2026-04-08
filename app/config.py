import os
from dataclasses import dataclass


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "TankFlix")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    tankerkoenig_api_key: str = os.getenv("TANKERKOENIG_API_KEY", "")
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-please")
    poll_interval_seconds: int = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
    tankerkoenig_min_fetch_interval_seconds: int = int(os.getenv("TANKERKOENIG_MIN_FETCH_INTERVAL_SECONDS", "300"))

    default_origin_address: str = os.getenv("DEFAULT_ORIGIN_ADDRESS", "An d. Wesebreede 2, 33699 Bielefeld")
    default_origin_lat: float = float(os.getenv("DEFAULT_ORIGIN_LAT", "51.9887894"))
    default_origin_lng: float = float(os.getenv("DEFAULT_ORIGIN_LNG", "8.6197121"))


settings = Settings()
