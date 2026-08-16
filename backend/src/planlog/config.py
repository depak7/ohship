from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


from planlog.constants import PUBLIC_INSTALL_URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://planlog:planlog@localhost:5433/planlog"
    bootstrap_token: str = "dev"
    cors_origins: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    install_url: str = PUBLIC_INSTALL_URL
    jwt_secret: str = "planlog-dev-secret-change-me-please-32b"
    jwt_expire_hours: int = 168
    google_client_id: str = ""
    google_client_secret: str = ""
    # Analytics is off unless a website id is set — same empty-string-means-disabled pattern
    # as Google OAuth above. Deliberately not defaulted to Planlog's own id, so self-hosters
    # never ship their traffic to us.
    umami_website_id: str = ""
    umami_host: str = "https://cloud.umami.is"

    @field_validator("database_url", mode="before")
    @classmethod
    def heroku_postgres_url(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql://", 1)
        return value


settings = Settings()
