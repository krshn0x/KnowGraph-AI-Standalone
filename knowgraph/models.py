from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class Kind(StrEnum):
    PERSON = "Person"
    SERVICE = "Service"
    PR = "PullRequest"
    COMMIT = "Commit"
    INCIDENT = "Incident"
    TICKET = "Ticket"
    DOCUMENT = "Document"
    DEPLOYMENT = "Deployment"


class Relation(StrEnum):
    AUTHORED = "AUTHORED"
    MODIFIES = "MODIFIES"
    AFFECTS = "AFFECTS"
    RESOLVED = "RESOLVED"
    DEPENDS_ON = "DEPENDS_ON"
    DESCRIBES = "DESCRIBES"
    DEPLOYED = "DEPLOYED"
    INCLUDES = "INCLUDES"
    LINKED_TO = "LINKED_TO"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeInput(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+:[A-Za-z0-9_./:@-]+$", max_length=200)
    kind: Kind
    title: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, max_length=20000)
    source_ref: str | None = Field(default=None, max_length=1000)
    occurred_at: AwareDatetime | None = None
    status: str | None = Field(default=None, max_length=80)
    environment: str | None = Field(default=None, max_length=80)

    @field_validator(
        "title", "body", "source_ref", "occurred_at", "status", "environment", mode="before"
    )
    @classmethod
    def no_explicit_null(cls, value):
        if value is None:
            raise ValueError(
                "Omit fields to preserve existing values; explicit null is unsupported"
            )
        return value


class Entity(StrictModel):
    id: str
    kind: Kind
    title: str
    body: str = ""
    source_ref: str = ""
    occurred_at: datetime | None = None
    status: str = ""
    environment: str = ""


class EdgeInput(StrictModel):
    source: str = Field(min_length=1, max_length=200)
    kind: Relation
    target: str = Field(min_length=1, max_length=200)
    source_ref: str = Field(default="", max_length=1000)

    @property
    def key(self) -> str:
        value = f"{self.source}|{self.kind}|{self.target}"
        return "edge:" + sha256(value.encode()).hexdigest()[:24]


class GraphEdge(EdgeInput):
    id: str


class Bundle(StrictModel):
    nodes: list[NodeInput] = Field(default_factory=list, max_length=2000)
    edges: list[EdgeInput] = Field(default_factory=list, max_length=5000)


class EvidencePath(StrictModel):
    id: str
    node_ids: list[str]
    edge_ids: list[str]


class Evidence(StrictModel):
    nodes: list[Entity] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    paths: list[EvidencePath] = Field(default_factory=list)
    truncated: bool = False


class Claim(StrictModel):
    text: str
    evidence_ids: list[str]
    certainty: Literal["observed", "hypothesis"]


class Expert(StrictModel):
    person: Entity
    score: int
    reasons: list[str]
    evidence_ids: list[str]


class ExpertResult(StrictModel):
    experts: list[Expert]
    evidence: Evidence


class DocumentResult(StrictModel):
    documents: list[Entity]
    evidence: Evidence


class Investigation(StrictModel):
    incident: Entity
    services: list[Entity]
    deployments: list[Entity]
    changes: list[Entity]
    related_incidents: list[Entity]
    timeline: list[Entity]
    evidence: Evidence
    warnings: list[str]


class Message(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AskRequest(StrictModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[Message] = Field(default_factory=list, max_length=12)


class DraftAnswer(StrictModel):
    summary: str
    claims: list[Claim]
    insufficient_evidence: bool


class Answer(DraftAnswer):
    evidence: Evidence = Field(default_factory=Evidence)
    retrieved_evidence: Evidence = Field(default_factory=Evidence)
    sources: list[Entity] = Field(default_factory=list)
    experts: list[Expert] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    status: Literal["ok", "insufficient_evidence", "provider_error", "limit_reached"] = "ok"


class ImportResult(StrictModel):
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    errors: list[str] = Field(default_factory=list)
