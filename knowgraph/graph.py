"""FalkorDB persistence and bounded, read-only evidence queries."""

import re
from datetime import timezone
from hashlib import sha256

from falkordb.graph import Graph
from redis import Redis
from redis.exceptions import ResponseError

from knowgraph.config import Settings
from knowgraph.models import EdgeInput, Entity, Evidence, EvidencePath, GraphEdge, Kind, NodeInput


def entity(properties: dict) -> Entity:
    return Entity.model_validate({k: v for k, v in properties.items() if not k.startswith("_")})


def combine(*items: Evidence) -> Evidence:
    nodes, edges, paths = {}, {}, {}
    for item in items:
        nodes.update({n.id: n for n in item.nodes})
        edges.update({e.id: e for e in item.edges})
        paths.update({p.id: p for p in item.paths})
    return Evidence(
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        paths=list(paths.values()),
        truncated=any(item.truncated for item in items),
    )


def select_evidence(evidence: Evidence, citations: set[str]) -> Evidence:
    """Keep only cited paths/edges/nodes; never imply an uncited path supported a claim."""
    paths = [
        p
        for p in evidence.paths
        if p.id in citations or bool(set(p.edge_ids) & citations) or set(p.node_ids) <= citations
    ]
    edge_ids = citations | {i for p in paths for i in p.edge_ids}
    edges = [e for e in evidence.edges if e.id in edge_ids]
    node_ids = (
        citations
        | {i for p in paths for i in p.node_ids}
        | {i for e in edges for i in (e.source, e.target)}
    )
    return Evidence(
        nodes=[n for n in evidence.nodes if n.id in node_ids],
        edges=edges,
        paths=paths,
        truncated=evidence.truncated,
    )


PATH_RETURN = """
RETURN [n IN nodes(p) | properties(n)], [r IN relationships(p) | properties(r)]
LIMIT $limit
"""


