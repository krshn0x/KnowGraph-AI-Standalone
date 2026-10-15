"""Allowlisted, read-only Cypher retrieval functions and graph record formatting."""
import re

from knowgraph.models import GraphNode, GraphPath, GraphRelationship, SupportingFact
from knowgraph.queries import incident_evidence

STOP_WORDS = {
    "about", "after", "before", "because", "could", "does", "failing", "failure", "from", "have",
    "into", "latest", "started", "that", "the", "their", "there", "this", "what", "when", "where",
    "which", "while", "with", "would", "why", "was", "were", "will",
}


def query_terms(question: str) -> list[str]:
    terms = [word.lower() for word in re.findall(r"[A-Za-z0-9_-]{3,}", question)]
    return list(dict.fromkeys(term for term in terms if term not in STOP_WORDS))[:6]


def _node(value) -> GraphNode | None:
    if value is None:
        return None
    props = dict(value.properties)
    return GraphNode(id=str(props.get("id", "")), label=value.labels[0], properties=props)


def _edge(value, start: GraphNode, end: GraphNode) -> GraphRelationship:
    props = dict(value.properties)
    return GraphRelationship(
        type=value.relation,
        start_id=start.id,
        end_id=end.id,
        source_id=str(props.get("source_id", "")),
        evidence_kind=str(props.get("evidence_kind", "")),
        evidence_excerpt=str(props.get("evidence_excerpt", "")),
    )


def search_incidents(graph, term: str) -> list[GraphNode]:
    result = graph.query(
        "MATCH (i:Incident) OPTIONAL MATCH (i)<-[:TRIGGERED]-(:Deployment)-[:DEPLOYED]->(s:Service) "
        "WHERE toLower(i.id) CONTAINS toLower($term) OR toLower(i.title) CONTAINS toLower($term) "
        "OR toLower(coalesce(s.name, '')) CONTAINS toLower($term) RETURN DISTINCT i LIMIT 10",
        {"term": term[:100]},
    )
    return [_node(row[0]) for row in result.result_set if row and row[0] is not None]


def incident_paths(graph, incident_id: str) -> list[GraphPath]:
    paths: list[GraphPath] = []
    for index, row in enumerate(incident_evidence(graph, incident_id)):
        incident, deployment, service, pr, person, edges = row
        incident_n, deployment_n, service_n, pr_n, person_n = map(_node, (incident, deployment, service, pr, person))
        nodes = [incident_n, deployment_n, service_n, pr_n]
        # The primary path follows the three returned relationships. Include its
        # author as a separate one-edge path below, since OPTIONAL MATCH is not part of p.
        usable_nodes = [node for node in nodes if node is not None]
        if len(usable_nodes) >= 4:
            rels = [
                _edge(edges[0], deployment_n, incident_n),
                _edge(edges[1], deployment_n, service_n),
                _edge(edges[2], pr_n, service_n),
            ]
            paths.append(GraphPath(id=f"{incident_id}:change:{index}", nodes=usable_nodes, relationships=rels))
        if person_n is not None and pr_n is not None:
            author_result = graph.query(
                "MATCH (person:Person {id: $person_id})-[r:AUTHORED]->(pr:PullRequest {id: $pr_id}) "
                "RETURN person, r, pr",
                {"person_id": person_n.id, "pr_id": pr_n.id},
            )
            for author_row in author_result.result_set:
                person_value, author_edge, pr_value = author_row
                person_node, pr_node = _node(person_value), _node(pr_value)
                if person_node and pr_node:
                    paths.append(GraphPath(
                        id=f"{incident_id}:author:{person_node.id}:{pr_node.id}",
                        nodes=[person_node, pr_node],
                        relationships=[_edge(author_edge, person_node, pr_node)],
                    ))
    return paths


