from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_graph: str = "knowgraph"
    falkordb_password: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-6.1-sol"
    llm_provider: Literal["openai", "agentrouter"] = "openai"
    agentrouter_api_key: SecretStr = SecretStr("")
    agentrouter_base_url: str = Field(default="", max_length=2048)
    agentrouter_model: str = Field(default="", max_length=200)
    agent_deadline_seconds: float = Field(default=60, ge=1, le=120)
    agent_max_tool_calls: int = Field(default=8, ge=1, le=8)

    @field_validator("agentrouter_base_url")
    @classmethod
    def validate_router_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value:
            return value
        url = urlsplit(value)
        local_http = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not url.hostname
            or (url.scheme != "https" and not local_http)
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Use an HTTPS API base URL without credentials, query, or fragment.")
        return value

    @field_validator("agentrouter_model")
    @classmethod
    def trim_router_model(cls, value: str) -> str:
        return value.strip()

    @property
    def active_model(self) -> str:
        return self.agentrouter_model if self.llm_provider == "agentrouter" else self.openai_model

    @property
    def active_api_key(self) -> SecretStr:
        return (
            self.agentrouter_api_key if self.llm_provider == "agentrouter" else self.openai_api_key
        )

    @property
    def configuration_message(self) -> str | None:
        if self.llm_provider == "agentrouter":
            missing = [
                name
                for name, value in (
                    ("AGENTROUTER_API_KEY", self.agentrouter_api_key.get_secret_value().strip()),
                    ("AGENTROUTER_BASE_URL", self.agentrouter_base_url),
                    ("AGENTROUTER_MODEL", self.agentrouter_model),
                )
                if not value
            ]
            if missing:
                return (
                    f"Set {', '.join(missing)} in the backend environment to enable Agent Router."
                )
        elif not self.openai_api_key.get_secret_value().strip():
            return "Set OPENAI_API_KEY in the backend environment to enable AI answers."
        return None


class AISettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai", "agentrouter"]
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field(default="", max_length=2048)
    # Omitted/null preserves the saved key; an explicit empty string disconnects it.
    api_key: SecretStr | None = Field(default=None, max_length=4096)

    @field_validator("model")
    @classmethod
    def nonempty_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter the model ID shown by your provider.")
        return value.strip()

    @model_validator(mode="after")
    def router_endpoint(self):
        if self.provider == "agentrouter":
            self.base_url = Settings.validate_router_url(self.base_url)
            if not self.base_url:
                raise ValueError("Enter the Agent Router API base URL.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
