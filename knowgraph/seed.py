from collections import defaultdict

from knowgraph.dataset import EDGES, NODES


def seed_graph(graph) -> dict[str, int]:
    """Idempotently MERGE synthetic nodes and cited evidence edges."""
    counts = defaultdict(int)
    for label, entity_id, properties in NODES:
        fields = {"id": entity_id, **properties}
        keys = list(fields)
        assignments = ", ".join(f"n.{key} = ${key}" for key in keys if key != "id")
        query = f"MERGE (n:{label} {{id: $id}}) SET {assignments} RETURN n.id"
        graph.query(query, fields)
        counts["nodes"] += 1
    for rel_type, start_id, end_id, source_id, excerpt in EDGES:
        query = (
            "MATCH (a {id: $start_id}), (b {id: $end_id}) "
            f"MERGE (a)-[r:{rel_type} {{source_id: $source_id}}]->(b) "
            "SET r.evidence_kind = 'synthetic_record', r.evidence_excerpt = $excerpt "
            "RETURN type(r)"
        )
        graph.query(query, {"start_id": start_id, "end_id": end_id, "source_id": source_id, "excerpt": excerpt})
        counts["edges"] += 1
    return dict(counts)
