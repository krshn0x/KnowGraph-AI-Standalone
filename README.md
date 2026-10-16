# KnowGraph AI

An engineering company brain powered by **FalkorDB**. Investigate incidents, find experienced people and useful documents, inspect cited graph paths, and update company knowledge without duplicates.

The **Next.js + React + TypeScript** frontend is a dark engineering console: charcoal panels, restrained green accents, dense incident context, and an interactive React Flow evidence graph. FastAPI owns the graph and agent logic.

The bundled Northstar Labs workspace is fictional: **113 nodes, 209 relationships, three incident scenarios**. AI chat supports **Agent Router / DeepSeek** through OpenAI-compatible Chat Completions, or OpenAI’s Responses API with configurable `gpt-6.1-sol`. All structured investigation, expert, document, graph, and ingestion views work without an API key.

## Start with Docker

Install Docker Desktop/Engine with Compose, start Docker, and run from this repository:

```bash
cp .env.example .env
# Optional: configure provider credentials in .env, or use AI settings in the app.
docker compose up -d --build
```

Open **http://localhost:8501** for the dashboard and **http://localhost:8000/docs** for the API. Compose starts FalkorDB, seeds an empty graph, starts the API, then starts the Next.js standalone server. Initial startup downloads images and dependencies. Check startup with `docker compose ps` and `docker compose logs api seed frontend`.

A named volume persists FalkorDB's actual data directory (`/var/lib/falkordb/data`); append-only persistence is enabled. Normal startup skips seeding an existing graph, preserving imported updates. `docker compose down` retains the volume. Services are published on loopback for this local single-user prototype.

If port 6379 is already occupied, set `FALKORDB_PORT=6380` in `.env`. Container-to-container connections still use 6379. After changing provider settings in .env, run `docker compose up -d api`. Credentials stay in the backend; never commit `.env`.

## Connect Agent Router / DeepSeek

Open **AI settings** in the top bar (also available from Ask KnowGraph and System status):

1. Choose **Agent Router / DeepSeek**.
2. Enter your router’s OpenAI-compatible **API base URL** and the **exact model ID** shown in its dashboard for DeepSeek V4.
3. Paste the API key into the password field and select **Save AI settings**.
4. Open **Ask KnowGraph** and ask a question. Saving configures the provider; actual model access is checked when you send a question.

