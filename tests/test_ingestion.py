from contextlib import contextmanager
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from knowgraph.ingestion import ingest, parse_csv, parse_json
from knowgraph.models import Bundle, EdgeInput, NodeInput

ROOT = Path(__file__).resolve().parents[1]


class MemoryStore:
    """A write recorder for validation tests; retrieval tests use real FalkorDB."""

    lock_name = "test"

    def __init__(self):
        self.nodes, self.edges = {}, {}
        self.redis = SimpleNamespace(lock=self.lock)

    @contextmanager
    def lock(self, *args, **kwargs):
        yield SimpleNamespace(extend=lambda *args, **kwargs: None)

    def existing(self, ids):
        return {i: self.nodes[i] for i in ids if i in self.nodes}

    def upsert_node(self, node):
        properties = node.model_dump(mode="json", exclude_unset=True)
        if node.occurred_at:
            properties["occurred_at"] = node.occurred_at.astimezone(timezone.utc).isoformat()
        self.nodes.setdefault(node.id, {}).update(properties)

    def edge_properties(self, edge):
        return self.edges.get(edge.key)

    def upsert_edge(self, edge):
        self.edges.setdefault(edge.key, {"source_ref": ""}).update(
            edge.model_dump(exclude_unset=True) | {"id": edge.key}
        )


def test_fixture_csv_json_parity():
    bundle = parse_json((ROOT / "data/demo.json").read_bytes())
    csv_bundle = parse_csv(
        (ROOT / "data/nodes.csv").read_bytes(), (ROOT / "data/edges.csv").read_bytes()
    )
    assert bundle == csv_bundle
    assert len(bundle.nodes) == 113


def test_duplicate_retry_and_partial_update():
    store = MemoryStore()
    bundle = parse_json((ROOT / "data/demo.json").read_bytes())
    assert ingest(store, bundle).created == 322
    assert ingest(store, bundle).unchanged == 322
    update = Bundle(nodes=[NodeInput(id="demo:inc-checkout", kind="Incident", status="resolved")])
    assert ingest(store, update).updated == 1
    assert store.nodes["demo:inc-checkout"]["title"] == "Checkout errors after morning release"


def test_validation_is_all_or_nothing_before_writes():
    store = MemoryStore()
    bundle = Bundle(
        nodes=[NodeInput(id="demo:new", kind="Service", title="new", source_ref="fixture://new")],
        edges=[EdgeInput(source="demo:new", kind="DEPENDS_ON", target="demo:missing")],
    )
    result = ingest(store, bundle)
    assert result.rejected == 2
    assert not store.nodes and not store.edges


def test_invalid_relationship_and_kind_change():
    store = MemoryStore()
    ingest(store, parse_json((ROOT / "data/demo.json").read_bytes()))
    result = ingest(
        store,
        Bundle(edges=[EdgeInput(source="demo:checkout", kind="AUTHORED", target="demo:nina")]),
    )
    assert result.rejected == 1
    result = ingest(store, Bundle(nodes=[NodeInput(id="demo:nina", kind="Service")]))
    assert result.rejected == 1


def test_duplicate_in_upload_rejected():
    node = NodeInput(id="demo:new", kind="Service", title="new", source_ref="fixture://new")
    result = ingest(MemoryStore(), Bundle(nodes=[node, node]))
    assert result.rejected == 2


@pytest.mark.parametrize("value", ["2026-10-15T10:00:00", "not-a-date", None])
def test_timezone_required_and_explicit_null_rejected(value):
    with pytest.raises(ValidationError):
        NodeInput(id="demo:new", kind="Incident", occurred_at=value)


def test_empty_csv_is_safe():
    assert parse_csv(b"id,kind,title\n", None) == Bundle()
