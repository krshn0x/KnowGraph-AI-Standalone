from collections import defaultdict
import asyncio

import httpx

from knowgraph.agent import Investigator, NO_EVIDENCE_ANSWER
from knowgraph.api import create_app
from knowgraph.dataset import EDGES, NODES
from knowgraph.models import Hypothesis, OllamaAnalysis
from knowgraph.ollama import OllamaClient
from knowgraph.tools import facts_from_paths, incident_paths, related_records, search_incidents


class Node:
    def __init__(self, label, entity_id, properties):
        self.labels = [label]
        self.properties = {"id": entity_id, **properties}


class Edge:
    def __init__(self, edge_type, source_id, excerpt):
        self.relation = edge_type
        self.properties = {
            "source_id": source_id,
            "evidence_kind": "synthetic_record",
            "evidence_excerpt": excerpt,
        }


class FixtureGraph:
    def __init__(self):
        self.nodes = {entity_id: Node(label, entity_id, props) for label, entity_id, props in NODES}
        self.edges = {
            (edge_type, start, end): Edge(edge_type, source_id, excerpt)
            for edge_type, start, end, source_id, excerpt in EDGES
        }
        self.by_type = defaultdict(list)
        for edge_type, start, end, *_ in EDGES:
            self.by_type[edge_type].append((self.nodes[start], self.edges[(edge_type, start, end)], self.nodes[end]))

    def query(self, query, params=None):
        params = params or {}
        if query.startswith("RETURN 1"):
            return Result([[1]])
        if query.startswith("MATCH (i:Incident) OPTIONAL MATCH"):
            term = params["term"].lower()
            matches = [node for node in self.nodes.values() if "Incident" in node.labels and (
                term in node.properties["id"].lower() or term in node.properties["title"].lower()
            )]
            if term == "checkout":
                matches = [self.nodes["inc-2026-104"]]
            return Result([[item] for item in matches])
        if "MATCH p=(i:Incident" in query:
            incident = self.nodes.get(params["incident_id"])
            if not incident:
                return Result([])
            dep, service, pr = self.nodes["deploy-2026-10-14-17"], self.nodes["service-checkout"], self.nodes["pr-1842"]
            edges = [
                self.edges[("TRIGGERED", dep.properties["id"], incident.properties["id"])],
                self.edges[("DEPLOYED", dep.properties["id"], service.properties["id"])],
                self.edges[("CHANGED", pr.properties["id"], service.properties["id"])],
            ]
            person = self.nodes["person-maya"]
            return Result([[incident, dep, service, pr, person, edges]])
        if "r:AUTHORED" in query:
            person = self.nodes[params["person_id"]]
            pr = self.nodes[params["pr_id"]]
            return Result([[person, self.edges[("AUTHORED", person.properties["id"], pr.properties["id"])], pr]])
        if "r:TRACKED_BY" in query:
            return Result([self.by_type["TRACKED_BY"][0]])
        if "contains:CONTAINS" in query:
            changed = self.edges[("CHANGED", "pr-1842", "service-checkout")]
            pr, commit_edge, commit = self.by_type["CONTAINS"][0]
            return Result([[self.nodes["service-checkout"], changed, pr, commit_edge, commit]])
        if "r:DOCUMENTED_IN" in query:
            return Result([self.by_type["DOCUMENTED_IN"][0]])
        if "RETURN s LIMIT 10" in query:
            return Result([[self.nodes["service-checkout"]]])
        if "dependency:Service" in query:
            return Result([])
        raise AssertionError(f"Unexpected Cypher: {query}")


class Result:
    def __init__(self, result_set):
        self.result_set = result_set


class MockOllama:
    def __init__(self, analysis=None):
        self.analysis = analysis or OllamaAnalysis()
        self.calls = 0

    def available(self):
        return True

    def analyze(self, question, facts):
        self.calls += 1
        self.received_facts = facts
        return self.analysis


def test_graph_tools_return_actual_paths_people_docs_tickets_commits_and_dependency_limitation():
    graph = FixtureGraph()
    incidents = search_incidents(graph, "checkout")
    assert [item.id for item in incidents] == ["inc-2026-104"]
    paths = incident_paths(graph, incidents[0].id)
    supplemental, limitations = related_records(graph, incidents[0].id)
    all_paths = paths + supplemental
    rel_types = {rel.type for path in all_paths for rel in path.relationships}
    assert {"TRIGGERED", "DEPLOYED", "CHANGED", "AUTHORED", "TRACKED_BY", "CONTAINS", "DOCUMENTED_IN"} <= rel_types
    commit_path = next(path for path in all_paths if ":commit:" in path.id)
    assert len(commit_path.nodes) == 3 and len(commit_path.relationships) == 2
    assert any(node.label == "Person" and node.properties["name"] == "Maya Chen" for path in all_paths for node in path.nodes)
    assert any("dependency" in text for text in limitations)
    facts = facts_from_paths(all_paths)
    assert all(fact.source_id and fact.evidence_excerpt for fact in facts)


