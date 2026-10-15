from knowgraph.models import ChatResponse, Hypothesis
from knowgraph.ollama import OllamaClient
from knowgraph.tools import facts_from_paths, incident_paths, query_terms, related_records, search_incidents


NO_EVIDENCE_ANSWER = "I don't have enough graph evidence to answer that question."


class Investigator:
    def __init__(self, graph, ollama: OllamaClient):
        self.graph = graph
        self.ollama = ollama

    def investigate(self, question: str) -> ChatResponse:
        limitations: list[str] = []
        incidents_by_id = {}
        for term in query_terms(question):
            for incident in search_incidents(self.graph, term):
                incidents_by_id[incident.id] = incident
        incidents = list(incidents_by_id.values())[:5]
        if not incidents:
            return ChatResponse(
                answer=NO_EVIDENCE_ANSWER,
                limitations=["No matching incident records were found in the graph."],
            )

        paths = []
        people = {}
        for incident in incidents:
            incident_change_paths = incident_paths(self.graph, incident.id)
            supplemental_paths, path_limitations = related_records(self.graph, incident.id)
            paths.extend(incident_change_paths)
            paths.extend(supplemental_paths)
            limitations.extend(path_limitations)
            for path in incident_change_paths:
                for node in path.nodes:
                    if node.label == "Person":
                        people[node.id] = node

        facts = facts_from_paths(paths)
        limitations = list(dict.fromkeys(limitations))
        if not facts:
            return ChatResponse(
                answer=NO_EVIDENCE_ANSWER,
                graph_paths=paths,
                relevant_people=list(people.values()),
                limitations=limitations + ["Matching incident records have no cited evidence edges."],
            )

        analysis = self.ollama.analyze(question, [fact.model_dump() for fact in facts])
        known_fact_ids = {fact.id for fact in facts}
        selected_ids = list(dict.fromkeys(
            fact_id for fact_id in analysis.selected_fact_ids if fact_id in known_fact_ids
        ))
        accepted_hypotheses = [
            hypothesis for hypothesis in analysis.hypotheses
            if hypothesis.text.strip() and hypothesis.evidence_ids
            and set(hypothesis.evidence_ids) <= known_fact_ids
        ]
        referenced_ids = list(dict.fromkeys(selected_ids + [
            evidence_id for item in accepted_hypotheses for evidence_id in item.evidence_ids
        ]))
        facts_by_id = {fact.id: fact for fact in facts}
        cited = [facts_by_id[fact_id] for fact_id in referenced_ids]
        selected_facts = [facts_by_id[fact_id] for fact_id in selected_ids]
        if selected_facts:
            answer = (
                "The graph supports these evidence-backed connections: "
                + " ".join(
                    f"{fact.statement} Source {fact.source_id}: {fact.evidence_excerpt}"
                    for fact in selected_facts
                )
                + " These records show connected events and changes, but do not establish a root cause."
            )
        else:
            answer = NO_EVIDENCE_ANSWER
            limitations.append("The model selected no verifiable graph evidence for an answer.")
        return ChatResponse(
            answer=answer,
            supporting_facts=cited,
            source_ids=list(dict.fromkeys(fact.source_id for fact in cited)),
            evidence_excerpts=list(dict.fromkeys(fact.evidence_excerpt for fact in cited)),
            graph_paths=paths,
            relevant_people=list(people.values()),
            hypotheses=[Hypothesis.model_validate(item.model_dump()) for item in accepted_hypotheses],
            limitations=limitations,
        )
