from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_secret: str
    database_url: str = "sqlite:////data/quickboard.db"
    cookie_secure: bool = True
    access_token_minutes: int = 10080
    invite_expire_hours: int = 24
    message_retention_days: int = 90
    max_message_length: int = 5000
    cors_origins: str = ""
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = ""
    auto_cleanup_enabled: bool = True
    model_config=SettingsConfigDict(env_file=".env",extra="ignore")
settings=Settings()