class GraphStore:
    def __init__(self, settings: Settings):
        password = settings.falkordb_password.get_secret_value() or None
        options = dict(
            host=settings.falkordb_host,
            port=settings.falkordb_port,
            password=password,
            socket_connect_timeout=2,
            socket_timeout=5,
            decode_responses=True,
        )
        self.redis = Redis(**options)
        # Construct the graph on the Redis client without connecting at import time.
        # FalkorDB's top-level factory performs topology detection immediately.
        self.graph = Graph(self.redis, settings.falkordb_graph)
        self.lock_name = f"knowgraph:{settings.falkordb_graph}:import"

    def close(self):
        self.redis.close()

    def ping(self) -> bool:
        return bool(self.redis.ping())

    def initialize(self):
        with self.redis.lock(self.lock_name, timeout=120, blocking_timeout=5):
            for query in (
                "CREATE INDEX ON :Entity(id)",
                "CALL db.idx.fulltext.createNodeIndex('Entity', 'title', 'body')",
            ):
                try:
                    self.graph.query(query)
                except ResponseError as exc:
                    if not any(
                        s in str(exc).lower() for s in ("already indexed", "already exists")
                    ):
                        raise

    def read(self, query: str, params: dict | None = None):
        return self.graph.ro_query(query, params or {}, timeout=2000).result_set

    def get(self, node_id: str) -> Entity | None:
        rows = self.read("MATCH (n:Entity {id:$id}) RETURN properties(n)", {"id": node_id})
        return entity(rows[0][0]) if rows else None

    def existing(self, ids: list[str]) -> dict[str, dict]:
        rows = self.read("MATCH (n:Entity) WHERE n.id IN $ids RETURN properties(n)", {"ids": ids})
        return {r[0]["id"]: r[0] for r in rows}

    def edge_properties(self, edge: EdgeInput) -> dict | None:
        rows = self.read("MATCH ()-[r]->() WHERE r.id=$id RETURN properties(r)", {"id": edge.key})
        return rows[0][0] if rows else None

    def upsert_node(self, node: NodeInput):
        props = node.model_dump(mode="json", exclude_unset=True)
        props["kind"] = str(node.kind)
        if node.occurred_at is not None:
            props["occurred_at"] = node.occurred_at.astimezone(timezone.utc).isoformat()
            props["_time"] = int(node.occurred_at.timestamp())
        # Label is a validated enum; all user-supplied values are parameters.
        self.graph.query(
            f"MERGE (n:Entity {{id:$id}}) SET n:{node.kind} SET n += $props",
            {"id": node.id, "props": props},
        )

    def upsert_edge(self, edge: EdgeInput):
        props = edge.model_dump(exclude_unset=True) | {"id": edge.key}
        self.graph.query(
            f"MATCH (a:Entity {{id:$source}}), (b:Entity {{id:$target}}) "
            f"MERGE (a)-[r:{edge.kind} {{id:$id}}]->(b) ON CREATE SET r.source_ref='' SET r += $props",
            {"source": edge.source, "target": edge.target, "id": edge.key, "props": props},
        )

    def counts(self) -> dict:
        nodes = self.read("MATCH (n:Entity) RETURN count(n)")[0][0]
        edges = self.read("MATCH (:Entity)-[r]->(:Entity) RETURN count(r)")[0][0]
        return {"nodes": nodes, "edges": edges}

    def list_entities(self, kind: Kind | None = None, limit: int = 100) -> list[Entity]:
        return [
            entity(r[0])
            for r in self.read(
                "MATCH (n:Entity) WHERE $kind='' OR n.kind=$kind "
                "RETURN properties(n) ORDER BY n.title LIMIT $limit",
                {"kind": str(kind) if kind else "", "limit": min(limit, 100)},
            )
        ]

    def search(self, text: str, kinds: list[Kind] | None = None, limit: int = 20) -> list[Entity]:
        direct = self.get(text)
        if direct and (not kinds or direct.kind in kinds):
            return [direct]
        tokens = re.findall(r"[\w]+", text, flags=re.UNICODE)[:12]
        if not tokens:
            return []
        # Construct a term-only query. Never forward RediSearch operators from the user.
        term = " ".join(t + "*" for t in tokens if len(t) > 1)
        if not term:
            return []
        rows = self.read(
            "CALL db.idx.fulltext.queryNodes('Entity', $term) YIELD node, score "
            "WHERE size($kinds)=0 OR node.kind IN $kinds "
            "RETURN properties(node) ORDER BY score DESC, node.id LIMIT $limit",
            {"term": term, "kinds": [str(k) for k in kinds or []], "limit": min(limit, 100)},
        )
        return [entity(r[0]) for r in rows]

    def paths(self, match: str, params: dict, limit: int = 100) -> Evidence:
        rows = self.read(match + PATH_RETURN, params | {"limit": limit + 1})
        nodes, edges, paths = {}, {}, {}
        for raw_nodes, raw_edges in rows[:limit]:
            parsed_nodes = [entity(n) for n in raw_nodes]
            parsed_edges = [GraphEdge.model_validate(e) for e in raw_edges]
            nodes.update({n.id: n for n in parsed_nodes})
            edges.update({e.id: e for e in parsed_edges})
            node_ids = [n.id for n in parsed_nodes]
            edge_ids = [e.id for e in parsed_edges]
            path_id = "path:" + sha256("|".join(node_ids + edge_ids).encode()).hexdigest()[:24]
            paths[path_id] = EvidencePath(id=path_id, node_ids=node_ids, edge_ids=edge_ids)
        return Evidence(
            nodes=list(nodes.values()),
            edges=list(edges.values()),
            paths=list(paths.values()),
            truncated=len(rows) > limit,
        )

    def neighborhood(self, node_id: str, hops: int = 1, limit: int = 100) -> Evidence:
        root = self.get(node_id)
        if not root:
            return Evidence()
        result = Evidence(nodes=[root])
        seen = {node_id}
        frontier = [node_id]
        for _ in range(min(max(hops, 1), 3)):
            if not frontier:
                break
            layer = self.paths(
                "MATCH p=(a:Entity)-[]-(b:Entity) WHERE a.id IN $ids ", {"ids": frontier}, limit=400
            )
            accepted = Evidence(truncated=layer.truncated)
            next_frontier = []
            by_id = {n.id: n for n in layer.nodes}
            by_edge = {e.id: e for e in layer.edges}
            for path in layer.paths:
                new = [i for i in path.node_ids if i not in seen]
                if len(seen) + len(new) > limit:
                    accepted.truncated = True
                    continue
                for i in new:
                    seen.add(i)
                    next_frontier.append(i)
                accepted.nodes.extend(by_id[i] for i in path.node_ids)
                accepted.edges.extend(by_edge[i] for i in path.edge_ids)
                accepted.paths.append(path)
            result = combine(result, accepted)
            frontier = next_frontier
        return result
