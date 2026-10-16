from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from knowgraph.api import create_app
from knowgraph.config import Settings
from knowgraph.models import Answer


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
def test_invalid_configuration_never_echoes_credentials(configuration_client, updates):
    response = configuration_client.post("/settings/ai", json=payload(**updates))
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
