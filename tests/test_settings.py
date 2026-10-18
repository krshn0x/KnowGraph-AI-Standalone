from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from knowgraph.api import create_app
from knowgraph.config import Settings
from knowgraph.models import Answer, Entity


@pytest.mark.parametrize("source", ["environment", "dotenv"])
@pytest.mark.parametrize(
    "prefix,provider", [("TOKENHARBOUR", "tokenharbour"), ("AGENTROUTER", "agentrouter")]
)
def test_tokenharbour_and_legacy_configuration_names(
    monkeypatch, tmp_path, source, prefix, provider
):
    for name in (
        "LLM_PROVIDER",
        *(
            f"{p}_{f}"
            for p in ("TOKENHARBOUR", "AGENTROUTER")
            for f in ("API_KEY", "BASE_URL", "MODEL")
        ),
    ):
        monkeypatch.delenv(name, raising=False)
    values = {
        "LLM_PROVIDER": provider,
        f"{prefix}_API_KEY": "private-tokenharbour-test-key",
        f"{prefix}_BASE_URL": "https://tokenharbor.ai/v1",
        f"{prefix}_MODEL": "deepseek-v4-flash:free",
    }
    env_file = None
    if source == "dotenv":
        env_file = tmp_path / ".env"
        env_file.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    else:
        for name, value in values.items():
            monkeypatch.setenv(name, value)
    settings = Settings(_env_file=env_file)
    assert settings.llm_provider == "agentrouter"
    assert settings.active_base_url == "https://tokenharbor.ai/v1"
    assert settings.active_model == "deepseek-v4-flash:free"
    assert settings.active_api_key.get_secret_value() == "private-tokenharbour-test-key"
    assert settings.configuration_message is None
    assert "private-tokenharbour-test-key" not in repr(settings)


@pytest.mark.parametrize("override", [None, "private-session-key", ""])
def test_tokenharbour_names_take_precedence_and_session_snapshots_override_environment(
    monkeypatch, override
):
    monkeypatch.setenv("LLM_PROVIDER", "tokenharbour")
    for prefix, value in (("TOKENHARBOUR", "current"), ("AGENTROUTER", "legacy")):
        monkeypatch.setenv(f"{prefix}_API_KEY", f"private-{value}-key")
        monkeypatch.setenv(f"{prefix}_BASE_URL", f"https://{value}.example/v1")
        monkeypatch.setenv(f"{prefix}_MODEL", f"{value}-model")
    settings = Settings(_env_file=None)
    assert settings.active_api_key.get_secret_value() == "private-current-key"
    assert settings.active_base_url == "https://current.example/v1"
    assert settings.active_model == "current-model"
    if override is not None:
        # The settings API rebuilds Settings from a snapshot, including disconnects.
        snapshot = settings.model_dump() | {"agentrouter_api_key": override}
        changed = Settings(_env_file=None, **snapshot)
        assert changed.active_api_key.get_secret_value() == override
        assert changed.active_model == settings.active_model


@pytest.fixture
def configuration_client(monkeypatch):
    monkeypatch.setattr(
        "knowgraph.api.get_settings",
        lambda: Settings(
            _env_file=None,
            llm_provider="openai",
            openai_api_key="",
            agentrouter_api_key="",
            agentrouter_base_url="",
            agentrouter_model="",
            gemini_api_key="",
        ),
    )
    store = SimpleNamespace(
        initialize=lambda: None, ping=lambda: None, counts=lambda: {"nodes": 0, "edges": 0}
    )
    with TestClient(create_app(store)) as client:
        yield client


def payload(**updates):
    return {
        "provider": "agentrouter",
        "model": "my-deepseek-v4",
        "base_url": "https://router.example.test/v1",
        "api_key": "private-router-test-key",
        **updates,
    }


def test_agentrouter_website_url_is_normalized_when_saved(configuration_client):
    response = configuration_client.post(
        "/settings/ai",
        json=payload(base_url="https://agentrouter.org/", model="deepseek-v4-flash"),
    )
    assert response.status_code == 200
    router = response.json()["providers"]["agentrouter"]
    assert router["base_url"] == "https://agentrouter.org/v1"
    assert router["model"] == "deepseek-v4-flash"
    assert "private-router-test-key" not in response.text


@pytest.mark.parametrize("provider", ["agentrouter", "gemini"])
def test_settings_key_is_write_only_and_can_be_preserved_or_disconnected(
    configuration_client, provider
):
    client = configuration_client
    response = client.post("/settings/ai", json=payload(provider=provider))
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["storage"] == "session"
    assert response.json()["providers"][provider]["has_api_key"] is True
    for response in [response, client.get("/settings/ai"), client.get("/health")]:
        assert "private-router-test-key" not in response.text
    keep = payload(provider=provider, model="updated-model")
    del keep["api_key"]
    response = client.post("/settings/ai", json=keep)
    assert response.json()["providers"][provider]["has_api_key"] is True
    response = client.post("/settings/ai", json=payload(provider=provider, api_key=""))
    assert response.json()["configured"] is False
    assert response.json()["providers"][provider]["has_api_key"] is False
    assert client.get("/health").json()["ai_configured"] is False


