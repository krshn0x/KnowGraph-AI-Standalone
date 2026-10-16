import json
from types import SimpleNamespace

import httpx
import pytest

from knowgraph.agent import Agent
from knowgraph.config import DEFAULT_GEMINI_MODEL, Settings
from knowgraph.gemini import GEMINI_NATIVE_URL, GeminiClient
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
        "functionCall": {
            "id": identifier,
            "name": "search_entities",
            "args": {"query": "checkout", "kind": "Service"},
        }
    }
    if signature:
        result["thoughtSignature"] = signature
    return result


def final(citation=SERVICE.id):
    return {
        "role": "model",
        "parts": [
            {
                "text": json.dumps(
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
                )
            }
        ],
    }


def make_agent(messages, **updates):
    requests = []

    def handler(request):
        assert (
            str(request.url)
            == GEMINI_NATIVE_URL + f"/models/{DEFAULT_GEMINI_MODEL}:generateContent"
        )
        assert request.headers["x-goog-api-key"] == "gemini-test-secret"
        assert "authorization" not in request.headers
        requests.append(json.loads(request.content))
        message = messages[min(len(requests) - 1, len(messages) - 1)]
        if isinstance(message, httpx.Response):
            return message
        return httpx.Response(
            200, json={"candidates": [{"finishReason": "STOP", "content": message}]}
        )

    client = GeminiClient("gemini-test-secret", transport=httpx.MockTransport(handler))
    retrieval = SimpleNamespace(store=SimpleNamespace(search=lambda *a, **kw: [SERVICE]))
    return Agent(retrieval, settings(**updates), client=client), requests


def test_native_gemini_replays_all_parts_signatures_and_parallel_results_verbatim():
    first = {
        "role": "model",
        "parts": [
            {
                "text": "private reasoning",
                "thought": True,
                "thoughtSignature": "thought-part-signature",
            },
            call(),
            call("call_2", None),
        ],
    }
    second = {"role": "model", "parts": [call("call_3", "second-google-signature")]}
    agent, requests = make_agent([first, second, final()])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "ok" and answer.sources == [SERVICE]
    assert requests[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert "responseMimeType" not in requests[0]["generationConfig"]
    assert len(requests[0]["tools"][0]["functionDeclarations"]) == 5
    replay = requests[1]["contents"]
    assert replay[-2] == first
    assert [p["functionResponse"]["id"] for p in replay[-1]["parts"]] == ["call_1", "call_2"]
    assert requests[2]["contents"][-2] == second
    assert "google-signature" not in answer.model_dump_json()
    assert "private reasoning" not in answer.model_dump_json()
    assert "gemini-test-secret" not in answer.model_dump_json()


def test_native_gemini_cap_uses_json_schema_without_functions():
    agent, requests = make_agent(
        [{"role": "model", "parts": [call()]}, final()], agent_max_tool_calls=1
    )
    assert agent.ask(AskRequest(question="checkout")).status == "ok"
    assert requests[-1]["generationConfig"]["responseMimeType"] == "application/json"
    assert requests[-1]["generationConfig"]["responseJsonSchema"]["type"] == "object"
    assert "tools" not in requests[-1]


def test_native_gemini_finishes_prose_with_a_separate_schema_enforced_answer():
    agent, requests = make_agent(
        [
            {"role": "model", "parts": [call()]},
            {"role": "model", "parts": [{"text": "Checkout is a service in the graph."}]},
            final(),
        ]
    )
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "ok" and answer.claims
    assert len(requests) == 3
    assert requests[-1]["generationConfig"]["responseJsonSchema"]["required"]
    assert "tools" not in requests[-1]
    assert requests[-1]["contents"][-1]["role"] == "user"


@pytest.mark.parametrize(
    "message", [final("invented:source"), {"role": "model", "parts": [{"text": "invalid JSON"}]}]
)
def test_gemini_invalid_answers_preserve_evidence_without_unsupported_claims(message):
    agent, _ = make_agent([{"role": "model", "parts": [call()]}, message])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and not answer.claims
    assert answer.evidence.nodes == [SERVICE]
    assert "invalid" in answer.warnings[0]


@pytest.mark.parametrize(
    "status,reason,expected",
    [
        (400, "API_KEY_INVALID", "rejected the Gemini API key"),
        (403, "SERVICE_DISABLED", "denied"),
        (404, "", "could not find"),
        (429, "", "quota or rate limit"),
        (500, "", "HTTP 500"),
    ],
)
def test_native_gemini_errors_are_actionable_sanitized_and_never_retry(status, reason, expected):
    agent, requests = make_agent(
        [
            httpx.Response(
                status,
                json={
                    "error": {
                        "message": "private-provider-details",
                        "details": [{"reason": reason}],
                    }
                },
            )
        ]
    )
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and not answer.claims
    assert expected in answer.warnings[0]
    assert "private-provider-details" not in answer.model_dump_json()
    assert len(requests) == 1


def test_gemini_uses_only_native_google_endpoint_and_selected_key():
    agent = Agent(SimpleNamespace(), settings())
    assert isinstance(agent.client, GeminiClient)
    assert agent.client.http.headers["x-goog-api-key"] == "gemini-test-secret"
    agent.client.close()
    missing = Agent(
        SimpleNamespace(store=SimpleNamespace(search=lambda *a, **kw: [])),
        settings(gemini_api_key=""),
    )
    assert missing.client is None
    assert "GEMINI_API_KEY" in missing.ask(AskRequest(question="checkout")).warnings[0]


def test_native_gemini_handles_optional_function_call_ids_and_history():
    part = call()
    del part["functionCall"]["id"]
    agent, requests = make_agent([{"role": "model", "parts": [part]}, final()])
    answer = agent.ask(
        AskRequest(
            question="checkout", history=[{"role": "assistant", "content": "Previous summary"}]
        )
    )
    assert answer.status == "ok"
    assert requests[0]["contents"][0] == {"role": "model", "parts": [{"text": "Previous summary"}]}
    assert "id" not in requests[1]["contents"][-1]["parts"][0]["functionResponse"]
