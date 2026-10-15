"""Opt-in tests against a real local FalkorDB: RUN_FALKORDB_INTEGRATION=1 pytest."""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_FALKORDB_INTEGRATION") != "1", reason="set RUN_FALKORDB_INTEGRATION=1 with FalkorDB running"
)


def test_real_falkordb_connect_seed_and_query():
    from knowgraph.db import check_connection, connect
    from knowgraph.dataset import EDGES, NODES
    from knowgraph.queries import count_nodes_by_label, incident_evidence
    from knowgraph.seed import seed_graph

    graph = connect()
    assert check_connection(graph)
    expected = {"nodes": len(NODES), "edges": len(EDGES)}
    assert seed_graph(graph) == expected

    def assert_fixture_records_are_unique():
        for label, entity_id, _properties in NODES:
            result = graph.query(f"MATCH (n:{label} {{id: $id}}) RETURN count(n)", {"id": entity_id})
            assert result.result_set[0][0] == 1, f"Expected one {label} record for {entity_id}"
        for rel_type, start_id, end_id, source_id, _excerpt in EDGES:
            result = graph.query(
                f"MATCH (a {{id: $start_id}})-[r:{rel_type} {{source_id: $source_id}}]->(b {{id: $end_id}}) "
                "RETURN count(r)",
                {"start_id": start_id, "end_id": end_id, "source_id": source_id},
            )
            assert result.result_set[0][0] == 1, f"Expected one {rel_type} edge from {start_id} to {end_id}"

    assert_fixture_records_are_unique()
    first_counts = count_nodes_by_label(graph)
    path_rows = incident_evidence(graph, "inc-2026-104")
    assert path_rows, "Expected an incident/deployment/service/pull-request evidence path"
    assert len(path_rows[0]) >= 5

    assert seed_graph(graph) == expected
    assert_fixture_records_are_unique()
    assert count_nodes_by_label(graph) == first_counts
