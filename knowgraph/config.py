from functools import lru_cache
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlsplit

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_OLLAMA_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_graph: str = "knowgraph"
    falkordb_password: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-6.1-sol"
    llm_provider: Literal["openai", "agentrouter", "gemini", "ollama"] = "openai"
    ollama_model: str = Field(default=DEFAULT_OLLAMA_MODEL, max_length=200)
    ollama_base_url: str = Field(default=DEFAULT_OLLAMA_URL, max_length=2048)
    ollama_deadline_seconds: float | None = Field(default=None, ge=1, le=900)
    ollama_max_output_tokens: int = Field(default=1536, ge=256, le=4096)
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = Field(default=DEFAULT_GEMINI_MODEL, max_length=200)
    agentrouter_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("TOKENHARBOUR_API_KEY", "AGENTROUTER_API_KEY"),
    )
    agentrouter_base_url: str = Field(
        default="",
        max_length=2048,
        validation_alias=AliasChoices("TOKENHARBOUR_BASE_URL", "AGENTROUTER_BASE_URL"),
    )
    agentrouter_model: str = Field(
        default="",
        max_length=200,
        validation_alias=AliasChoices("TOKENHARBOUR_MODEL", "AGENTROUTER_MODEL"),
    )
    agent_deadline_seconds: float = Field(default=60, ge=1, le=900)
    agent_max_tool_calls: int = Field(default=8, ge=1, le=8)

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_tokenharbour_provider(cls, value):
        # Keep the existing adapter and session API compatible with saved settings.
        return "agentrouter" if value == "tokenharbour" else value

    @field_validator("ollama_deadline_seconds", mode="before")
    @classmethod
    def optional_local_deadline(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

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
        # The public website root is commonly pasted instead of the API endpoint.
        # Only normalize this known provider; custom gateways may use other paths.
        if url.netloc.lower() == "agentrouter.org" and not url.path:
            return "https://agentrouter.org/v1"
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_url(cls, value: str) -> str:
        value = value.strip().rstrip("/") or DEFAULT_OLLAMA_URL
        url = urlsplit(value)
        local = url.hostname in {"localhost", "host.docker.internal", "ollama"}
        try:
            local = local or ip_address(url.hostname or "").is_private
        except ValueError:
            pass
        if (
            not url.hostname
            or url.scheme not in {"http", "https"}
            or (url.scheme == "http" and not local)
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or (url.port is not None and not 1 <= url.port <= 65535)
        ):
            raise ValueError("Use a local Ollama HTTP URL or HTTPS URL without credentials.")
        return value

    @field_validator("agentrouter_model", "gemini_model", "ollama_model")
    @classmethod
    def trim_router_model(cls, value: str) -> str:
        return value.strip()

    @property
    def active_model(self) -> str:
        return getattr(self, f"{self.llm_provider}_model")

    @property
    def active_deadline_seconds(self) -> float:
        if self.llm_provider == "ollama":
            # Retain compatibility with users who raised the shared deadline.
            return self.ollama_deadline_seconds or max(300, self.agent_deadline_seconds)
        return self.agent_deadline_seconds

    @property
    def active_api_key(self) -> SecretStr:
        if self.llm_provider == "ollama":
            # Required by the SDK, ignored by the local Ollama server.
            return SecretStr("ollama")
        return getattr(self, f"{self.llm_provider}_api_key")

    @property
    def active_base_url(self) -> str:
        if self.llm_provider == "gemini":
            return GEMINI_BASE_URL
        if self.llm_provider == "agentrouter":
            return self.agentrouter_base_url
        if self.llm_provider == "ollama":
            return self.ollama_base_url
        return "https://api.openai.com/v1"

    @property
    def configuration_message(self) -> str | None:
        if self.llm_provider == "ollama":
            return (
                "Set OLLAMA_MODEL to a downloaded, tool-capable model."
                if not self.ollama_model
                else None
            )
        if self.llm_provider == "gemini":
            missing = []
            if not self.gemini_api_key.get_secret_value().strip():
                missing.append("GEMINI_API_KEY")
            if not self.gemini_model:
                missing.append("GEMINI_MODEL")
            return f"Set {', '.join(missing)} to enable Gemini answers." if missing else None
        if self.llm_provider == "agentrouter":
            missing = [
                name
                for name, value in (
                    ("TOKENHARBOUR_API_KEY", self.agentrouter_api_key.get_secret_value().strip()),
                    ("TOKENHARBOUR_BASE_URL", self.agentrouter_base_url),
                    ("TOKENHARBOUR_MODEL", self.agentrouter_model),
                )
                if not value
            ]
            if missing:
                return (
                    f"Set {', '.join(missing)} in the backend environment to enable Token Harbour."
                )
        elif not self.openai_api_key.get_secret_value().strip():
            return "Set OPENAI_API_KEY in the backend environment to enable AI answers."
        return None


class AISettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai", "agentrouter", "gemini", "ollama"]
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field(default="", max_length=2048)
    # Omitted/null preserves the saved key; an explicit empty string disconnects it.
    api_key: SecretStr | None = Field(default=None, max_length=4096)
    deadline_seconds: float | None = Field(default=None, ge=1, le=900)

    @field_validator("model")
    @classmethod
    def nonempty_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter the model ID shown by your provider.")
        return value.strip()

    @model_validator(mode="after")
    def router_endpoint(self):
        if self.deadline_seconds is not None and self.provider != "ollama":
            raise ValueError("Investigation deadline is an Ollama setting.")
        if self.provider == "agentrouter":
            self.base_url = Settings.validate_router_url(self.base_url)
            if not self.base_url:
                raise ValueError("Enter the Agent Router API base URL.")
        if self.provider == "ollama":
            if not self.base_url.strip():
                raise ValueError("Enter the Ollama API base URL.")
            self.base_url = Settings.validate_ollama_url(self.base_url)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
