# KnowGraph AI — The Evidence-Driven Company Brain

KnowGraph AI is a local engineering-investigation demo. It connects incidents, deployments, services, pull requests, commits, people, tickets, and documentation in FalkorDB, then answers questions with evidence IDs, excerpts, and the actual graph paths returned by the database.

> **Synthetic demo data:** AcmePay is fictional. Every person, incident, deployment, timestamp, ticket, document, relationship, and evidence excerpt in the bundled fixture is illustrative. Nothing here describes a real company or production incident.

The model runs locally through Ollama. There are no paid APIs, hosted LLMs, API keys, or vector database requirements. The model cannot run Cypher or arbitrary Python. The application selects facts only from approved graph queries and constructs answer claims from those facts; timing does not establish causation.

## Features

- Search synthetic incidents and retrieve connected changes, deployments, services, people, tickets, commits, and runbooks.
- Show the returned nodes and directed, evidence-carrying graph relationships; each cited fact exposes its source ID and excerpt.
- Separate graph-supported facts, tentative evidence-linked hypotheses, and explicit limitations.
- Report backend, FalkorDB, and configured local Ollama model availability.
- Seed the fixture idempotently with Cypher `MERGE`.

## Architecture

[View the architecture diagram](docs/architecture.md).

The graph is the system of record. FastAPI validates requests and coordinates allow-listed graph queries with a local Ollama model. Ollama selects IDs from facts already retrieved; it does not issue queries. Streamlit displays the API response and only draws graph records the API returned.

## Requirements

- Python 3.12 or newer
- Docker Engine/Desktop and Docker Compose plugin
- Ollama installed locally, with an already available chat model (default: `llama3:latest`)

## Setup

Run once from the project root:

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Set `OLLAMA_MODEL` in `.env` to a chat model already available in `ollama list`. The default model is `llama3:latest`. If no local chat model is installed, install one separately before the demo; KnowGraph does not download models or use a hosted fallback. `nomic-embed-text` is not a chat model and is not used by this MVP. No API key is needed.

## Launch the demo

Keep each service running in its own terminal, all opened at the project root. Start in this order.

**Terminal 1 — FalkorDB**

```bash
docker compose up -d --wait
.venv/bin/python -m knowgraph.cli check
.venv/bin/python -m knowgraph.cli seed
```

FalkorDB listens on `localhost:6379`; its browser UI is exposed on `http://localhost:3000`. The graph name defaults to `knowgraph`. Connection settings are in `.env` (`FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_USERNAME`, `FALKORDB_PASSWORD`, `FALKORDB_GRAPH`). The provided compose service uses a local named volume for persistence.

**Terminal 2 — Ollama**

Check the installed model:

```bash
ollama list
```

If Ollama is not already running, start it in this terminal:

```bash
ollama serve
```

Ollama listens on `http://localhost:11434`. `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_TIMEOUT_SECONDS` are configurable in `.env`. The selected model must already be installed; the app never calls a paid or remote model provider.

**Terminal 3 — FastAPI**

```bash
.venv/bin/uvicorn knowgraph.api:app --host 127.0.0.1 --port 8000 --reload
```

Check readiness at `http://localhost:8000/health` or `http://localhost:8000/docs`.

**Terminal 4 — Streamlit**

```bash
.venv/bin/streamlit run frontend/app.py
```

Open the local URL printed by Streamlit (normally `http://localhost:8501`). The frontend calls the local API at `http://localhost:8000`; override it with `KNOWGRAPH_API_URL` if needed. This client only accepts loopback URLs.

## Try a question

Use the first example in the UI, or send a request directly:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did checkout start failing after the latest deployment?"}'
```

Other fixture questions:

- `What changed in checkout around incident inc-2026-104?`
- `Who authored the pull request linked to the checkout incident?`
- `What documentation is connected to the checkout incident?`
- `What service dependencies are recorded for checkout?`

The last question demonstrates a known gap: **the fixture has no service-to-service dependency edges**. The investigator reports that limitation and does not invent dependencies. Answers are evidence-backed connections, not confirmed root-cause analysis.

## Tests

Run unit tests without FalkorDB:

```bash
.venv/bin/python -m pytest -q
```

Run the opt-in tests against a running local FalkorDB:

```bash
RUN_FALKORDB_INTEGRATION=1 .venv/bin/python -m pytest -q
```

## Limitations

- All included AcmePay data is synthetic, not operational company evidence.
- No service dependency relationships are seeded, so dependency traversal is unavailable.
- The graph contains one small incident scenario; it is not connected to GitHub, ticketing, deployment, or document systems.
- The model can select only retrieved fact IDs. It cannot prove causation from temporal proximity; unsupported answers return an insufficient-evidence response.
- No authentication, multi-user controls, frontend deployment, or hosted services are included. Keep the demo bound to localhost.

## Troubleshooting and shutdown

- **Docker/FalkorDB is unavailable:** confirm Docker Desktop/Engine is running, then run `docker compose up -d --wait` and `.venv/bin/python -m knowgraph.cli check`.
- **Ollama is unavailable:** run `ollama serve` if needed, check `ollama list`, then make `.env` `OLLAMA_MODEL` match an installed chat model.
- **API health is degraded:** `/health` identifies FalkorDB and Ollama availability separately. Restart the missing service, then use **Refresh status** in the dashboard.
- **Streamlit reports API unavailable:** start Terminal 3 and confirm `KNOWGRAPH_API_URL` points at the local FastAPI address.
- **No evidence is returned:** seed the graph, then ask about `checkout` or `inc-2026-104`. The investigator reports when no matching evidence exists.

Stop the graph container with `docker compose down`; the named `falkordb_data` volume remains. `docker compose down -v` also removes that persisted graph data.

## Demo assets

- [Architecture diagram](docs/architecture.md)
- [2–3 minute demo script](docs/demo-script.md)
