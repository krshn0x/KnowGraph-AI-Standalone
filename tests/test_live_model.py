import os

import pytest

from knowgraph.agent import Agent
from knowgraph.config import Settings
from knowgraph.models import AskRequest
from knowgraph.retrieval import Retrieval

pytestmark = pytest.mark.live


def test_live_model_investigates_with_retrieved_citations(store):
    if os.environ.get("RUN_LIVE_MODEL") != "1":
        pytest.skip(
            "Set RUN_LIVE_MODEL=1, RUN_INTEGRATION=1 and provider credentials; incurs usage"
        )
    settings = Settings()
    if settings.configuration_message:
        pytest.fail(settings.configuration_message)
    answer = Agent(Retrieval(store), settings).ask(
        AskRequest(
            question="Investigate demo:inc-checkout. Find the relevant deployment, expert and runbook."
        )
    )
    assert answer.status == "ok"
    assert "investigate_incident" in answer.tool_calls
    assert answer.claims and answer.sources
    ids = (
        {n.id for n in answer.evidence.nodes}
        | {e.id for e in answer.evidence.edges}
        | {p.id for p in answer.evidence.paths}
    )
    assert all(c.evidence_ids and set(c.evidence_ids) <= ids for c in answer.claims)
