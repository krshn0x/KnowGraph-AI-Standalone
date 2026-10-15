from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class GraphNode(BaseModel):
    id: str
    label: str
    properties: dict


class GraphRelationship(BaseModel):
    type: str
    start_id: str
    end_id: str
    source_id: str
    evidence_kind: str
    evidence_excerpt: str


class GraphPath(BaseModel):
    id: str
    nodes: list[GraphNode]
    relationships: list[GraphRelationship]


class SupportingFact(BaseModel):
    id: str
    statement: str
    source_id: str
    evidence_excerpt: str
    path_id: str


class Hypothesis(BaseModel):
    text: str
    evidence_ids: list[str]


class ChatResponse(BaseModel):
    answer: str
    supporting_facts: list[SupportingFact] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    evidence_excerpts: list[str] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    relevant_people: list[GraphNode] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class OllamaAnalysis(BaseModel):
    selected_fact_ids: list[str] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
