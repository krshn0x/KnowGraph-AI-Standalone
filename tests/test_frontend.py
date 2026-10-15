from frontend.presentation import build_graphviz, expert_reasons, source_catalog


def response_fixture():
    return {
        "graph_paths": [
            {
                "id": "incident-change",
                "nodes": [
                    {"id": "inc-1", "label": "Incident", "properties": {"id": "inc-1", "title": "Checkout errors"}},
                    {"id": "dep-1", "label": "Deployment", "properties": {"id": "dep-1", "version": "v1"}},
                    {"id": "svc-1", "label": "Service", "properties": {"id": "svc-1", "name": "checkout"}},
                    {"id": "pr-1", "label": "PullRequest", "properties": {"id": "pr-1", "title": "Retry change"}},
                    {"id": "person-1", "label": "Person", "properties": {"id": "person-1", "name": "Maya Chen"}},
                ],
                "relationships": [
                    {"type": "TRIGGERED", "start_id": "dep-1", "end_id": "inc-1", "source_id": "inc-1", "evidence_kind": "synthetic_record", "evidence_excerpt": "Started after release"},
                    {"type": "DEPLOYED", "start_id": "dep-1", "end_id": "svc-1", "source_id": "dep-1", "evidence_kind": "synthetic_record", "evidence_excerpt": "Release v1"},
                    {"type": "CHANGED", "start_id": "pr-1", "end_id": "svc-1", "source_id": "pr-1", "evidence_kind": "synthetic_record", "evidence_excerpt": "Changed checkout"},
                    {"type": "AUTHORED", "start_id": "person-1", "end_id": "pr-1", "source_id": "pr-1", "evidence_kind": "synthetic_record", "evidence_excerpt": "PR author"},
                ],
            }
        ],
        "supporting_facts": [
            {"source_id": "inc-1", "evidence_excerpt": "Started after release", "statement": "Deployment linked to incident"},
            {"source_id": "pr-1", "evidence_excerpt": "Changed checkout", "statement": "PR changed service"},
        ],
        "relevant_people": [
            {"id": "person-1", "label": "Person", "properties": {"id": "person-1", "name": "Maya Chen", "role": "Engineer"}}
        ],
    }


def test_graphviz_contains_only_returned_nodes_and_directed_edges():
    dot = build_graphviz(response_fixture()["graph_paths"])
    assert dot
    assert "TRIGGERED" in dot and 'n1 -> n0' in dot
    assert 'n3 -> n2' in dot  # CHANGED is PullRequest -> Service, as returned.
    assert 'n4 -> n3' in dot  # AUTHORED is Person -> PullRequest, as returned.
    assert "DEPENDS_ON" not in dot
    assert "MISSING_NODE" not in dot
    assert build_graphviz([]) is None


def test_sources_use_returned_ids_types_and_excerpts():
    sources = source_catalog(response_fixture())
    assert {item["source_id"] for item in sources} == {"inc-1", "pr-1"}
    assert next(item for item in sources if item["source_id"] == "inc-1")["record_type"] == "Incident"
    assert next(item for item in sources if item["source_id"] == "pr-1")["title"] == "Retry change"
    assert all(item["evidence_kind"] == "synthetic_record" for item in sources)


def test_expert_explanation_uses_authored_relationship_from_path():
    experts = expert_reasons(response_fixture())
    assert experts[0]["person"]["properties"]["name"] == "Maya Chen"
    assert experts[0]["reason"] == "AUTHORED to PullRequest Retry change"


def test_missing_paths_do_not_create_placeholder_sources_or_edges():
    assert build_graphviz([]) is None
    assert source_catalog({"supporting_facts": [], "graph_paths": []}) == []
    assert expert_reasons({"relevant_people": [], "graph_paths": []}) == []
