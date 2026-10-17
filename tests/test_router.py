import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI
from pydantic import ValidationError

from knowgraph.agent import Agent
from knowgraph.api import create_app
from knowgraph.config import Settings
from knowgraph.models import AskRequest, Entity

SERVICE = Entity(
    id="demo:checkout", kind="Service", title="Checkout", source_ref="fixture://checkout"
)


class RouterRetrieval:
    def __init__(self):
        self.store = SimpleNamespace(search=lambda *a, **kw: [SERVICE])


def router_settings(**overrides):
    return Settings(
        **{
            "llm_provider": "agentrouter",
            "agentrouter_api_key": "router-test-secret",
            "agentrouter_base_url": "https://router.example.test/v1",
            "agentrouter_model": "test-deepseek-v4",
            **overrides,
        }
    )


def tool_message(reasoning=True):
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "search_entities",
                    "arguments": json.dumps({"query": "checkout", "kind": "Service"}),
                },
            }
        ],
    }
    if reasoning:
        message["reasoning_content"] = "private-model-reasoning"
    return message


def final_message(citation=SERVICE.id):
    return {
        "role": "assistant",
        "content": json.dumps(
            {
                "summary": "Checkout is a recorded service.",
                "claims": [
                    {
                        "text": "Checkout is a recorded service.",
                        "certainty": "observed",
                        "evidence_ids": [citation],
                    }
                ],
                "insufficient_evidence": False,
            }
        ),
    }