def test_investigator_only_keeps_claims_and_hypotheses_with_known_evidence_ids():
    graph = FixtureGraph()
    valid_fact_id = facts_from_paths(incident_paths(graph, "inc-2026-104"))[0].id
    llm = MockOllama(OllamaAnalysis(
        selected_fact_ids=[valid_fact_id, "invented-source"],
        hypotheses=[
            Hypothesis(text="The retry change may be relevant.", evidence_ids=[valid_fact_id]),
            Hypothesis(text="An unsupported guess.", evidence_ids=["made-up"]),
        ],
    ))
    response = Investigator(graph, llm).investigate("Why did checkout start failing after deployment?")
    assert "13 minutes after release" in response.answer
    assert "root cause" in response.answer
    assert "Payments provider X" not in response.answer
    assert len(response.supporting_facts) == 1
    assert response.source_ids == [response.supporting_facts[0].source_id]
    assert [hyp.text for hyp in response.hypotheses] == ["The retry change may be relevant."]
    assert response.graph_paths and response.relevant_people


def test_missing_evidence_returns_clear_answer_without_calling_llm():
    llm = MockOllama()
    response = Investigator(FixtureGraph(), llm).investigate("Tell me about an unrelated inventory system outage")
    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.supporting_facts == []
    assert response.source_ids == []
    assert response.limitations
    assert llm.calls == 0


def test_api_health_chat_and_request_validation():
    graph = FixtureGraph()
    fact_id = facts_from_paths(incident_paths(graph, "inc-2026-104"))[0].id
    llm = MockOllama(OllamaAnalysis(selected_fact_ids=[fact_id]))
    async def exercise_api():
        transport = httpx.ASGITransport(app=create_app(graph_factory=lambda: graph, ollama_factory=lambda: llm))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ready"
            assert "password" not in health.text.lower()
            result = await client.post("/chat", json={"question": "Why did checkout start failing?"})
            assert result.status_code == 200
            assert result.json()["source_ids"]
            assert (await client.post("/chat", json={"question": "x"})).status_code == 422
            assert (await client.post("/chat", json={})).status_code == 422

    asyncio.run(exercise_api())


def test_api_health_reports_graph_and_ollama_degradation():
    graph = FixtureGraph()

    class OfflineOllama:
        def available(self):
            return False

    class BrokenGraphFactory:
        def __call__(self):
            raise ConnectionError("private database connection detail")

    async def exercise_health():
        ollama_down = httpx.ASGITransport(
            app=create_app(graph_factory=lambda: graph, ollama_factory=OfflineOllama)
        )
        async with httpx.AsyncClient(transport=ollama_down, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "degraded"
            assert response.json()["graph_available"] is True
            assert response.json()["ollama_available"] is False
            chat = await client.post("/chat", json={"question": "Why did checkout fail?"})
            assert chat.status_code == 503
            assert chat.json()["detail"] == "Configured local Ollama model is unavailable"

        graph_down = httpx.ASGITransport(
            app=create_app(graph_factory=BrokenGraphFactory(), ollama_factory=MockOllama)
        )
        async with httpx.AsyncClient(transport=graph_down, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.json()["status"] == "degraded"
            assert health.json()["graph_available"] is False
            assert health.json()["ollama_available"] is True
            chat = await client.post("/chat", json={"question": "Why did checkout fail?"})
            assert chat.status_code == 503
            assert "private database" not in chat.text
            assert chat.json()["detail"] == "Graph database is unavailable"

    asyncio.run(exercise_health())


def test_ollama_health_checks_the_selected_installed_model():
    client = OllamaClient(base_url="http://localhost:11434", model="llama3:latest")
    client._request = lambda method, path, body=None: {"models": [{"name": "llama3:latest"}]}
    assert client.available()


def test_ollama_client_rejects_nonlocal_services():
    import pytest

    with pytest.raises(ValueError, match="local loopback"):
        OllamaClient(base_url="https://api.ollama.com")
