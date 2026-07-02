from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    openf1_base_url: str = "https://api.openf1.org/v1"
    replay_data_dir: str = "data/replays"
    static_tracks_dir: str = "data/tracks"
    replay_frame_interval_ms: int = 250
    replay_chunk_duration_ms: int = 60_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Single shared instance imported everywhere
settings = Settings()