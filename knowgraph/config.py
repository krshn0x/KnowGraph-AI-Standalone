from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_username: str | None = None
    falkordb_password: str | None = None
    falkordb_graph: str = "knowgraph"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"
    ollama_timeout_seconds: float = 120.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