@pytest.mark.parametrize(
    "updates",
    [
        {"base_url": "https://user:private-url-password@router.example/v1"},
        {"base_url": "http://remote-router.example/v1"},
        {"base_url": ""},
        {"model": " "},
        {"provider": "unapproved"},
        {"api_key": "private-oversized-key" * 500},
        {"unexpected": "private-extra-value"},
    ],
)
@pytest.mark.parametrize("path", ["/settings/ai", "/settings/ai/test"])
def test_invalid_configuration_never_echoes_credentials(configuration_client, updates, path):
    response = configuration_client.post(path, json=payload(**updates))
    assert response.status_code == 422
    assert "private-" not in response.text
    assert configuration_client.get("/settings/ai").json()["provider"] == "openai"


def test_invalid_json_does_not_echo_the_request_body(configuration_client):
    response = configuration_client.post(
        "/settings/ai",
        content='{"api_key":"private-router-test-key",broken}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert "private-router-test-key" not in response.text


def test_new_questions_use_updated_settings_and_close_their_client(
    configuration_client, monkeypatch
):
    captured, closed = [], []

    class FakeAgent:
        def __init__(self, retrieval, settings):
            captured.append(settings)
            self.settings = settings
            self.client = SimpleNamespace(close=lambda: closed.append(True))

        def ask(self, request):
            return Answer(summary=self.settings.active_model, claims=[], insufficient_evidence=True)

    monkeypatch.setattr("knowgraph.api.Agent", FakeAgent)
    client = configuration_client
    client.post("/settings/ai", json=payload()).raise_for_status()
    assert client.post("/ask", json={"question": "checkout"}).json()["summary"] == "my-deepseek-v4"
    client.post("/settings/ai", json=payload(model="new-model", api_key="new-private-key"))
    assert client.post("/ask", json={"question": "checkout"}).json()["summary"] == "new-model"
    assert captured[0].active_api_key.get_secret_value() == "private-router-test-key"
    assert captured[1].active_api_key.get_secret_value() == "new-private-key"
    assert len(closed) == 2


def test_ui_configuration_does_not_modify_environment_defaults(configuration_client):
    configuration_client.post("/settings/ai", json=payload()).raise_for_status()
    store = SimpleNamespace(initialize=lambda: None)
    with TestClient(create_app(store)) as restarted:
        settings = restarted.get("/settings/ai").json()
    assert settings["provider"] == "openai"
    assert settings["storage"] == "environment"
    assert settings["providers"]["agentrouter"]["has_api_key"] is False


def test_ollama_settings_need_no_key_and_ignore_any_supplied_cloud_key(configuration_client):
    response = configuration_client.post(
        "/settings/ai",
        json={
            "provider": "ollama",
            "model": "qwen3:4b",
            "base_url": "http://host.docker.internal:11434/v1",
            "api_key": "private-accidental-cloud-key",
            "deadline_seconds": 600,
        },
    )
    assert response.status_code == 200 and response.json()["configured"] is True
    assert response.json()["providers"]["ollama"]["has_api_key"] is False
    assert response.json()["providers"]["ollama"]["deadline_seconds"] == 600
    assert "private-accidental-cloud-key" not in response.text
    health = configuration_client.get("/health").json()
    assert health["provider"] == "ollama" and health["ai_configured"] is True
    assert health["model"] == "qwen3:4b"


def test_invalid_local_deadline_does_not_change_saved_settings(configuration_client):
    for deadline in (0, 901):
        response = configuration_client.post(
            "/settings/ai",
            json={
                "provider": "ollama",
                "model": "qwen3:4b",
                "base_url": "http://localhost:11434/v1",
                "deadline_seconds": deadline,
            },
        )
        assert response.status_code == 422
    assert configuration_client.get("/settings/ai").json()["provider"] == "openai"


def test_connection_test_uses_staged_credentials_without_saving_them(
    configuration_client, monkeypatch
):
    captured = []
    closed = []

    class TestAgent:
        def __init__(self, retrieval, settings):
            captured.append(settings)
            self.client = SimpleNamespace(close=lambda: closed.append(True))

        def ask(self, request):
            return Answer(
                summary="Test completed",
                claims=[
                    {
                        "text": "A test source exists",
                        "certainty": "observed",
                        "evidence_ids": ["test:source"],
                    }
                ],
                sources=[Entity(id="test:source", kind="Service", title="Test source")],
                insufficient_evidence=False,
                status="ok",
            )

    monkeypatch.setattr("knowgraph.api.Agent", TestAgent)
    result = configuration_client.post("/settings/ai/test", json=payload(provider="gemini"))
    assert result.status_code == 200 and result.json()["ok"] is True
    assert captured[0].gemini_api_key.get_secret_value() == "private-router-test-key"
    assert "private-" not in result.text and closed == [True]
    saved = configuration_client.get("/settings/ai").json()
    assert saved["provider"] == "openai" and not saved["providers"]["gemini"]["has_api_key"]


def test_connection_test_limits_local_probe_time_without_changing_the_saved_deadline(
    configuration_client, monkeypatch
):
    captured = []

    class TestAgent:
        def __init__(self, retrieval, settings):
            captured.append(settings)
            self.client = None

        def ask(self, request):
            return Answer(
                summary="Unavailable",
                claims=[],
                insufficient_evidence=True,
                warnings=["Cannot reach Ollama"],
            )

    monkeypatch.setattr("knowgraph.api.Agent", TestAgent)
    response = configuration_client.post(
        "/settings/ai/test",
        json=payload(provider="ollama", base_url="http://localhost:11434/v1", deadline_seconds=600),
    )
    assert response.status_code == 200 and response.json()["ok"] is False
    assert captured[0].active_deadline_seconds == 90
    assert (
        configuration_client.get("/settings/ai").json()["providers"]["ollama"]["deadline_seconds"]
        == 300
    )
