from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "workforcesync"
    postgres_user: str = "workforcesync"
    postgres_password: SecretStr
    source_api_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    batch_size: int = Field(default=500, ge=1, le=2000)
    page_size: int = Field(default=100, ge=1, le=1000)
    max_rejected_fraction: float = Field(default=1, ge=0, le=1)

    def connection_kwargs(self) -> dict:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password.get_secret_value(),
            "connect_timeout": 5,
        }
