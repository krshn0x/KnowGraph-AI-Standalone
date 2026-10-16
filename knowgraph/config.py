from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_graph: str = "knowgraph"
    falkordb_password: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-6.1-sol"
    agent_deadline_seconds: float = Field(default=60, ge=1, le=120)
    agent_max_tool_calls: int = Field(default=8, ge=1, le=8)


@lru_cache
def get_settings() -> Settings:
    return Settings()
