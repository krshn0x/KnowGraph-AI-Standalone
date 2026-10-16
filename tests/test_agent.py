import json
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI

from knowgraph.agent import Agent
from knowgraph.config import Settings
from knowgraph.models import AskRequest, Entity, Evidence, ExpertResult

SERVICE = Entity(
    id="demo:checkout", kind="Service", title="Checkout", source_ref="fixture://checkout"
)


class StubRetrieval:
    def __init__(self):
        self.store = SimpleNamespace(search=self.search)

    def search(self, query, *args, **kwargs):
        return [SERVICE] if "checkout" in query.lower() else []

    def experts(self, query):
        return ExpertResult(experts=[], evidence=Evidence(nodes=[SERVICE]))


def final(claim_ids=None, text="Checkout is a recorded service."):
    draft = {
        "summary": text,
        "claims": [{"text": text, "evidence_ids": claim_ids, "certainty": "observed"}]
        if claim_ids
        else [],
        "insufficient_evidence": not claim_ids,
    }
    return [
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": json.dumps(draft), "annotations": []}],
        }
    ]


def tool(name="search_entities", arguments=None, call_id="call_1"):
    return [
        {
            "id": "fc_1",
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": json.dumps(arguments or {"query": "checkout", "kind": "Service"}),
            "status": "completed",
        }
    ]


def make_agent(outputs, **settings):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        value = outputs[len(requests) - 1]
        if isinstance(value, Exception):
            raise value
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-6.1-sol",
                "output": value,
            },
        )

    client = OpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    agent = Agent(StubRetrieval(), Settings(openai_api_key="", **settings), client=client)
    return agent, requests


def test_sdk_tool_round_trip_uses_only_retrieved_citations():
    agent, requests = make_agent([tool(), final([SERVICE.id])])
    answer = agent.ask(AskRequest(question="Tell me about checkout"))
    assert answer.status == "ok"
    assert answer.claims[0].evidence_ids == [SERVICE.id]
    assert [n.id for n in answer.sources] == [SERVICE.id]
    assert answer.tool_calls == ["search_entities"]
    assert requests[0]["parallel_tool_calls"] is False
    assert requests[0]["text"]["format"]["strict"] is True
    assert requests[0]["store"] is False
    assert any(item.get("type") == "function_call_output" for item in requests[1]["input"])
    assert {t["name"] for t in requests[0]["tools"]} == {
        "search_entities",
        "investigate_incident",
        "find_experts",
        "find_documents",
        "get_evidence_paths",
    }


def test_fabricated_citation_never_reaches_the_user():
    agent, _ = make_agent([tool(), final(["demo:invented"], text="Invented root cause")])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error" and not answer.claims
    assert "Invented" not in answer.summary
    assert [n.id for n in answer.evidence.nodes] == [SERVICE.id]


def test_no_matching_evidence_does_not_accept_an_uncited_summary():
    agent, _ = make_agent([final(text="An unsupported root cause")])
    answer = agent.ask(AskRequest(question="unknown topic"))
    assert answer.status == "insufficient_evidence"
    assert "unsupported root cause" not in answer.summary
    assert not answer.claims


def test_missing_key_still_returns_deterministic_source_records():
    agent = Agent(StubRetrieval(), Settings(openai_api_key=""))
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error"
    assert answer.sources and not answer.claims and not answer.tool_calls
    assert "OPENAI_API_KEY" in answer.warnings[0]


def test_provider_failure_after_retrieval_preserves_evidence():
    agent, _ = make_agent([tool(), httpx.ReadTimeout("provider slow")])
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "provider_error"
    assert answer.evidence.nodes == [SERVICE]


def test_tool_limit_forces_a_final_response_without_more_tool_calls():
    agent, requests = make_agent([tool(), final([SERVICE.id])], agent_max_tool_calls=1)
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "ok"
    assert requests[-1]["tool_choice"] == "none"
    assert len(answer.tool_calls) == 1


def test_model_cannot_bypass_tool_limit():
    agent, _ = make_agent([tool(), tool(call_id="call_2")], agent_max_tool_calls=1)
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "limit_reached"
    assert len(answer.tool_calls) == 1


def test_history_is_forwarded_but_old_citations_need_fresh_retrieval():
    agent, requests = make_agent([final([SERVICE.id])])
    answer = agent.ask(
        AskRequest(
            question="And who owns it?",
            history=[
                {"role": "assistant", "content": "Checkout demo:checkout was mentioned earlier."}
            ],
        )
    )
    assert requests[0]["input"][0]["role"] == "assistant"
    assert answer.status == "provider_error" and not answer.claims


def test_invalid_tool_arguments_are_returned_to_the_model_as_errors():
    agent, requests = make_agent(
        [tool(arguments={"query": "checkout", "kind": "NotALabel"}), final()]
    )
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "insufficient_evidence"
    output = requests[-1]["input"][-1]
    assert output["type"] == "function_call_output"
    assert "error" in json.loads(output["output"])


def test_deadline_is_checked_before_accepting_a_late_response(monkeypatch):
    agent, _ = make_agent([tool()])
    times = iter([0, 0, 61])
    monkeypatch.setattr("knowgraph.agent.time.monotonic", lambda: next(times))
    answer = agent.ask(AskRequest(question="checkout"))
    assert answer.status == "limit_reached"
    assert not answer.claims


@pytest.mark.parametrize(
    "name,arguments",
    [("delete_graph", {}), ("get_evidence_paths", {"node_id": "demo:checkout", "hops": 4})],
)
def test_unapproved_tools_and_unbounded_traversals_are_rejected(name, arguments):
    agent = Agent(StubRetrieval(), Settings(openai_api_key=""))
    with pytest.raises(ValueError):
        agent.execute(name, json.dumps(arguments))
