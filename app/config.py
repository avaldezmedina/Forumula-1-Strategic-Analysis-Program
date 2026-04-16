from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    openf1_base_url: str = "https://api.openf1.org/v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Single shared instance imported everywhere
settings = Settings()