def related_records(graph, incident_id: str) -> tuple[list[GraphPath], list[str]]:
    """Fetch the incident's ticket, commits, docs, and optional existing dependency edges."""
    paths: list[GraphPath] = []
    limitations: list[str] = []
    queries = [
        (
            "MATCH (i:Incident {id: $incident_id})-[r:TRACKED_BY]->(t:Ticket) RETURN i, r, t",
            "ticket",
        ),
        (
            "MATCH (i:Incident {id: $incident_id})<-[:TRIGGERED]-(:Deployment)-[:DEPLOYED]->(s:Service) "
            "<-[changed:CHANGED]-(pr:PullRequest)-[contains:CONTAINS]->(c:Commit) "
            "RETURN s, changed, pr, contains, c",
            "commit",
        ),
        (
            "MATCH (i:Incident {id: $incident_id})<-[:TRIGGERED]-(:Deployment)-[:DEPLOYED]->(s:Service) "
            "-[r:DOCUMENTED_IN]->(d:Document) RETURN s, r, d",
            "document",
        ),
    ]
    for query, kind in queries:
        result = graph.query(query, {"incident_id": incident_id})
        for index, row in enumerate(result.result_set):
            if kind == "ticket":
                start, rel, end = row
                nodes = [_node(start), _node(end)]
                relationships = [_edge(rel, nodes[0], nodes[1])]
            elif kind == "commit":
                service, changed, pr, contains, commit = row
                nodes = [_node(service), _node(pr), _node(commit)]
                relationships = [_edge(changed, nodes[1], nodes[0]), _edge(contains, nodes[1], nodes[2])]
            else:
                service, rel, document = row
                nodes = [_node(service), _node(document)]
                relationships = [_edge(rel, nodes[0], nodes[1])]
            concrete = [node for node in nodes if node]
            if len(concrete) >= 2:
                paths.append(GraphPath(
                    id=f"{incident_id}:{kind}:{index}",
                    nodes=concrete,
                    relationships=relationships,
                ))

    # The schema currently has no DEPENDS_ON relationship. Inspect only explicit
    # Service-to-Service edges and retain dependency paths only when actually recorded.
    main = graph.query(
        "MATCH (i:Incident {id: $incident_id})<-[:TRIGGERED]-(:Deployment)-[:DEPLOYED]->(s:Service) "
        "RETURN s LIMIT 10",
        {"incident_id": incident_id},
    )
    seen_services = set()
    for row in main.result_set:
        service = _node(row[0])
        if not service or service.id in seen_services:
            continue
        seen_services.add(service.id)
        dependencies = graph.query(
            "MATCH (s:Service {id: $service_id})-[r]->(dependency:Service) RETURN s, r, dependency LIMIT 30",
            {"service_id": service.id},
        )
        for index, (source, edge, target) in enumerate(dependencies.result_set):
            if edge.relation == "DEPENDS_ON":
                source_n, target_n = _node(source), _node(target)
                paths.append(GraphPath(
                    id=f"{incident_id}:dependency:{index}",
                    nodes=[source_n, target_n],
                    relationships=[_edge(edge, source_n, target_n)],
                ))
    if not any(path.id.startswith(f"{incident_id}:dependency:") for path in paths):
        limitations.append("No service dependency edges are recorded for this incident in the current graph.")
    return paths, limitations


def facts_from_paths(paths: list[GraphPath]) -> list[SupportingFact]:
    facts = []
    for path in paths:
        node_by_id = {node.id: node for node in path.nodes}
        for relationship in path.relationships:
            if not relationship.source_id or not relationship.evidence_excerpt:
                continue
            start = node_by_id.get(relationship.start_id)
            end = node_by_id.get(relationship.end_id)
            start_name = (start.properties.get("title") or start.properties.get("name") or start.id) if start else relationship.start_id
            end_name = (end.properties.get("title") or end.properties.get("name") or end.id) if end else relationship.end_id
            fact_id = f"{relationship.source_id}|{relationship.type}|{relationship.start_id}|{relationship.end_id}"
            facts.append(SupportingFact(
                id=fact_id,
                statement=f"{start_name} --{relationship.type}--> {end_name}",
                source_id=relationship.source_id,
                evidence_excerpt=relationship.evidence_excerpt,
                path_id=path.id,
            ))
    unique = {fact.id: fact for fact in facts}
    return list(unique.values())
