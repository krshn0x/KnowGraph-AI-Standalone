from collections import Counter

from knowgraph.db import check_connection
from knowgraph.dataset import EDGES, NODES
from knowgraph.queries import count_nodes_by_label, incident_evidence
from knowgraph.schema import EVIDENCE_RELATIONSHIPS, INFERRED_RELATIONSHIP, NODE_LABELS
from knowgraph.seed import seed_graph


class Result:
    def __init__(self, rows):
        self.result_set = rows


class MemoryGraph:
    """Small query-aware test double; integration behavior is covered separately."""
    def __init__(self):
        self.nodes = {}
        self.edges = {}

    def query(self, query, params=None):
        params = params or {}
        if query.startswith("RETURN 1"):
            return Result([[1]])
        if "MATCH p=(i:Incident" in query:
            self.last_query = query
            self.last_params = params
            return Result([["incident-path"]])
        if "MERGE (n:" in query:
            label = query.split("MERGE (n:", 1)[1].split(" ", 1)[0]
            self.nodes[(label, params["id"])] = params
            return Result([[params["id"]]])
        if "MERGE (a)-[r:" in query:
            rel = query.split("MERGE (a)-[r:", 1)[1].split(" ", 1)[0]
            self.edges[(rel, params["start_id"], params["end_id"], params["source_id"])] = params
            return Result([[rel]])
        if query.startswith("MATCH (n:"):
            label = query.split("MATCH (n:", 1)[1].split(")", 1)[0]
            return Result([[sum(1 for node_label, _ in self.nodes if node_label == label)]])
        raise AssertionError(f"Unexpected query: {query}")


def test_connection_check_uses_graph_query():
    assert check_connection(MemoryGraph()) is True


def test_schema_and_fixture_cover_requested_types_and_keep_edges_evidenced():
    assert set(NODE_LABELS) == {label for label, _, _ in NODES}
    assert set(EVIDENCE_RELATIONSHIPS) == {edge[0] for edge in EDGES}
    assert INFERRED_RELATIONSHIP not in EVIDENCE_RELATIONSHIPS
    assert all(edge[3] for edge in EDGES)


def test_seed_is_idempotent_and_basic_label_counts_work():
    graph = MemoryGraph()
    expected = {"nodes": len(NODES), "edges": len(EDGES)}
    assert seed_graph(graph) == expected
    assert seed_graph(graph) == expected
    assert len(graph.nodes) == len(NODES)
    assert len(graph.edges) == len(EDGES)
    assert count_nodes_by_label(graph) == dict(Counter({label: sum(1 for item in NODES if item[0] == label) for label in NODE_LABELS}))


def test_incident_query_requests_connected_evidence_path():
    graph = MemoryGraph()
    assert incident_evidence(graph, "inc-2026-104") == [["incident-path"]]
    assert graph.last_params == {"incident_id": "inc-2026-104"}
    assert "TRIGGERED" in graph.last_query
    assert "CHANGED" in graph.last_query
