from knowgraph.graph import select_evidence
from knowgraph.models import Entity, Evidence, EvidencePath, GraphEdge


def test_claim_graph_excludes_uncited_retrieved_context():
    nodes = [Entity(id=f"demo:{i}", kind="Service", title=str(i)) for i in range(3)]
    edge = GraphEdge(id="edge:1", source="demo:0", kind="DEPENDS_ON", target="demo:1")
    path = EvidencePath(id="path:1", node_ids=["demo:0", "demo:1"], edge_ids=[edge.id])
    evidence = Evidence(nodes=nodes, edges=[edge], paths=[path])
    cited = select_evidence(evidence, {path.id})
    assert [n.id for n in cited.nodes] == ["demo:0", "demo:1"]
    assert cited.paths == [path] and cited.edges == [edge]
    assert select_evidence(evidence, {"demo:2"}).nodes == [nodes[2]]
    assert not select_evidence(evidence, {"demo:2"}).edges
    assert not select_evidence(evidence, set()).nodes
