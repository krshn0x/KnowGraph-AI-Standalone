import os
from pathlib import Path
from uuid import uuid4

import pytest

from knowgraph.config import Settings
from knowgraph.graph import GraphStore
from knowgraph.ingestion import ingest, parse_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store():
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("Set RUN_INTEGRATION=1 and start FalkorDB to run database tests")
    settings = Settings(falkordb_graph="knowgraph_test_" + uuid4().hex)
    database = GraphStore(settings)
    database.initialize()
    result = ingest(database, parse_json((ROOT / "data/demo.json").read_bytes()))
    assert result.created == 322
    yield database
    database.graph.delete()
    database.close()
