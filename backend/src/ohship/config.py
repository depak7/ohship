from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://ohship:ohship@localhost:5433/ohship"
    bootstrap_token: str = "dev"
    cors_origins: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    jwt_secret: str = "ohship-dev-secret-change-me-please-32b"
    jwt_expire_hours: int = 168
    google_client_id: str = ""
    google_client_secret: str = ""


settings = Settings()
