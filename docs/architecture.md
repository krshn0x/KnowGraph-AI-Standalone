# KnowGraph AI architecture

All AcmePay records shown below are synthetic demo fixtures. Arrows are seeded relationship directions; the evidence graph view renders API-returned paths only.

```mermaid
flowchart LR
    U[Engineer question] --> UI[Streamlit dashboard]
    UI -->|local HTTP| API[FastAPI · Pydantic]
    API --> Q[Approved graph tools · Cypher]
    Q -->|evidence facts · paths| DB[(FalkorDB · knowgraph)]
    API -->|question + retrieved fact IDs| LLM[Ollama · local model]
    LLM -->|selected fact IDs · hypotheses| API
    API -->|grounded response · limitations| UI

    D[Deployment] -->|TRIGGERED| I[Incident]
    D -->|DEPLOYED| S[Service]
    P[Person] -->|AUTHORED| PR[PullRequest]
    PR -->|CHANGED| S
    PR -->|CONTAINS| C[Commit]
    I -->|TRACKED_BY| T[Ticket]
    S -->|DOCUMENTED_IN| DOC[Document]
    T -->|REFERENCES| PR

    DB --- D
    DB --- I
    DB --- S
    DB --- P
```

The deployment/incident/change chain is the fixture's central scenario. The current fixture has no service-to-service dependency edge. Model-selected hypotheses, if returned, must cite evidence IDs and are displayed separately from graph-supported facts.
