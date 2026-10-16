import os
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frontend.render import answer_view, evidence_view, expert_cards, source_card  # noqa: E402

st.set_page_config(page_title="KnowGraph AI", page_icon="◈", layout="wide")
BASE = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")

st.markdown(
    """<style>
.stApp {background: #0b1020;}
[data-testid="stSidebar"] {background: #111a2e;}
h1,h2,h3 {letter-spacing: -.035em;}
[data-testid="stMetricValue"] {color: #a5c4ff;}
.block-container {padding-top: 2rem; max-width: 1500px;}
.hero-tag {color: #91b8ff; font-size: .8rem; letter-spacing: .16em; margin-bottom: .4rem;}
.hero-desc {color: #a9b5ce; font-size: 1.08rem; max-width: 850px; margin-bottom: 1.8rem;}
</style>""",
    unsafe_allow_html=True,
)


def api(path, method="GET", **kwargs):
    try:
        response = httpx.request(method, BASE + path, timeout=75, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
        except ValueError:
            detail = {"detail": "Unexpected server response"}
        st.error(detail.get("detail") or "; ".join(detail.get("errors", [])) or "Request failed")
    except httpx.RequestError:
        st.error("Cannot reach the API. Start the backend and check API_BASE_URL.")
    return None


@st.cache_data(ttl=15, show_spinner=False)
def cached_get(path):
    # Exceptions propagate rather than caching an outage as a successful empty result.
    response = httpx.get(BASE + path, timeout=8)
    response.raise_for_status()
    return response.json()


with st.sidebar:
    st.markdown("## ◈ KnowGraph")
    st.caption("THE ENGINEERING COMPANY BRAIN")
    st.divider()
    try:
        health = cached_get("/health")
        st.success("FalkorDB connected")
        a, b = st.columns(2)
        a.metric("Records", health["nodes"])
        b.metric("Links", health["edges"])
        if health["ai_configured"]:
            st.caption(f"AI · {health['model']}")
        else:
            st.info(
                "Graph tools are ready. Add OPENAI_API_KEY and restart the API to enable AI chat."
            )
    except httpx.HTTPError:
        st.warning("API or database unavailable")
    st.divider()
    st.markdown("**Demo workspace**")
    st.caption("Northstar Labs · fictional company data")
    st.caption("Every answer starts with connected evidence.")
    if st.button("Refresh workspace", width="stretch"):
        st.cache_data.clear()
        st.rerun()

st.markdown(
    '<div class="hero-tag">CONNECTED KNOWLEDGE. TRACEABLE ANSWERS.</div>', unsafe_allow_html=True
)
st.title("Find the story behind the incident.")
st.markdown(
    '<div class="hero-desc">Connect releases, services, people, and past decisions. '
    "Investigate what changed and see the evidence behind every answer.</div>",
    unsafe_allow_html=True,
)

chat, incidents, experts, documents, graph, updater = st.tabs(
    ["Ask KnowGraph", "Incidents", "Experts", "Documents", "Evidence Graph", "Knowledge Update"]
)

try:
    incident_records = cached_get("/entities?kind=Incident")
    services = cached_get("/entities?kind=Service")
except httpx.HTTPError:
    incident_records, services = [], []

with chat:
    st.subheader("Ask a question across your company knowledge")
    examples = [
        "What changed before the checkout incident? Who should investigate and which runbook helps?",
        "Investigate payment authorization timeouts and changes in its dependencies.",
        "Why is queue lag recurring, and who has resolved similar incidents?",
    ]
    st.session_state.setdefault("messages", [])
    cols = st.columns(3)
    question = None
    for index, (col, example) in enumerate(zip(cols, examples)):
        if col.button(
            ["Investigate checkout", "Trace payment dependencies", "Explain recurring queue lag"][
                index
            ],
            width="stretch",
        ):
            question = example
    for index, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if message.get("answer"):
                answer_view(message["answer"], f"answer-{index}")
            else:
                st.write(message["content"])
    typed = st.chat_input("Ask about a failure, expert, service, or runbook…")
    question = typed or question
    if question:
        history = [
            {"role": m["role"], "content": m["content"][:4000]}
            for m in st.session_state.messages[-12:]
        ]
        with st.spinner("Following the evidence…"):
            result = api("/ask", "POST", json={"question": question, "history": history})
        if result:
            st.session_state.messages.extend(
                [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": result["summary"], "answer": result},
                ]
            )
            st.session_state.latest_evidence = result["evidence"]
            st.rerun()

with incidents:
    st.subheader("Follow the incident timeline")
    by_incident = {n["id"]: n for n in incident_records}
    with st.form("incident-form"):
        incident_id = st.selectbox(
            "Incident", list(by_incident), format_func=lambda i: by_incident[i]["title"]
        )
        lookback = st.slider("Deployment lookback (hours)", 1, 168, 24)
        investigate = st.form_submit_button("Investigate incident", type="primary")
    if investigate and incident_id:
        result = api(
            f"/incidents/{quote(incident_id, safe='')}/investigation",
            params={"lookback_hours": lookback},
        )
        if result:
            st.session_state.investigation = result
            st.session_state.latest_evidence = result["evidence"]
    if result := st.session_state.get("investigation"):
        st.markdown(f"### {result['incident']['title']}")
        st.write(result["incident"]["body"])
        cols = st.columns(3)
        for col, label, value in zip(
            cols,
            ["Services", "Deployments", "Changes"],
            [len(result[k]) for k in ["services", "deployments", "changes"]],
        ):
            col.metric(label, value)
        for warning in result["warnings"]:
            st.warning(warning)
        st.dataframe(
            [
                {k: n.get(k) for k in ["occurred_at", "kind", "title", "id"]}
                for n in result["timeline"]
            ],
            width="stretch",
            hide_index=True,
        )
        evidence_view(result["evidence"], "incident")
    elif not incident_records:
        st.info("Seed the demo data or upload your first incident records.")

with experts:
    st.subheader("Find people with relevant experience")
    st.caption(
        "3 points per resolved incident · 2 per authored change · 1 per authored document. "
        "Distinct records only; recent activity breaks ties."
    )
    with st.form("expert-form"):
        expert_q = st.text_input("Service, incident ID, or topic", value="demo:checkout")
        if st.form_submit_button("Find experts", type="primary") and expert_q:
            result = api("/experts", params={"q": expert_q})
            if result:
                st.session_state.experts_result = result
                st.session_state.latest_evidence = result["evidence"]
    if result := st.session_state.get("experts_result"):
        expert_cards(result["experts"])
        with st.expander("Supporting graph paths"):
            evidence_view(result["evidence"], "experts")

with documents:
    st.subheader("Find the runbook, ticket, or decision")
    with st.form("document-form"):
        document_q = st.text_input("Search text or service/incident ID", value="checkout retry")
        if st.form_submit_button("Search knowledge", type="primary") and document_q:
            result = api("/documents", params={"q": document_q})
            if result:
                st.session_state.documents_result = result
                st.session_state.latest_evidence = result["evidence"]
    if result := st.session_state.get("documents_result"):
        if not result["documents"]:
            st.info("No matching documents or tickets.")
        for document in result["documents"]:
            with st.expander(f"{document['kind']} · {document['title']}"):
                source_card(document)

with graph:
    st.subheader("Inspect the relationships behind the answer")
    mode = st.radio(
        "Evidence selection", ["Latest retrieved evidence", "Explore neighborhood"], horizontal=True
    )
    if mode == "Latest retrieved evidence":
        st.caption("These records and paths came from the latest successful query or answer.")
        evidence_view(st.session_state.get("latest_evidence", {}), "latest")
    else:
        st.caption("Additional exploration can include records that were not used in an answer.")
        with st.form("neighborhood-form"):
            root = st.text_input("Starting entity ID", "demo:inc-checkout")
            hops = st.slider("Hops", 1, 3, 2)
            if st.form_submit_button("Explore graph", type="primary"):
                result = api("/graph/neighborhood", params={"node_id": root, "hops": hops})
                if result:
                    st.session_state.neighborhood = result
        if result := st.session_state.get("neighborhood"):
            evidence_view(result, "neighborhood")

with updater:
    st.subheader("Keep the company brain current")
    st.write("Upload a JSON bundle or node/edge CSV files. Stable IDs update existing records.")
    st.caption(
        "Try data/resolution_update.json after investigating checkout, then investigate again."
    )
    format = st.radio("Upload format", ["JSON bundle", "CSV files"], horizontal=True)
    with st.form("upload-form", clear_on_submit=True):
        if format == "JSON bundle":
            bundle = st.file_uploader("JSON bundle", type=["json"])
            nodes_file = edges_file = None
        else:
            bundle = None
            nodes_file = st.file_uploader("Nodes CSV", type=["csv"])
            edges_file = st.file_uploader("Edges CSV", type=["csv"])
        submitted = st.form_submit_button("Validate and import", type="primary")
    if submitted:
        files = {
            name: (f.name, f.getvalue())
            for name, f in [
                ("bundle_file", bundle),
                ("nodes_file", nodes_file),
                ("edges_file", edges_file),
            ]
            if f
        }
        if not files:
            st.warning("Select at least one file.")
        else:
            result = api("/ingest", "POST", files=files)
            if result:
                st.session_state.import_result = result
                st.cache_data.clear()
                # Old answer snapshots remain explicitly tied to their previous retrieval.
                for name in [
                    "investigation",
                    "experts_result",
                    "documents_result",
                    "latest_evidence",
                    "neighborhood",
                ]:
                    st.session_state.pop(name, None)
                st.rerun()
    if result := st.session_state.get("import_result"):
        st.success("Import completed. Run your query again to retrieve the updated evidence.")
        cols = st.columns(4)
        for col, name in zip(cols, ["created", "updated", "unchanged", "rejected"]):
            col.metric(name.title(), result[name])
