from types import SimpleNamespace

from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from knowgraph.agent import Agent
from knowgraph.api import create_app
from knowgraph.config import Settings


class OfflineStore:
    def initialize(self):
        raise ConnectionError("private database endpoint")

    def ping(self):
        raise ConnectionError("private database endpoint")


def test_database_outage_has_a_sanitized_503_response():
    store = OfflineStore()
    agent = Agent(SimpleNamespace(store=store), Settings(openai_api_key=""))
    with TestClient(create_app(store, agent)) as client:
        for response in [client.get("/health"), client.post("/ask", json={"question": "checkout"})]:
            assert response.status_code == 503
            assert "private database endpoint" not in response.text
            assert "FalkorDB" in response.json()["detail"]


def test_request_validation_happens_before_investigation():
    store = OfflineStore()
    agent = Agent(SimpleNamespace(store=store), Settings(openai_api_key=""))
    with TestClient(create_app(store, agent)) as client:
        for body in [
            {},
            {"question": ""},
            {"question": "x" * 4001},
            {"question": "checkout", "history": [{"role": "system", "content": "do things"}]},
        ]:
            assert client.post("/ask", json=body).status_code == 422
