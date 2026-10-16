import html
import re
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

COLORS = {
    "Incident": "#ff7a90",
    "Service": "#7daaff",
    "Deployment": "#ffc66d",
    "Commit": "#ad9aff",
    "PullRequest": "#c4acff",
    "Person": "#70dfbd",
    "Document": "#87d5ee",
    "Ticket": "#e2bd86",
}


def graph_html(evidence: dict, selected_path: str | None = None) -> str:
    net = Network(
        height="500px",
        width="100%",
        bgcolor="#111827",
        font_color="#e5e7eb",
        directed=True,
        cdn_resources="in_line",
    )
    selected = next((p for p in evidence.get("paths", []) if p["id"] == selected_path), None)
    highlight_nodes = set(selected["node_ids"]) if selected else set()
    highlight_edges = set(selected["edge_ids"]) if selected else set()
    ids = {n["id"] for n in evidence["nodes"]}
    for n in evidence["nodes"]:
        title = html.escape(n["title"])
        net.add_node(
            n["id"],
            label=title[:45],
            title=f"<b>{title}</b><br>{html.escape(n['kind'])}<br>{html.escape(n['id'])}",
            color=COLORS.get(n["kind"], "#aaa"),
            shape="dot",
            size=23 if n["id"] in highlight_nodes else 15,
            borderWidth=3 if n["id"] in highlight_nodes else 1,
        )
    for e in evidence.get("edges", []):
        if e["source"] in ids and e["target"] in ids:
            net.add_edge(
                e["source"],
                e["target"],
                label=e["kind"],
                id=e["id"],
                color="#ffffff" if e["id"] in highlight_edges else "#54647d",
                width=4 if e["id"] in highlight_edges else 1,
                title=html.escape(e["source_ref"] or e["id"]),
            )
    net.set_options("""{"layout":{"randomSeed":7},"physics":{"solver":"forceAtlas2Based",
        "stabilization":{"iterations":120}},"edges":{"font":{"size":10,"align":"middle"},
        "smooth":{"type":"dynamic"}},"interaction":{"hover":true,"navigationButtons":true},
        "nodes":{"font":{"size":12}}}""")
    rendered = net.generate_html(notebook=False)
    # PyVis embeds vis-network for in_line mode but its base template still adds
    # Bootstrap CDN tags. This graph uses no Bootstrap controls, so remove them.
    rendered = re.sub(r'<link\b[^>]*href="https?://[^\"]*"[^>]*>', "", rendered, flags=re.S)
    return re.sub(
        r'<script\b[^>]*src="https?://[^\"]*"[^>]*>\s*</script>', "", rendered, flags=re.S
    )


def source_card(node: dict):
    st.caption(f"{node['kind']} · {node['id']}")
    st.write(node.get("body") or "No source body recorded.")
    if node.get("occurred_at"):
        st.caption(f"Recorded time: {node['occurred_at']}")
    ref = node.get("source_ref", "")
    if urlparse(ref).scheme in {"http", "https"}:
        st.link_button("Open source", ref)
    elif ref:
        st.code(ref, language=None)


def evidence_view(evidence: dict, key: str):
    if not evidence.get("nodes"):
        st.info("No graph evidence found.")
        return
    if evidence.get("truncated"):
        st.warning("Results are bounded. Narrow your selection to inspect more evidence.")
    lookup = {n["id"]: n for n in evidence["nodes"]}
    paths = {p["id"]: p for p in evidence.get("paths", [])}
    selected = st.selectbox(
        "Highlight a retrieved path",
        [None, *paths],
        format_func=lambda p: (
            "All retrieved evidence"
            if p is None
            else " — ".join(lookup[i]["title"] for i in paths[p]["node_ids"])
        ),
        key=f"{key}-path",
    )
    components.html(graph_html(evidence, selected), height=520, scrolling=False)
    st.caption("Drag to explore · hover for IDs · arrows show stored relationship direction.")
    selected_node = st.selectbox(
        "Inspect a source record",
        list(lookup),
        format_func=lambda i: f"{lookup[i]['kind']} · {lookup[i]['title']}",
        key=f"{key}-node",
    )
    source_card(lookup[selected_node])
    with st.expander("Relationship evidence"):
        st.dataframe(
            [
                {k: e[k] for k in ("source", "kind", "target", "id")}
                for e in evidence.get("edges", [])
            ],
            width="stretch",
            hide_index=True,
        )


def expert_cards(experts: list[dict]):
    if not experts:
        st.info("No supported expert matches were found.")
    for person in experts:
        with st.container(border=True):
            left, right = st.columns([5, 1])
            left.subheader(person["person"]["title"])
            right.metric("Score", person["score"])
            for reason in person["reasons"]:
                st.write(f"• {reason}")
            st.caption(person["person"]["id"])


def answer_view(answer: dict, key: str):
    st.write(answer["summary"])
    for warning in answer.get("warnings", []):
        st.warning(warning)
    for claim in answer.get("claims", []):
        label = "Hypothesis" if claim["certainty"] == "hypothesis" else "Finding"
        st.markdown(f"**{label}** · {claim['text']}")
        st.caption("Evidence: " + ", ".join(claim["evidence_ids"]))
    if answer.get("experts"):
        with st.expander("Relevant experts"):
            expert_cards(answer["experts"])
    with st.expander(f"Sources ({len(answer.get('sources', []))})"):
        for node in answer.get("sources", []):
            st.markdown(f"**{node['title']}**")
            source_card(node)
            st.divider()
    if answer.get("evidence", {}).get("nodes"):
        with st.expander(
            "Evidence used for this answer"
            if answer.get("status") == "ok"
            else "Retrieved evidence"
        ):
            evidence_view(answer["evidence"], key)
    if answer.get("retrieved_evidence", {}).get("nodes"):
        with st.expander("Additional retrieved context"):
            st.caption(
                "These records were retrieved during investigation; they may not be cited in the answer."
            )
            evidence_view(answer["retrieved_evidence"], f"{key}-retrieved")
    st.caption(
        "Tools: " + (" → ".join(answer.get("tool_calls", [])) or "deterministic retrieval only")
    )
