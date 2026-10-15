import streamlit as st

from frontend.api_client import APIError, api_base_url, ask, get_health
from frontend.presentation import build_graphviz, expert_reasons, source_catalog


EXAMPLES = [
    "Why did checkout start failing after the latest deployment?",
    "What changed in checkout around incident inc-2026-104?",
    "Who authored the pull request linked to the checkout incident?",
]

st.set_page_config(page_title="KnowGraph AI", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
      .stApp { background: radial-gradient(ellipse at 15% 0%, #10202c 0, #0b1118 48rem); }
      [data-testid="stHeader"] { background: rgba(0,0,0,0); }
      .kg-eyebrow { color:#65d8c7; text-transform:uppercase; letter-spacing:.16em; font-size:.72rem; font-weight:700; }
      .kg-title { font-size:2.35rem; font-weight:750; letter-spacing:-.045em; margin:.1rem 0 .35rem; }
      .kg-subtitle { color:#9eacbb; font-size:1rem; margin-bottom:1.3rem; }
      .kg-card { background:rgba(18,29,39,.88); border:1px solid #263746; border-radius:14px; padding:1rem 1.15rem; }
      .kg-muted { color:#9eacbb; }
      .kg-source { color:#65d8c7; font-family:monospace; }
      div[data-testid="stMetric"] { background:#101b25; border:1px solid #263746; border-radius:12px; padding:.8rem 1rem; }
      div[data-testid="stTabs"] button { font-weight:600; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "investigation" not in st.session_state:
    st.session_state.investigation = None
if "question_input" not in st.session_state:
    st.session_state.question_input = ""


@st.cache_data(ttl=5, show_spinner=False)
def cached_health():
    return get_health()


health_payload = None
health_error = None
try:
    health_payload = cached_health()
except APIError as exc:
    health_error = str(exc)

with st.sidebar:
    st.markdown("<div class='kg-eyebrow'>Local engineering intelligence</div>", unsafe_allow_html=True)
    st.markdown("## ◈ KnowGraph AI")
    st.caption("Evidence first. Root causes only when proven.")
    st.divider()
    st.markdown("### System status")
    if health_payload:
        st.write("🟢 API connected")
        st.write("🟢 FalkorDB ready" if health_payload.get("graph_available") else "🔴 FalkorDB unavailable")
        st.write("🟢 Ollama ready" if health_payload.get("ollama_available") else "🔴 Ollama unavailable")
        st.caption(f"Model: `{health_payload.get('model', 'not reported')}`")
    else:
        st.error("Backend API unavailable")
        st.caption(health_error)
    st.caption(f"API: `{api_base_url() if not health_error else 'local service'}`")
    st.divider()
    st.caption("Runs locally with FalkorDB + Ollama. No hosted LLM or API key.")

st.markdown("<div class='kg-eyebrow'>AcmePay · evidence-driven investigation</div>", unsafe_allow_html=True)
st.markdown("<div class='kg-title'>Understand what changed.</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='kg-subtitle'>Ask an engineering question. Follow every answer back to the graph records that support it.</div>",
    unsafe_allow_html=True,
)
st.warning(
    "SYNTHETIC DEMO DATA · AcmePay is fictional. Incidents, people, changes, dates, excerpts, and relationships are illustrative—not production records.",
    icon="⚠️",
)

example_columns = st.columns(len(EXAMPLES))
for index, (column, prompt) in enumerate(zip(example_columns, EXAMPLES)):
    with column:
        if st.button(prompt, key=f"example_{index}", width="stretch"):
            st.session_state.question_input = prompt

with st.form("investigation_form", clear_on_submit=False):
    question = st.text_area(
        "Investigation question",
        key="question_input",
        placeholder="e.g. Why did checkout start failing after the latest deployment?",
        height=92,
        max_chars=2000,
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Investigate  →", type="primary", width="stretch")

if submitted:
    if len(question.strip()) < 3:
        st.warning("Enter a question with at least 3 characters.")
    else:
        try:
            with st.spinner("Tracing incidents, deployments, code changes, and source records…"):
                st.session_state.investigation = ask(question.strip())
                st.session_state.investigation_question = question.strip()
        except APIError as exc:
            st.error(f"The investigation could not be completed: {exc}")
            st.info("Check that FalkorDB and Ollama are running, then start the FastAPI service on port 8000.")

investigation = st.session_state.investigation
tabs = st.tabs(["Investigate", "Evidence Graph", "Sources", "Experts", "System Status"])

with tabs[0]:
    if not investigation:
        st.markdown(
            "<div class='kg-card'><b>Ready when you are.</b><br><span class='kg-muted'>Choose an example above or enter a question to trace the graph evidence.</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"Question · {st.session_state.get('investigation_question', '')}")
        st.markdown("### Investigation")
        with st.container(border=True):
            st.write(investigation.get("answer", ""))

        if investigation.get("relevant_people"):
            st.markdown("#### People connected to this investigation")
            people_columns = st.columns(min(3, len(investigation["relevant_people"])))
            for index, person in enumerate(investigation["relevant_people"]):
                props = person.get("properties", {})
                with people_columns[index % len(people_columns)]:
                    st.markdown(f"**{props.get('name', person.get('id'))}**")
                    st.caption(f"{props.get('role', person.get('label', 'Person'))} · `{person.get('id')}`")

        st.markdown("#### Graph-supported facts · root cause not established")
        facts = investigation.get("supporting_facts", [])
        if facts:
            for fact in facts:
                with st.container(border=True):
                    st.markdown(f"**{fact.get('statement', 'Evidence fact')}**")
                    st.caption(
                        f"Evidence `{fact.get('id', 'not provided')}` · "
                        f"Source `{fact.get('source_id', 'not provided')}` · "
                        f"Path `{fact.get('path_id', 'not provided')}`"
                    )
                    st.write(fact.get("evidence_excerpt", "No excerpt returned."))
        else:
            st.info("The backend returned no supporting facts for this question.")

        for hypothesis in investigation.get("hypotheses", []):
            st.warning(f"Hypothesis — not established: {hypothesis.get('text', '')}\n\nEvidence IDs: {', '.join(hypothesis.get('evidence_ids', []))}")
        if investigation.get("limitations"):
            st.markdown("#### Limitations")
            for limitation in investigation["limitations"]:
                st.info(limitation)

with tabs[1]:
    st.markdown("### Evidence Graph")
    if not investigation:
        st.info("Run an investigation to see graph records returned by the API.")
    else:
        paths = investigation.get("graph_paths", [])
        dot = build_graphviz(paths)
        if dot:
            st.caption("Synthetic AcmePay records. Arrows and edge labels are the actual relationships returned by FalkorDB; no missing edges are inferred.")
            st.graphviz_chart(dot, width="stretch")
            st.markdown("#### Returned evidence paths")
            for path in paths:
                with st.container(border=True):
                    st.markdown(f"**{path.get('id', 'Graph path')}**")
                    nodes = " · ".join(f"{node.get('label')} `{node.get('id')}`" for node in path.get("nodes", []))
                    st.caption(f"Nodes in path traversal order: {nodes or 'No nodes returned'}")
                    for edge in path.get("relationships", []):
                        st.write(
                            f"`{edge.get('start_id')}` —**{edge.get('type')}**→ `{edge.get('end_id')}`"
                        )
                        st.caption(
                            f"Source `{edge.get('source_id')}` · "
                            f"{edge.get('evidence_excerpt') or 'No excerpt returned.'}"
                        )
        else:
            st.info("No graph paths were returned. The UI does not infer or fill missing relationships.")

with tabs[2]:
    st.markdown("### Sources")
    if not investigation:
        st.info("Sources appear here after an investigation.")
    else:
        sources = source_catalog(investigation)
        if any(source.get("evidence_kind") == "synthetic_record" for source in sources):
            st.warning("Synthetic AcmePay demo data — these records are illustrative, not production evidence.")
        if not sources:
            st.info("The backend returned no cited source records.")
        for source in sources:
            with st.expander(f"{source['record_type']} · {source['title']} · {source['source_id']}"):
                st.markdown(f"**Source ID**  `{source['source_id']}`")
                st.markdown(f"**Record type**  {source['record_type']}")
                st.markdown(f"**Evidence kind**  `{source['evidence_kind']}`")
                for excerpt in source["excerpts"]:
                    st.write(excerpt)

with tabs[3]:
    st.markdown("### Experts")
    if not investigation:
        st.info("Relevant people appear here after an investigation.")
    else:
        experts = expert_reasons(investigation)
        if not experts:
            st.info("No relevant people were returned by the backend.")
        for expert in experts:
            person = expert["person"]
            props = person.get("properties", {})
            with st.container(border=True):
                st.markdown(f"**{props.get('name', person.get('id'))}**  ·  {props.get('role', 'Person')}")
                st.caption(f"Relevance from returned graph path: {expert['reason']}")
                st.caption(f"Record ID: `{person.get('id')}`")

with tabs[4]:
    st.markdown("### System Status")
    if st.button("Refresh status", key="refresh_health"):
        cached_health.clear()
        st.rerun()
    if health_payload:
        cols = st.columns(3)
        cols[0].metric("Backend API", "Reachable")
        cols[1].metric("FalkorDB", "Ready" if health_payload.get("graph_available") else "Unavailable")
        cols[2].metric("Local Ollama", "Ready" if health_payload.get("ollama_available") else "Unavailable")
        st.write(f"API status: `{health_payload.get('status', 'unknown')}`")
        st.write(f"Configured model: `{health_payload.get('model', 'not reported')}`")
        if not health_payload.get("graph_available"):
            st.error("FalkorDB is not reachable. Start Docker Compose and check the backend logs.")
        if not health_payload.get("ollama_available"):
            st.error("Ollama or the configured model is unavailable. Start Ollama and check `ollama list`.")
    else:
        st.error("The FastAPI backend did not respond.")
        st.code("uvicorn knowgraph.api:app --reload")
        st.caption(health_error or "Check that the backend is running on http://localhost:8000.")
