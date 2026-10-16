import json
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI

from knowgraph.agent import Agent
from knowgraph.config import DEFAULT_GEMINI_MODEL, GEMINI_BASE_URL, Settings
from knowgraph.models import AskRequest, Entity

SERVICE = Entity(
    id="demo:checkout", kind="Service", title="Checkout", source_ref="fixture://checkout"
)


def settings(**updates):
    return Settings(
        **{
            "llm_provider": "gemini",
            "gemini_api_key": "gemini-test-secret",
            "gemini_model": DEFAULT_GEMINI_MODEL,
            "openai_api_key": "unrelated-openai-key",
            "agentrouter_api_key": "unrelated-router-key",
            **updates,
        }
    )


def call(identifier="call_1", signature="opaque-google-signature"):
    result = {
        "id": identifier,
        "type": "function",
        "function": {
            "name": "search_entities",
            "arguments": json.dumps({"query": "checkout", "kind": "Service"}),
        },
    }
    if signature:
        result["extra_content"] = {"google": {"thought_signature": signature}}
    return result


def final(citation=SERVICE.id):
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


def make_agent(messages, **updates):
    requests = []

    def handler(request):
        assert str(request.url) == GEMINI_BASE_URL + "/chat/completions"
        assert request.headers["authorization"] == "Bearer gemini-test-secret"
        requests.append(json.loads(request.content))
        message = messages[len(requests) - 1]
        if isinstance(message, httpx.Response):
            return message
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_gemini",
                "object": "chat.completion",
                "created": 0,
                "model": DEFAULT_GEMINI_MODEL,
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
        api_key="gemini-test-secret",
        base_url=GEMINI_BASE_URL,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    retrieval = SimpleNamespace(store=SimpleNamespace(search=lambda *a, **kw: [SERVICE]))
    return Agent(retrieval, settings(**updates), client=client), requests


def test_gemini_replays_all_thought_signatures_and_preserves_tool_result_order():
    agent, requests = make_agent(
        [
            {"role": "assistant", "content": None, "tool_calls": [call(), call("call_2", None)]},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [call("call_3", "second-google-signature")],
            },
            final(),
        ]
    )
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "ok" and answer.sources == [SERVICE]
    assert requests[0]["model"] == DEFAULT_GEMINI_MODEL
    assert requests[0]["reasoning_effort"] == "low"
    assert "response_format" not in requests[0]
    replay = requests[1]["messages"]
    assert [m["role"] for m in replay[-3:]] == ["assistant", "tool", "tool"]
    assert (
        replay[-3]["tool_calls"][0]["extra_content"]["google"]["thought_signature"]
        == "opaque-google-signature"
    )
    assert "extra_content" not in replay[-3]["tool_calls"][1]
    assert replay[-2]["tool_call_id"] == "call_1" and replay[-1]["tool_call_id"] == "call_2"
    signatures = [
        c["extra_content"]["google"]["thought_signature"]
        for m in requests[2]["messages"]
        for c in m.get("tool_calls", [])
        if "extra_content" in c
    ]
    assert signatures == ["opaque-google-signature", "second-google-signature"]
    assert "google-signature" not in answer.model_dump_json()
    assert "gemini-test-secret" not in answer.model_dump_json()


def test_gemini_tool_cap_finishes_with_json_without_functions():
    agent, requests = make_agent(
        [{"role": "assistant", "content": None, "tool_calls": [call()]}, final()],
        agent_max_tool_calls=1,
    )
    assert agent.ask(AskRequest(question="checkout")).status == "ok"
    assert requests[-1]["response_format"] == {"type": "json_object"}
    assert "tools" not in requests[-1] and "tool_choice" not in requests[-1]


@pytest.mark.parametrize(
    "message", [final("invented:source"), {"role": "assistant", "content": "invalid JSON"}]
)
def test_gemini_invalid_answers_preserve_evidence_without_unsupported_claims(message):
    agent, _ = make_agent([{"role": "assistant", "content": None, "tool_calls": [call()]}, message])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and not answer.claims
    assert answer.evidence.nodes == [SERVICE]


def test_gemini_quota_error_does_not_retry_or_fall_back_to_other_provider_keys():
    agent, requests = make_agent(
        [httpx.Response(429, json={"error": {"message": "private-provider-details"}})]
    )
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and not answer.claims
    assert "quota or rate limit" in answer.warnings[0]
    assert "private-provider-details" not in answer.model_dump_json()
    assert len(requests) == 1


def test_gemini_uses_only_the_google_endpoint_and_selected_key():
    agent = Agent(SimpleNamespace(), settings())
    assert str(agent.client.base_url) == GEMINI_BASE_URL + "/"
    assert agent.client.api_key == "gemini-test-secret"
    agent.client.close()
    configured = settings(gemini_api_key="")
    missing = Agent(SimpleNamespace(store=SimpleNamespace(search=lambda *a, **kw: [])), configured)
    assert missing.client is None
    assert "GEMINI_API_KEY" in missing.ask(AskRequest(question="checkout")).warnings[0]