def make_router(messages, **overrides):
    requests = []

    def handler(request):
        assert request.url == "https://router.example.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer router-test-secret"
        requests.append(json.loads(request.content))
        message = messages[len(requests) - 1]
        if isinstance(message, httpx.Response):
            return message
        if isinstance(message, Exception):
            raise message
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_1",
                "object": "chat.completion",
                "created": 0,
                "model": "test-deepseek-v4",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                        "message": message,
                    }
                ],
            },
        )

    client = OpenAI(
        api_key="router-test-secret",
        base_url="https://router.example.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return Agent(RouterRetrieval(), router_settings(**overrides), client=client), requests


def test_router_tool_round_trip_replays_reasoning_and_validates_citations():
    agent, requests = make_router([tool_message(), final_message()])
    answer = agent.ask(
        AskRequest(question="checkout", history=[{"role": "user", "content": "Earlier question"}])
    )
    assert answer.status == "ok"
    assert answer.tool_calls == ["search_entities"]
    assert answer.sources == [SERVICE]
    assert requests[0]["model"] == "test-deepseek-v4"
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert requests[0]["messages"][0]["role"] == "system"
    assert "JSON" in requests[0]["messages"][0]["content"]
    assert requests[0]["messages"][1] == {"role": "user", "content": "Earlier question"}
    assert len(requests[0]["tools"]) == 5
    assert requests[0]["tools"][0]["function"]["parameters"]["additionalProperties"] is False
    assert "strict" not in requests[0]["tools"][0]["function"]
    assert requests[1]["messages"][-2]["reasoning_content"] == "private-model-reasoning"
    assert requests[1]["messages"][-1]["tool_call_id"] == "call_1"
    assert json.loads(requests[1]["messages"][-1]["content"])["entities"][0]["id"] == SERVICE.id
    assert "private-model-reasoning" not in answer.model_dump_json()
    assert "router-test-secret" not in answer.model_dump_json()


@pytest.mark.parametrize(
    "final", [final_message("invented:source"), {"role": "assistant", "content": "not JSON"}]
)
def test_router_invalid_answers_fail_closed_and_preserve_retrieved_records(final):
    agent, _ = make_router([tool_message(False), final])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error"
    assert not answer.claims and answer.evidence.nodes == [SERVICE]
    assert "recorded service" not in answer.summary


def test_router_cannot_reuse_history_citations_without_retrieval():
    agent, _ = make_router([final_message()])
    answer = agent.ask(
        AskRequest(
            question="What about it?", history=[{"role": "assistant", "content": SERVICE.id}]
        )
    )
    assert answer.status == "provider_error" and not answer.claims


def test_router_respects_tool_limit_even_if_it_returns_parallel_calls():
    message = tool_message()
    message["tool_calls"].append({**message["tool_calls"][0], "id": "call_2"})
    agent, requests = make_router([message], agent_max_tool_calls=1)
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "limit_reached"
    assert answer.tool_calls == ["search_entities"]
    assert len(requests) == 1


def test_router_forces_no_tools_when_budget_is_used():
    agent, requests = make_router([tool_message(), final_message()], agent_max_tool_calls=1)
    assert agent.ask(AskRequest(question="checkout")).status == "ok"
    assert requests[-1]["tool_choice"] == "none"


def test_router_deadline_rejects_a_late_answer(monkeypatch):
    agent, _ = make_router([tool_message()])
    times = iter([0, 0, 61])
    monkeypatch.setattr("knowgraph.agent.time.monotonic", lambda: next(times))
    assert agent.ask(AskRequest(question="checkout")).status == "limit_reached"


@pytest.mark.parametrize(
    "status, expected",
    [
        (400, "supports Chat Completions"),
        (401, "rejected authentication"),
        (402, "available credit or quota"),
        (403, "key's permissions"),
        (404, "endpoint or model"),
        (429, "quota or rate limit"),
        (500, "upstream model returned HTTP 500"),
        (502, "upstream model returned HTTP 502"),
    ],
)
def test_router_errors_are_actionable_without_leaking_provider_bodies_or_retrying(
    status, expected, caplog
):
    agent, requests = make_router(
        [httpx.Response(status, json={"error": {"message": "private-provider-details"}})]
    )
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error"
    assert len(requests) == 1
    assert expected in answer.warnings[0]
    assert answer.sources == [SERVICE]
    assert "private-provider-details" not in answer.model_dump_json()
    assert "private-provider-details" not in caplog.text


@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.parametrize(
    "body",
    [
        {"error": {"message": "unauthorized client detected; private-provider-details"}},
        {"message": "Unsupported client: private-provider-details"},
        {"error": "unauthorized client detected; private-provider-details"},
    ],
)
def test_router_client_restriction_is_distinguished_from_an_invalid_key(status, body, caplog):
    agent, requests = make_router([httpx.Response(status, json=body)])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and not answer.claims
    assert "blocked this application" in answer.warnings[0]
    assert "KnowGraph" in answer.warnings[0]
    assert "rejected authentication" not in answer.warnings[0]
    assert len(requests) == 1
    assert "private-provider-details" not in answer.model_dump_json() + caplog.text


@pytest.mark.parametrize(
    "error, status, expected",
    [
        (httpx.ConnectError("private-network-details"), "provider_error", "Cannot reach"),
        (
            httpx.ReadTimeout("private-network-details"),
            "limit_reached",
            "investigation deadline",
        ),
    ],
)
def test_router_network_failures_are_distinguished_without_leaking_details(error, status, expected):
    agent, requests = make_router([error])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == status and not answer.claims
    assert expected in answer.warnings[0]
    assert len(requests) == 1
    assert "private-network-details" not in answer.model_dump_json()


@pytest.mark.parametrize(
    "field", ["agentrouter_api_key", "agentrouter_base_url", "agentrouter_model"]
)
def test_incomplete_router_configuration_never_uses_an_openai_key(field):
    settings = router_settings(**{field: "", "openai_api_key": "unrelated-openai-key"})
    agent = Agent(RouterRetrieval(), settings)
    assert agent.client is None
    answer = agent.ask(AskRequest(question="checkout"))
    assert field.upper() in answer.warnings[0]
    assert "unrelated-openai-key" not in answer.model_dump_json()


def test_router_client_uses_only_the_selected_endpoint_key_and_model():
    settings = router_settings(openai_api_key="unrelated-openai-key")
    agent = Agent(RouterRetrieval(), settings)
    assert str(agent.client.base_url) == "https://router.example.test/v1/"
    assert agent.client.api_key == "router-test-secret"
    assert settings.active_model == "test-deepseek-v4"
    assert "router-test-secret" not in repr(settings)
    agent.client.close()


def test_health_reports_the_selected_provider_without_credentials():
    agent, _ = make_router([])
    store = SimpleNamespace(
        initialize=lambda: None, ping=lambda: None, counts=lambda: {"nodes": 1, "edges": 0}
    )
    with TestClient(create_app(store, agent)) as client:
        response = client.get("/health")
    assert response.json()["provider"] == "agentrouter"
    assert response.json()["model"] == "test-deepseek-v4"
    assert response.json()["ai_configured"] is True
    assert "router-test-secret" not in response.text


@pytest.mark.parametrize(
    "url",
    [
        "http://router.example/v1",
        "https://user:password@router.example/v1",
        "https://router.example/v1?key=secret",
        "https://router.example/v1#fragment",
        "not-a-url",
    ],
)
def test_router_configuration_rejects_unsafe_or_invalid_endpoints(url):
    with pytest.raises(ValidationError):
        router_settings(agentrouter_base_url=url)


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://agentrouter.org/", "https://agentrouter.org/v1"),
        (" https://agentrouter.org ", "https://agentrouter.org/v1"),
        ("https://agentrouter.org/v1/", "https://agentrouter.org/v1"),
        ("https://agentrouter.org/custom/", "https://agentrouter.org/custom"),
        ("https://custom-router.example/", "https://custom-router.example"),
        ("https://agentrouter.org.example/", "https://agentrouter.org.example"),
    ],
)
def test_only_the_known_agentrouter_website_root_is_normalized(url, expected):
    settings = router_settings(agentrouter_base_url=url, agentrouter_model="deepseek-v4-flash")
    assert settings.active_base_url == expected
    assert settings.active_model == "deepseek-v4-flash"
