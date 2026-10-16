"""Validated, serialized and retry-safe CSV/JSON imports."""

import csv
import io
import json
import time
from datetime import timezone

from knowgraph.graph import GraphStore
from knowgraph.models import Bundle, ImportResult, Kind, Relation

ALLOWED = {
    Relation.AUTHORED: ({Kind.PERSON}, {Kind.PR, Kind.COMMIT, Kind.DOCUMENT}),
    Relation.MODIFIES: ({Kind.PR, Kind.COMMIT}, {Kind.SERVICE}),
    Relation.AFFECTS: ({Kind.INCIDENT, Kind.TICKET}, {Kind.SERVICE}),
    Relation.RESOLVED: ({Kind.PERSON}, {Kind.INCIDENT, Kind.TICKET}),
    Relation.DEPENDS_ON: ({Kind.SERVICE}, {Kind.SERVICE}),
    Relation.DESCRIBES: ({Kind.DOCUMENT}, {Kind.SERVICE, Kind.INCIDENT, Kind.TICKET}),
    Relation.DEPLOYED: ({Kind.DEPLOYMENT}, {Kind.SERVICE}),
    Relation.INCLUDES: ({Kind.DEPLOYMENT, Kind.PR}, {Kind.COMMIT}),
    Relation.LINKED_TO: (set(Kind), set(Kind)),
}


def parse_json(content: bytes) -> Bundle:
    return Bundle.model_validate(json.loads(content))


def parse_csv(nodes: bytes | None, edges: bytes | None) -> Bundle:
    def rows(content):
        if not content:
            return []
        return [
            {k: v for k, v in row.items() if v not in ("", None)}
            for row in csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        ]

    return Bundle.model_validate({"nodes": rows(nodes), "edges": rows(edges)})


def ingest(store: GraphStore, bundle: Bundle) -> ImportResult:
    count = len(bundle.nodes) + len(bundle.edges)
    if not count:
        return ImportResult()
    # A Redis lock serializes imports across API workers and the seed CLI.
    with store.redis.lock(store.lock_name, timeout=120, blocking_timeout=5) as lock:
        existing = store.existing(
            list(
                {n.id for n in bundle.nodes}
                | {e.source for e in bundle.edges}
                | {e.target for e in bundle.edges}
            )
        )
        types = {i: Kind(p["kind"]) for i, p in existing.items()}
        errors = []
        seen_nodes, seen_edges = set(), set()
        for node in bundle.nodes:
            if node.id in seen_nodes:
                errors.append(f"Duplicate node ID in upload: {node.id}")
            seen_nodes.add(node.id)
            old = existing.get(node.id)
            if old and old["kind"] != node.kind:
                errors.append(f"Cannot change kind of {node.id}")
            if not old and (not node.title or not node.source_ref):
                errors.append(f"New node {node.id} needs title and source_ref")
            if not old and node.kind in {Kind.INCIDENT, Kind.DEPLOYMENT} and not node.occurred_at:
                errors.append(f"New {node.kind} {node.id} needs occurred_at with timezone")
            types[node.id] = node.kind
        for edge in bundle.edges:
            if edge.key in seen_edges:
                errors.append(f"Duplicate edge in upload: {edge.source} {edge.kind} {edge.target}")
            seen_edges.add(edge.key)
            if edge.source not in types or edge.target not in types:
                errors.append(f"Missing endpoint: {edge.source} -> {edge.target}")
                continue
            source_types, target_types = ALLOWED[edge.kind]
            if types[edge.source] not in source_types or types[edge.target] not in target_types:
                errors.append(
                    f"Invalid {edge.kind} direction/types: {edge.source} -> {edge.target}"
                )
        if errors:
            return ImportResult(rejected=count, errors=errors)

        result = ImportResult()
        renewed_at = time.monotonic()

        def renew():
            nonlocal renewed_at
            if time.monotonic() - renewed_at > 20:
                lock.extend(120, replace_ttl=True)
                renewed_at = time.monotonic()

        for node in bundle.nodes:
            renew()
            old = existing.get(node.id)
            props = node.model_dump(mode="json", exclude_unset=True)
            if node.occurred_at:
                props["occurred_at"] = node.occurred_at.astimezone(timezone.utc).isoformat()
            if old is None:
                store.upsert_node(node)
                result.created += 1
            elif all(old.get(k) == v for k, v in props.items()):
                result.unchanged += 1
            else:
                store.upsert_node(node)
                result.updated += 1
        for edge in bundle.edges:
            renew()
            old = store.edge_properties(edge)
            props = edge.model_dump(exclude_unset=True) | {"id": edge.key}
            if old is None:
                store.upsert_edge(edge)
                result.created += 1
            elif all(old.get(k) == v for k, v in props.items()):
                result.unchanged += 1
            else:
                store.upsert_edge(edge)
                result.updated += 1
        return result
