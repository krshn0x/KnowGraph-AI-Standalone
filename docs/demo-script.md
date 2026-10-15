# KnowGraph AI — 2–3 minute demo

**Before presenting:** start FalkorDB, Ollama, FastAPI, and Streamlit using the README's four-terminal commands. Confirm the sidebar says API, FalkorDB, and Ollama are ready. Keep the synthetic AcmePay banner visible.

## 0:00–0:25 · Set context

“KnowGraph AI is a local engineering investigator. It joins incidents, deployments, services, code changes, people, tickets, and docs in FalkorDB. The AcmePay story is synthetic demo data. The model runs locally in Ollama; it only selects evidence IDs returned by approved graph queries.”

## 0:25–1:10 · Investigate

Ask: **“Why did checkout start failing after the latest deployment?”**

“The graph connects this deployment to the incident and to the checkout service. The incident excerpt says failures began 13 minutes after release. That is temporal evidence; the system does not claim it proves the deployment caused the incident.”

Expand the supporting facts to show their evidence IDs, source IDs, paths, and excerpts. Point out the explicit limitations.

## 1:10–1:50 · Follow the graph

Open **Evidence Graph**.

“Every node and arrow comes from a graph path returned by the API. The arrows retain the relationship directions, and each relationship has its source ID and evidence excerpt. Here we can follow deployment → incident and deployment → checkout service, then the pull request's change to that service and the author relationship.”

Mention: “The fixture has no service dependency edges, so KnowGraph reports that gap instead of drawing an invented dependency.”

## 1:50–2:20 · Inspect sources and people

Open **Sources** and **Experts**.

“Sources are labelled as synthetic and show only source records and excerpts supplied by the backend. Maya Chen appears because the returned graph path links her to the pull request through `AUTHORED`; the UI shows that relationship as the relevance reason.”

## 2:20–2:40 · Close

Open **System Status**.

“The readiness panel checks the local API, FalkorDB, and Ollama model. This MVP demonstrates evidence retrieval and traceability; it does not confirm root causes or connect to real company systems.”
