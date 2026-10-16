from datetime import timedelta

from knowgraph.graph import GraphStore, combine
from knowgraph.models import (
    DocumentResult,
    Entity,
    Evidence,
    Expert,
    ExpertResult,
    Investigation,
    Kind,
)


class NotFound(ValueError):
    pass


class Retrieval:
    def __init__(self, store: GraphStore):
        self.store = store

    def context(self, query: str) -> tuple[list[str], Evidence]:
        node = self.store.get(query)
        if node:
            if node.kind == Kind.SERVICE:
                return [node.id], Evidence(nodes=[node])
            paths = self.store.paths(
                "MATCH p=(n:Entity)-[:AFFECTS|DESCRIBES|MODIFIES|DEPLOYED]-(s:Service) "
                "WHERE n.id=$id ",
                {"id": node.id},
            )
            return [n.id for n in paths.nodes if n.kind == Kind.SERVICE], paths
        services = self.store.search(query, [Kind.SERVICE], limit=5)
        return [s.id for s in services], Evidence(nodes=services)

    def investigate(self, incident_id: str, lookback_hours: int = 24) -> Investigation:
        incident = self.store.get(incident_id)
        if not incident or incident.kind != Kind.INCIDENT:
            raise NotFound(f"Incident not found: {incident_id}")
        affected = self.store.paths(
            "MATCH p=(i:Incident {id:$id})-[:AFFECTS]->(s:Service) ",
            {"id": incident_id},
        )
        dependencies = self.store.paths(
            "MATCH p=(i:Incident {id:$id})-[:AFFECTS]->(:Service)-[:DEPENDS_ON*1..2]->(:Service) ",
            {"id": incident_id},
        )
        evidence = combine(Evidence(nodes=[incident]), affected, dependencies)
        services = [n for n in evidence.nodes if n.kind == Kind.SERVICE]
        warnings = [
            "Deployments preceding an incident are candidates; timing alone does not prove causation."
        ]
        if not services:
            warnings.append("No affected service is recorded.")
        deployments, changes, related = [], [], []
        if incident.occurred_at:
            params = {
                "ids": [s.id for s in services],
                "env": incident.environment,
                "start": int((incident.occurred_at - timedelta(hours=lookback_hours)).timestamp()),
                "end": int(incident.occurred_at.timestamp()),
            }
            deployed = self.store.paths(
                "MATCH p=(s:Service)<-[:DEPLOYED]-(d:Deployment) "
                "WHERE s.id IN $ids AND d._time >= $start AND d._time <= $end "
                "AND ($env='' OR d.environment=$env) ",
                params,
            )
            deployments = [n for n in deployed.nodes if n.kind == Kind.DEPLOYMENT]
            lineage = self.store.paths(
                "MATCH p=(d:Deployment)-[:INCLUDES]->(c:Commit) WHERE d.id IN $ids ",
                {"ids": [d.id for d in deployments]},
            )
            prs = self.store.paths(
                "MATCH p=(d:Deployment)-[:INCLUDES]->(c:Commit)<-[:INCLUDES]-(pr:PullRequest) "
                "WHERE d.id IN $ids ",
                {"ids": [d.id for d in deployments]},
            )
            change_graph = combine(lineage, prs)
            changes = [n for n in change_graph.nodes if n.kind in {Kind.COMMIT, Kind.PR}]
            authors = self.store.paths(
                "MATCH p=(person:Person)-[:AUTHORED]->(c:Entity) WHERE c.id IN $ids ",
                {"ids": [c.id for c in changes]},
            )
            previous = self.store.paths(
                "MATCH p=(past:Incident)-[:AFFECTS]->(s:Service) "
                "WHERE s.id IN $ids AND past.id <> $incident AND past._time < $end ",
                params | {"incident": incident_id},
            )
            related = [n for n in previous.nodes if n.kind == Kind.INCIDENT]
            resolutions = self.store.paths(
                "MATCH p=(person:Person)-[:RESOLVED]->(i:Incident) WHERE i.id IN $ids ",
                {"ids": [incident_id] + [i.id for i in related]},
            )
            documentation = self.store.paths(
                "MATCH p=(d:Document)-[:DESCRIBES]->(i:Incident) WHERE i.id IN $ids ",
                {"ids": [incident_id] + [i.id for i in related]},
            )
            evidence = combine(
                evidence, deployed, change_graph, authors, previous, resolutions, documentation
            )
        else:
            warnings.append("Missing incident onset time; deployment correlation is unavailable.")
        if not deployments:
            warnings.append(
                "No matching deployment was found in the lookback window and environment."
            )
        if evidence.truncated:
            warnings.append("Evidence was truncated; narrow the investigation.")
        timeline = sorted([n for n in evidence.nodes if n.occurred_at], key=lambda n: n.occurred_at)
        return Investigation(
            incident=incident,
            services=services,
            deployments=deployments,
            changes=changes,
            related_incidents=related,
            timeline=timeline,
            evidence=evidence,
            warnings=warnings,
        )

    def experts(self, query: str) -> ExpertResult:
        ids, context = self.context(query)
        resolved = self.store.paths(
            "MATCH p=(person:Person)-[:RESOLVED]->(:Incident)-[:AFFECTS]->(s:Service) "
            "WHERE s.id IN $ids ",
            {"ids": ids},
        )
        changes = self.store.paths(
            "MATCH p=(person:Person)-[:AUTHORED]->(c:Entity)-[:MODIFIES]->(s:Service) "
            "WHERE s.id IN $ids AND c.kind IN ['Commit', 'PullRequest'] ",
            {"ids": ids},
        )
        docs = self.store.paths(
            "MATCH p=(person:Person)-[:AUTHORED]->(:Document)-[:DESCRIBES]->(s:Service) "
            "WHERE s.id IN $ids ",
            {"ids": ids},
        )
        evidence = combine(context, resolved, changes, docs)
        nodes = {n.id: n for n in evidence.nodes}
        records: dict[str, dict[str, Entity]] = {}
        for path in resolved.paths + changes.paths + docs.paths:
            records.setdefault(path.node_ids[0], {})[path.node_ids[1]] = nodes[path.node_ids[1]]
        experts = []
        activity = {}
        weights = {Kind.INCIDENT: 3, Kind.COMMIT: 2, Kind.PR: 2, Kind.DOCUMENT: 1}
        for person_id, items in records.items():
            person = nodes[person_id]
            reasons = [
                f"{weights[r.kind]} points: {'resolved' if r.kind == Kind.INCIDENT else 'authored'} "
                f"{r.title} ({r.id})"
                for r in items.values()
            ]
            activity[person_id] = max(
                (r.occurred_at.timestamp() if r.occurred_at else 0) for r in items.values()
            )
            experts.append(
                Expert(
                    person=person,
                    score=sum(weights[r.kind] for r in items.values()),
                    reasons=reasons,
                    evidence_ids=[person_id, *items],
                )
            )
        experts.sort(key=lambda e: (-e.score, -activity[e.person.id], e.person.id))
        return ExpertResult(experts=experts[:10], evidence=evidence)

    def documents(self, query: str) -> DocumentResult:
        found = self.store.search(query, [Kind.DOCUMENT, Kind.TICKET], limit=20)
        ids, context = self.context(query)
        connected = self.store.paths(
            "MATCH p=(d:Document)-[:DESCRIBES]->(s:Service) WHERE s.id IN $ids ",
            {"ids": ids},
        )
        tickets = self.store.paths(
            "MATCH p=(t:Ticket)-[:AFFECTS]->(s:Service) WHERE s.id IN $ids ",
            {"ids": ids},
        )
        direct = self.store.paths(
            "MATCH p=(d:Document)-[:DESCRIBES]->(n:Entity) WHERE n.id=$id ",
            {"id": query},
        )
        evidence = combine(context, Evidence(nodes=found), connected, tickets, direct)
        # Include actual links for text-search hits, not just detached search results.
        links = self.store.paths(
            "MATCH p=(d:Entity)-[:DESCRIBES|AFFECTS|LINKED_TO]-(n:Entity) WHERE d.id IN $ids ",
            {"ids": [n.id for n in found]},
        )
        evidence = combine(evidence, links)
        docs = {n.id: n for n in found}
        docs.update(
            {
                n.id: n
                for n in connected.nodes + tickets.nodes + direct.nodes
                if n.kind in {Kind.DOCUMENT, Kind.TICKET}
            }
        )
        return DocumentResult(documents=list(docs.values())[:30], evidence=evidence)
