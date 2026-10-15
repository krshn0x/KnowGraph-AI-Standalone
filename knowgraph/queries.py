def incident_evidence(graph, incident_id: str) -> list:
    """Return evidence-backed paths linking an incident to a deployment and change."""
    result = graph.query(
        "MATCH p=(i:Incident {id: $incident_id})<-[:TRIGGERED]-(d:Deployment) "
        "-[:DEPLOYED]->(s:Service)<-[:CHANGED]-(pr:PullRequest) "
        "OPTIONAL MATCH (person:Person)-[:AUTHORED]->(pr) "
        "RETURN i, d, s, pr, person, relationships(p) AS evidence_edges",
        {"incident_id": incident_id},
    )
    return result.result_set


def count_nodes_by_label(graph) -> dict[str, int]:
    counts = {}
    for label in ("Person", "Service", "PullRequest", "Commit", "Incident", "Ticket", "Document", "Deployment"):
        result = graph.query(f"MATCH (n:{label}) RETURN count(n)")
        counts[label] = result.result_set[0][0]
    return counts
