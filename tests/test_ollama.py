import json
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI
from pydantic import ValidationError

from knowgraph.agent import Agent
from knowgraph.config import DEFAULT_OLLAMA_MODEL, Settings
from knowgraph.models import AskRequest, Entity

SOURCE = Entity(
    id="demo:checkout", kind="Service", title="Checkout", source_ref="fixture://checkout"
)


def local_settings(**updates):
    return Settings(
        **{
            "llm_provider": "ollama",
            "ollama_model": DEFAULT_OLLAMA_MODEL,
            "ollama_base_url": "http://127.0.0.1:11434/v1",
            "openai_api_key": "private-openai-key",
            "gemini_api_key": "private-gemini-key",
            "agentrouter_api_key": "private-router-key",
            **updates,
        }
    )


def tool():
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "local_call",
                "type": "function",
                "function": {
                    "name": "search_entities",
                    "arguments": json.dumps({"query": "checkout", "kind": "Service"}),
                },
            }
        ],
    }


def final(citation=SOURCE.id):
    return {
        "role": "assistant",
        "content": json.dumps(
            {
                "summary": "Checkout is recorded.",
                "claims": [
                    {
                        "text": "Checkout is recorded.",
                        "certainty": "observed",
                        "evidence_ids": [citation],
                    }
                ],
                "insufficient_evidence": False,
            }
        ),
    }


def make_local(messages, **updates):
    requests = []

    def handler(request):
        assert str(request.url) == "http://127.0.0.1:11434/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer ollama"
        assert "private-" not in str(request.headers)
        requests.append(json.loads(request.content))
        message = messages[len(requests) - 1]
        if isinstance(message, Exception):
            raise message
        if isinstance(message, httpx.Response):
            return message
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_local",
                "object": "chat.completion",
                "created": 0,
                "model": DEFAULT_OLLAMA_MODEL,
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                    }
                ],
            },
        )

    client = OpenAI(
        api_key="ollama",
        base_url="http://127.0.0.1:11434/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    retrieval = SimpleNamespace(store=SimpleNamespace(search=lambda *a, **kw: [SOURCE]))
    return Agent(retrieval, local_settings(**updates), client=client), requests


def test_local_tool_loop_works_without_a_key_and_forces_json_at_the_cap():
    agent, requests = make_local([tool(), final()], agent_max_tool_calls=1)
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "ok" and answer.sources == [SOURCE]
    assert requests[0]["model"] == DEFAULT_OLLAMA_MODEL
    assert requests[0]["reasoning_effort"] == "none"
    assert requests[0]["max_tokens"] == 1536
    assert "response_format" not in requests[0]
    assert requests[1]["messages"][-1]["tool_call_id"] == "local_call"
    assert "tools" not in requests[1] and "tool_choice" not in requests[1]
    assert requests[1]["response_format"] == {"type": "json_object"}


def test_local_fabricated_citation_is_rejected_and_sources_are_preserved():
    agent, _ = make_local([tool(), final("invented:record")])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and not answer.claims
    assert answer.evidence.nodes == [SOURCE]


@pytest.mark.parametrize("status,expected", [(404, "model not found"), (400, "tool calling")])
def test_missing_model_or_unsupported_tools_has_actionable_errors(status, expected):
    agent, requests = make_local(
        [httpx.Response(status, json={"error": {"message": "private-error-body"}})]
    )
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and expected in answer.warnings[0]
    assert "private-error-body" not in answer.model_dump_json()
    assert len(requests) == 1


def test_offline_ollama_retains_sources_and_never_switches_to_a_cloud_provider():
    agent, requests = make_local([httpx.ConnectError("private-network-details")])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and "Cannot reach Ollama" in answer.warnings[0]
    assert answer.sources == [SOURCE] and len(requests) == 1
    assert "private-network-details" not in answer.model_dump_json()


def test_local_client_never_uses_cloud_credentials():
    settings = local_settings()
    agent = Agent(SimpleNamespace(), settings)
    assert agent.client.api_key == "ollama" and settings.configuration_message is None
    assert str(agent.client.base_url) == "http://127.0.0.1:11434/v1/"
    agent.client.close()


def test_slow_local_model_reports_deadline_instead_of_connection_failure():
    agent, requests = make_local([httpx.ReadTimeout("private-timeout-details")])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "limit_reached" and "deadline" in answer.warnings[0]
    assert "Cannot reach" not in answer.warnings[0]
    assert answer.sources == [SOURCE] and len(requests) == 1
    assert "private-timeout-details" not in answer.model_dump_json()


def test_local_answer_after_the_previous_120_second_cap_is_accepted(monkeypatch):
    agent, _ = make_local([tool(), final()])
    clock = iter([0, 0, 150, 150, 180])
    monkeypatch.setattr("knowgraph.agent.time.monotonic", lambda: next(clock))
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "ok" and answer.sources == [SOURCE]


def test_local_deadline_still_applies_across_all_model_turns(monkeypatch):
    agent, _ = make_local([tool(), final()], ollama_deadline_seconds=180)
    clock = iter([0, 0, 150, 150, 181])
    monkeypatch.setattr("knowgraph.agent.time.monotonic", lambda: next(clock))
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "limit_reached" and not answer.claims
    assert "180 seconds" in answer.warnings[0] and "1 graph tools" in answer.warnings[0]
    assert answer.sources == [SOURCE]


def test_local_tool_limit_is_not_misreported_as_a_timeout():
    agent, _ = make_local([tool(), tool()], agent_max_tool_calls=1)
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "limit_reached"
    assert "tool-call limit" in answer.warnings[0] and "deadline" not in answer.warnings[0]


def test_local_deadline_defaults_support_old_env_settings_and_ui_overrides():
    assert local_settings().active_deadline_seconds == 300
    assert local_settings(agent_deadline_seconds=600).active_deadline_seconds == 600
    assert (
        local_settings(
            agent_deadline_seconds=600, ollama_deadline_seconds=450
        ).active_deadline_seconds
        == 450
    )
    assert (
        local_settings(
            agent_deadline_seconds=600, ollama_deadline_seconds=""
        ).active_deadline_seconds
        == 600
    )
    assert local_settings(llm_provider="openai").active_deadline_seconds == 60
    with pytest.raises(ValidationError):
        local_settings(ollama_deadline_seconds=901)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/v1",
        "http://host.docker.internal:11434/v1",
        "http://ollama:11434/v1",
        "http://192.168.1.20:11434/v1",
        "https://local-model.example/v1",
    ],
)
def test_local_endpoints_support_host_docker_and_private_lan(url):
    assert local_settings(ollama_base_url=url).ollama_base_url == url


@pytest.mark.parametrize(
    "url",
    [
        "http://public-model.example/v1",
        "https://user:secret@local.example/v1",
        "http://localhost:11434/v1?key=secret",
        "file:///tmp/model",
        "http://localhost:99999/v1",
    ],
)
def test_invalid_local_urls_are_rejected(url):
    with pytest.raises(ValidationError):
        local_settings(ollama_base_url=url)
