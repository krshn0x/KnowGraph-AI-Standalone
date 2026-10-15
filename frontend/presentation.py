"""Pure transformations for rendering only evidence returned by the API."""
import json


def _escape_dot(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def build_graphviz(paths: list[dict]) -> str | None:
    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str, str, str], dict] = {}
    for path in paths:
        for node in path.get("nodes", []):
            if node.get("id"):
                nodes.setdefault(node["id"], node)
        for edge in path.get("relationships", []):
            start_id, end_id = edge.get("start_id"), edge.get("end_id")
            if start_id in nodes or start_id in {node.get("id") for node in path.get("nodes", [])}:
                if end_id in nodes or end_id in {node.get("id") for node in path.get("nodes", [])}:
                    key = (start_id, end_id, edge.get("type", ""), edge.get("source_id", ""))
                    edges.setdefault(key, edge)
    if not nodes:
        return None

    palette = {
        "Incident": ("#3b1d28", "#fb7185"),
        "Deployment": ("#302514", "#fbbf24"),
        "Service": ("#102b2b", "#2dd4bf"),
        "PullRequest": ("#201a3b", "#a78bfa"),
        "Person": ("#102944", "#60a5fa"),
        "Ticket": ("#29221a", "#f59e0b"),
        "Commit": ("#1c2934", "#7dd3fc"),
        "Document": ("#263123", "#a3e635"),
    }
    lines = [
        "digraph Evidence {",
        'graph [bgcolor="transparent", rankdir=LR, pad="0.25", nodesep="0.5", ranksep="0.8"];',
        'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, margin="0.16,0.10", color="#334155", fontcolor="#e2e8f0"];',
        'edge [fontname="Helvetica", fontsize=9, color="#64748b", fontcolor="#cbd5e1", arrowsize=0.7];',
    ]
    dot_id = {node_id: f"n{index}" for index, node_id in enumerate(nodes)}
    for node_id, node in nodes.items():
        label_name = node.get("properties", {}).get("name") or node.get("properties", {}).get("title") or node_id
        label, outline = palette.get(node.get("label"), ("#1e293b", "#94a3b8"))
        caption = f"{node.get('label', 'Record')}\n{label_name}\n{node_id}"
        lines.append(
            f"{dot_id[node_id]} [label={_escape_dot(caption)}, fillcolor={_escape_dot(label)}, "
            f"color={_escape_dot(outline)}, penwidth=1.4];"
        )
    for (start_id, end_id, relation, _source_id), edge in edges.items():
        # Preserve the direction and type exactly as returned by the graph API.
        excerpt = edge.get("evidence_excerpt", "")
        tooltip = f"{relation}: {excerpt}" if excerpt else relation
        lines.append(
            f"{dot_id[start_id]} -> {dot_id[end_id]} [label={_escape_dot(relation)}, "
            f"tooltip={_escape_dot(tooltip)}];"
        )
    lines.append("}")
    return "\n".join(lines)


def source_catalog(response: dict) -> list[dict]:
    nodes = {
        node.get("id"): node
        for path in response.get("graph_paths", [])
        for node in path.get("nodes", [])
        if node.get("id")
    }
    evidence_metadata = {}
    for path in response.get("graph_paths", []):
        for edge in path.get("relationships", []):
            source_id = edge.get("source_id")
            if source_id:
                evidence_metadata.setdefault(source_id, edge)
    catalog = {}
    for fact in response.get("supporting_facts", []):
        source_id = fact.get("source_id")
        if not source_id:
            continue
        node = nodes.get(source_id, {})
        properties = node.get("properties", {})
        edge = evidence_metadata.get(source_id, {})
        catalog.setdefault(source_id, {
            "source_id": source_id,
            "record_type": node.get("label", "Graph record"),
            "title": properties.get("title") or properties.get("name") or properties.get("key") or source_id,
            "evidence_kind": edge.get("evidence_kind", "recorded evidence"),
            "excerpts": [],
        })
        excerpt = fact.get("evidence_excerpt")
        if excerpt and excerpt not in catalog[source_id]["excerpts"]:
            catalog[source_id]["excerpts"].append(excerpt)
    return list(catalog.values())


def expert_reasons(response: dict) -> list[dict]:
    paths = response.get("graph_paths", [])
    experts = []
    for person in response.get("relevant_people", []):
        person_id = person.get("id")
        properties = person.get("properties", {})
        reasons = []
        for path in paths:
            path_nodes = {node.get("id"): node for node in path.get("nodes", [])}
            if person_id not in path_nodes:
                continue
            for edge in path.get("relationships", []):
                if edge.get("start_id") == person_id or edge.get("end_id") == person_id:
                    other_id = edge.get("end_id") if edge.get("start_id") == person_id else edge.get("start_id")
                    other = path_nodes.get(other_id, {})
                    other_name = other.get("properties", {}).get("title") or other.get("properties", {}).get("name") or other_id
                    reasons.append(f"{edge.get('type', 'Linked')} to {other.get('label', 'record')} {other_name}")
        experts.append({
            "person": person,
            "reason": "; ".join(dict.fromkeys(reasons)) or "The API marked this person relevant but returned no explanatory relationship.",
        })
    return experts
