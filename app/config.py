from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    openf1_base_url: str = "https://api.openf1.org/v1"

    class Config:
        env_file = ".env"


# Single shared instance imported everywhere
settings = Settings()