The URL is configurable because several services use the Agent Router name. For example, the `agentrouter.org` service [documents](https://github.com/agentrouter-org/docs/blob/main/qwencode.md) `https://agentrouter.org/v1`; use that only if it matches your provider. The adapter requires Chat Completions, function tools, and JSON-object output. Model IDs are passed through unchanged.

Keys entered in the app are held in **backend memory for that server session**. They are never returned by the settings API, placed in browser storage, or written to source files. Leave a saved key blank to keep it; **Disconnect provider** clears it for the session. Restarting the backend restores environment configuration. These settings belong to the local, single-user workspace.

For configuration that survives a restart, put these values in the gitignored root `.env`:

```dotenv
LLM_PROVIDER=agentrouter
AGENTROUTER_API_KEY=your-key
AGENTROUTER_BASE_URL=https://your-router.example/v1
AGENTROUTER_MODEL=exact-model-id-from-your-dashboard
```

Then run `docker compose up -d api`. For OpenAI, select it in AI settings or use `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. Provider keys remain separate; an Agent Router configuration never falls back to an OpenAI key.

## What you can do

| View | Behavior |
|---|---|
| Overview | Live graph counts, recent incidents, and a connected investigation map. |
| Ask KnowGraph | Natural-language questions, bounded conversation history, model-selected graph tools, cited claims, experts, and sources. |
| Investigations | Timeline, affected services, dependencies, deployments preceding onset, included commits/PRs, authors, similar incidents, and resolution notes. |
| Experts | Search independently by service, incident ID, or topic. Rank distinct records: resolved incident = 3, authored change = 2, authored document = 1. Latest activity breaks ties. |
| Documents | Full-text search for documents/tickets plus connected service and incident evidence. Inspect original source bodies and references. |
| Evidence Graph | Interactive directed graph with source inspection and path highlighting. Cited answer evidence is separate from additional retrieved context and neighborhood exploration. |
| Data sources | Upload JSON or node/edge CSV files; validate before writes; display created/updated/unchanged/rejected counts. |

Use **Cmd/Ctrl + K** to search source records from any screen. Graphs support pan, zoom, dragging nodes, path highlighting, source inspection, layout reset, and JSON export. Mobile navigation and layouts adapt to smaller screens. Every displayed metric comes from the API.

Incident investigation defaults to the preceding **24 hours**, matches the incident environment, and traverses up to two service-dependency hops. Deployment timing is evidence of correlation. A causal explanation remains a hypothesis unless source records explicitly establish a resolution.

## Demo in three minutes

1. In **Investigations**, investigate “Checkout errors after morning release” (`demo:inc-checkout`). Inspect `demo:deploy-checkout-retry` → commits → PR → Ada. Staging, future, old, and unrelated releases are excluded.
2. Find checkout experts and the checkout retry runbook. Nina ranks highly from recorded resolutions, changes, and documents.
3. Investigate `demo:inc-payments`: follow payments → ledger to the ledger deployment. Investigate `demo:inc-queue`: historical incidents and Mei's experience help despite no recent worker deployment.
4. In **Data sources**, upload `data/resolution_update.json`. Reinvestigate checkout: the incident is resolved and the newly recorded resolution is visible. Reimport the same file to see unchanged counts.
5. With a key configured, ask: “Investigate demo:inc-checkout. What changed, who can help, and which runbook should I read?” Open the cited evidence graph.

[Detailed demo script](docs/demo-script.md) · [Architecture and schema](docs/architecture.md)

## Ingestion contract

Upload through the dashboard or `POST /ingest` as multipart form data:

- `bundle_file`: JSON containing `nodes` and `edges`; **or**
- `nodes_file` and/or `edges_file`: CSV with header fields matching the JSON fields.

Example JSON:

```json
{
  "nodes": [
    {"id": "company:checkout", "kind": "Service", "title": "Checkout", "source_ref": "https://example.com/services/checkout"}
  ],
  "edges": []
}
```

Examples covering every node/relationship type are in `data/demo.json`, `data/nodes.csv`, and `data/edges.csv`. `python data/build_demo.py` regenerates these fixtures deterministically.

- IDs are stable, source-qualified strings such as `company:checkout` or `github:team/repo/pr/42`. New nodes require `id`, `kind`, `title`, and `source_ref`.
- Optional node fields: `body`, `occurred_at`, `status`, `environment`. New incidents and deployments require timezone-aware `occurred_at`.
- Edges require `source`, `kind`, and `target`; `source_ref` is optional. Identity is the directed source/type/target tuple.
- Both endpoints must already exist or appear in the same upload. Relationship directions/types, duplicate records within an upload, field sizes, and timestamps are validated before any write.
- Omitted fields preserve existing values; explicit node nulls are rejected. Node kinds cannot change. Omitted records are never deleted. Empty optional CSV cells mean “not supplied.”
- Imports are serialized with a Redis lock. A valid import interrupted by database failure can be retried safely; it is **not** a multi-record transaction. Full validation errors cause zero writes.
- Maximum upload: 8 MiB, 2,000 nodes, and 5,000 edges. Counts include both nodes and edges. Validation errors return HTTP 422; oversized uploads return 413.

```bash
curl -F bundle_file=@data/resolution_update.json http://localhost:8000/ingest
```

## API

| Endpoint | Returns |
|---|---|
| `POST /ask` | `{question, history?}` → claims, citations, sources, experts, cited `evidence`, additional `retrieved_evidence`, warnings, status, tool trace. |
| `GET /incidents/{id}/investigation?lookback_hours=24` | Deterministic investigation and timeline. |
| `GET /experts?q=demo:checkout` | Scored experts and supporting paths. |
| `GET /documents?q=checkout%20retry` | Relevant source records and relationships. |
| `GET /graph/neighborhood?node_id=demo:checkout&hops=2` | At most three hops and 100 nodes; truncation is reported. |
| `GET /entities?kind=Incident&q=checkout` | Record selection/search; `q` is optional. |
| `GET /entities/{id}` | Source body and metadata. |
| `POST /ingest` | Import summary or validation errors. |
| `GET /health` | Database readiness, record counts, selected provider/model, and configuration status. |
| `GET /settings/ai` | Selected provider and configuration metadata; keys are never returned. |
| `POST /settings/ai` | `{provider, model, base_url?, api_key?}` → update the backend session. Omit the key to preserve it; an empty key disconnects it. |

History accepts up to 12 `{role: "user" | "assistant", content: "..."}` messages. Questions are limited to 4,000 characters. Chat history lives in browser memory across console navigation and resets on reload, while company knowledge persists in FalkorDB.

The old `/chat` URL remains an alias for `/ask`, with the **new response schema**. AI provider configuration uses `LLM_PROVIDER` and the corresponding provider variables documented above; the original Ollama integration is not included. This version uses canonical `:Entity` nodes and source-qualified IDs; old demo records are not migrated or deleted. Select a fresh `FALKORDB_GRAPH` name if you want an entirely separate workspace.

## Local development and tests

Python **3.13+** and Node.js **22+** are required; containers and CI use Python 3.13 and Node 24.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
cp .env.example .env

docker compose up -d --wait falkordb
knowgraph seed
uvicorn knowgraph.api:app --host 127.0.0.1 --port 8000
# In another terminal:
cd web
npm ci
cp .env.example .env.local
npm run dev
```

Open **http://localhost:3000** during development. The Next.js server proxies `/api/*` to `API_BASE_URL` (default `http://127.0.0.1:8000`). Configure it in `web/.env.local` for local development; Compose supplies its internal API address at runtime. OpenAI credentials stay exclusively in FastAPI.

`knowgraph stats` prints canonical graph counts. Explicit `knowgraph seed` merges the fixture, so use it intentionally: it can restore fixture fields changed by a previous import. Automatic Compose seeding uses `--only-if-empty` instead.

```bash
pytest -q -m 'not integration and not live'
RUN_INTEGRATION=1 pytest -q -m 'not live'
ruff check .
ruff format --check .
```

Integration tests create unique temporary graphs and delete those graphs afterward. They exercise actual Cypher, ingestion retries/concurrency, the three scenarios, document search, evidence consistency, and API contracts. Unit tests exercise both provider protocols through the OpenAI SDK with mock HTTP transports, including DeepSeek reasoning replay, citation rejection, limits, missing credentials, outages, and provider failures. Settings tests verify write-only credentials, sanitized validation, configuration switching, client cleanup, and session reset.

The browser suite covers source inspection, graph paths/export, incident controls, expert/document search, uploads, citations, conversation continuity, errors, and mobile navigation. Fixture responses are fictional seed data and are intercepted only inside tests. CI builds both Docker images and also tests the real same-origin API proxy and multipart validation.

```bash
cd web
npm run lint
npm run build
npm run typecheck
npx playwright install chromium
npm run test:e2e
# Against a running Docker stack, including the real API proxy check:
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8501 KNOWGRAPH_LIVE_API=1 npm run test:e2e
```

Production JavaScript dependencies pass `npm audit --omit=dev`. The development-only Next.js lint dependency chain currently reports an unpatched `braces` advisory; do not lint untrusted glob configurations.

Optional live-model evaluation incurs API usage:

```bash
RUN_LIVE_MODEL=1 RUN_INTEGRATION=1 pytest -q -m live
```

It requires credentials and model access for the selected provider (Agent Router or OpenAI). CI runs without paid credentials. A configured key in `/health` indicates configuration only; it does not prove model access or provider availability.

## Limits and failure behavior

- The agent has five predefined read-only graph tools, at most eight tool calls, and a default 60-second investigation deadline. Each graph query has a two-second execution timeout. No model-generated Cypher is executed.
- Citation IDs must have been retrieved during the current question. This validates traceability, not semantic truth; inspect source bodies when judging a hypothesis.
- Missing key, provider failure, malformed output, and time/tool limits retain available source evidence and show an explicit warning. Structured feature views remain available without the model.
- Database outages return a sanitized HTTP 503. Unknown records return 404. Search is lexical full-text prefix matching with all supplied terms required, rather than embedding similarity.
- Live GitHub ingestion, authentication/company permissions, cloud hosting, autonomous remediation, and embeddings are deferred. GitHub is used for source control and automated checks.
