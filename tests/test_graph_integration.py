from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knowgraph.agent import Agent
from knowgraph.api import create_app
from knowgraph.config import Settings
from knowgraph.ingestion import ingest, parse_json
from knowgraph.models import Bundle, EdgeInput, Kind, NodeInput
from knowgraph.retrieval import Retrieval

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[1]


def test_initialization_and_import_are_idempotent(store):
    store.initialize()
    before = store.counts()
    result = ingest(store, parse_json((ROOT / "data/demo.json").read_bytes()))
    assert result.unchanged == 322
    assert store.counts() == before == {"nodes": 113, "edges": 209}


def test_checkout_lineage_excludes_distractors(store):
    result = Retrieval(store).investigate("demo:inc-checkout")
    assert {d.id for d in result.deployments} == {"demo:deploy-checkout-retry"}
    ids = {n.id for n in result.evidence.nodes}
    assert {"demo:commit-checkout-retry", "demo:pr-checkout-retry", "demo:ada", "demo:nina"} <= ids
    assert (
        not {
            "demo:deploy-analytics-chart",
            "demo:deploy-checkout-future",
            "demo:deploy-checkout-staging",
            "demo:deploy-checkout-old",
        }
        & ids
    )
    assert result.timeline == sorted(result.timeline, key=lambda n: n.occurred_at)


def test_dependency_failure_and_recurring_incident(store):
    retrieval = Retrieval(store)
    payments = retrieval.investigate("demo:inc-payments")
    assert "demo:deploy-ledger-pool" in {d.id for d in payments.deployments}
    assert "demo:bruno" in {n.id for n in payments.evidence.nodes}
    queue = retrieval.investigate("demo:inc-queue")
    assert not queue.deployments
    assert {i.id for i in queue.related_incidents} == {"demo:inc-queue-old", "demo:inc-queue-older"}


def test_experts_have_distinct_scored_records_and_paths(store):
    result = Retrieval(store).experts("demo:checkout")
    assert result.experts[0].person.id == "demo:nina"
    assert result.experts[0].score == 13  # two resolved incidents, two changes, three docs
    assert len(result.experts[0].reasons) == 7
    assert result.evidence.paths
    assert Retrieval(store).experts("demo:queue-worker").experts[0].person.id == "demo:mei"


def test_fulltext_and_connected_documents(store):
    retrieval = Retrieval(store)
    docs = retrieval.documents("retry saturation")
    assert "demo:doc-checkout-runbook" in {d.id for d in docs.documents}
    docs = retrieval.documents("demo:checkout")
    assert "demo:ticket-checkout-1" in {d.id for d in docs.documents}
    assert docs.evidence.paths
    assert store.search("fizzquux-no-such-topic") == []
    assert store.search("fizzquux", [Kind.INCIDENT]) == []
    assert store.search("@title:(*) OR 1=1") is not None  # treated as terms, not query operators


def test_bounded_neighborhood_has_valid_paths(store):
    result = store.neighborhood("demo:checkout", hops=3, limit=8)
    assert len(result.nodes) <= 8
    assert result.truncated
    nodes = {n.id for n in result.nodes}
    edges = {e.id: e for e in result.edges}
    for path in result.paths:
        assert set(path.node_ids) <= nodes
        assert len(path.node_ids) == len(path.edge_ids) + 1
        for i, edge_id in enumerate(path.edge_ids):
            assert {edges[edge_id].source, edges[edge_id].target} == set(path.node_ids[i : i + 2])


def test_resolution_update_changes_retrieval_and_preserves_identity(store):
    retrieval = Retrieval(store)
    assert not any(
        n.id == "demo:doc-checkout-resolution"
        for n in retrieval.investigate("demo:inc-checkout").evidence.nodes
    )
    result = ingest(store, parse_json((ROOT / "data/resolution_update.json").read_bytes()))
    assert (result.created, result.updated) == (6, 1)
    updated = retrieval.investigate("demo:inc-checkout")
    assert updated.incident.status == "resolved"
    assert "demo:doc-checkout-resolution" in {n.id for n in updated.evidence.nodes}
    assert store.counts() == {"nodes": 114, "edges": 214}
    assert (
        ingest(store, parse_json((ROOT / "data/resolution_update.json").read_bytes())).unchanged
        == 7
    )


