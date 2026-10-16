from unittest.mock import patch

import httpx
from conftest import ROOT
from streamlit.testing.v1 import AppTest

from frontend.render import graph_html
from knowgraph.models import Entity

SERVICE = Entity(
    id="demo:checkout", kind="Service", title="Checkout", source_ref="fixture://checkout"
).model_dump(mode="json")
EVIDENCE = {"nodes": [SERVICE], "edges": [], "paths": [], "truncated": False}


def response(method, url, **kwargs):
    request = httpx.Request(method, url)
    if url.endswith("/health"):
        payload = {"nodes": 113, "edges": 209, "ai_configured": False, "model": "gpt-6.1-sol"}
    elif "/entities?" in url:
        payload = []
    elif url.endswith("/ask"):
        payload = {
            "summary": "AI answer unavailable. Review the retrieved records below.",
            "claims": [],
            "sources": [SERVICE],
            "evidence": EVIDENCE,
            "experts": [],
            "warnings": ["Set OPENAI_API_KEY to enable AI answers."],
            "tool_calls": [],
            "status": "provider_error",
            "insufficient_evidence": True,
        }
    elif url.endswith("/experts"):
        payload = {"experts": [], "evidence": EVIDENCE}
    elif url.endswith("/documents"):
        payload = {
            "documents": [SERVICE | {"kind": "Document", "body": "Inspect retry budget."}],
            "evidence": EVIDENCE,
        }
    else:
        raise AssertionError(url)
    return httpx.Response(200, json=payload, request=request)


def test_all_feature_tabs_render_without_records_or_credentials():
    with patch("httpx.get", side_effect=lambda url, **kw: response("GET", url, **kw)):
        app = AppTest.from_file(str(ROOT / "frontend/app.py")).run(timeout=15)
        assert not app.exception
        assert [t.label for t in app.tabs] == [
            "Ask KnowGraph",
            "Incidents",
            "Experts",
            "Documents",
            "Evidence Graph",
            "Knowledge Update",
        ]


def test_question_and_expert_search_render_their_api_results():
    with (
        patch("httpx.get", side_effect=lambda url, **kw: response("GET", url, **kw)),
        patch("httpx.request", side_effect=response),
    ):
        app = AppTest.from_file(str(ROOT / "frontend/app.py")).run(timeout=15)
        app.chat_input[0].set_value("What changed in checkout?").run(timeout=15)
        assert not app.exception
        assert len(app.chat_message) == 2
        assert any("AI answer unavailable" in item.value for item in app.markdown)
        next(b for b in app.button if b.label == "Find experts").click().run(timeout=15)
        assert not app.exception
        assert any("No supported expert matches" in item.value for item in app.info)


def test_outage_does_not_crash_the_dashboard():
    with patch("httpx.get", side_effect=httpx.ConnectError("offline")):
        import streamlit as st

        st.cache_data.clear()
        app = AppTest.from_file(str(ROOT / "frontend/app.py")).run(timeout=15)
        assert not app.exception
        assert any("unavailable" in item.value for item in app.warning)
        st.cache_data.clear()


def test_graph_is_self_contained_and_escapes_source_titles():
    evidence = {
        "nodes": [SERVICE | {"title": '<img src=x onerror="alert(1)">'}],
        "edges": [],
        "paths": [],
    }
    rendered = graph_html(evidence)
    assert "<img src=x" not in rendered
    assert 'src="https://' not in rendered and 'href="https://' not in rendered
    assert "new vis.DataSet" in rendered
