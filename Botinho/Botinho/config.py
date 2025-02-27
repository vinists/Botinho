from functools import lru_cache
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    redis_host: str = "192.168.1.18"
    redis_port: int = 6379

    llm_api_url: str = "http://192.168.1.18:4454"

    prefix: str = Field(..., env="prefix")
    discord_token: str = Field(..., env="discord")
    voice_token: str = Field(..., env="voice")
    ibm_voice_token: str = Field(..., env="ibmkey")
    dreamstudio_token: str = Field(..., env="dreamstudio")
    openai_token: str = Field(..., env="openai")


@lru_cache()
def get_settings():
    return Settings()