def test_api_contracts_and_validation(store):
    agent = Agent(Retrieval(store), Settings(llm_provider="openai", openai_api_key=""))
    with TestClient(create_app(store, agent)) as client:
        assert client.get("/health").json()["nodes"] == 113
        assert len(client.get("/entities", params={"kind": "Service"}).json()) == 6
        assert client.get("/entities/demo:inc-checkout").status_code == 200
        assert client.get("/incidents/missing/investigation").status_code == 404
        assert (
            client.get(
                "/graph/neighborhood", params={"node_id": "demo:checkout", "hops": 4}
            ).status_code
            == 422
        )
        assert client.get("/experts", params={"q": "demo:checkout"}).json()["experts"]
        assert client.get("/documents", params={"q": "retry"}).json()["documents"]
        answer = client.post("/ask", json={"question": "checkout"}).json()
        assert answer["status"] == "provider_error" and answer["sources"]
        response = client.post(
            "/ingest", files={"bundle_file": ("demo.json", (ROOT / "data/demo.json").read_bytes())}
        )
        assert response.status_code == 200 and response.json()["unchanged"] == 322
        bad = b'{"edges":[{"source":"demo:checkout","kind":"DEPENDS_ON","target":"demo:missing"}]}'
        response = client.post("/ingest", files={"bundle_file": ("bad.json", bad)})
        assert response.status_code == 422 and response.json()["rejected"] == 1
        assert client.post("/ingest").status_code == 422
        assert client.post("/ingest", files={"bundle_file": ("bad.json", b"{")}).status_code == 422
        assert store.counts() == {"nodes": 113, "edges": 209}
        assert len(store.list_entities(Kind.INCIDENT)) == 9


def test_csv_import_and_source_qualified_incident_paths(store):
    agent = Agent(Retrieval(store), Settings(llm_provider="openai", openai_api_key=""))
    with TestClient(create_app(store, agent)) as client:
        result = client.post(
            "/ingest",
            files={
                "nodes_file": ("nodes.csv", (ROOT / "data/nodes.csv").read_bytes()),
                "edges_file": ("edges.csv", (ROOT / "data/edges.csv").read_bytes()),
            },
        )
        assert result.status_code == 200 and result.json()["unchanged"] == 322
        result = ingest(
            store,
            Bundle(
                nodes=[
                    NodeInput(
                        id="company:team/inc-42",
                        kind="Incident",
                        title="An unlinked incident",
                        source_ref="fixture://inc-42",
                        occurred_at="2026-10-15T10:00:00Z",
                    )
                ]
            ),
        )
        assert result.created == 1
        assert client.get("/incidents/company:team/inc-42/investigation").status_code == 200
        assert (
            client.post(
                "/ingest", files={"bundle_file": ("large.json", b" " * (8 * 1024 * 1024 + 1))}
            ).status_code
            == 413
        )


def test_partial_edge_import_preserves_provenance_and_serializes_writers(store):
    from concurrent.futures import ThreadPoolExecutor

    edge = EdgeInput(source="demo:checkout", kind="DEPENDS_ON", target="demo:payments")
    original = store.edge_properties(edge)["source_ref"]
    assert ingest(store, Bundle(edges=[edge])).unchanged == 1
    assert store.edge_properties(edge)["source_ref"] == original
    new = Bundle(
        nodes=[
            NodeInput(
                id="demo:concurrent",
                kind="Service",
                title="Concurrent",
                source_ref="fixture://concurrent",
            )
        ]
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: ingest(store, new), range(2)))
    assert sorted(r.created for r in results) == [0, 1]
    assert sorted(r.unchanged for r in results) == [0, 1]
