# KnowGraph AI — three-minute demo

Before presenting, run `docker compose up -d --build`. Open http://localhost:8501. The Northstar Labs records are fictional. For AI chat, use AI settings to configure Gemini, Agent Router / DeepSeek, or OpenAI with an accessible model and key; the deterministic feature screens do not require them.

**0:00–0:45 — Investigate checkout.** In Investigations, select “Checkout errors after morning release.” Show the incident timeline and the deployment/commit/PR/author paths. Explain that staging releases, deployments after onset, and unrelated services are excluded. Timing alone does not establish cause.

**0:45–1:15 — Find experts and a runbook.** Search Experts for `demo:checkout`. Explain Nina's score from distinct resolutions, authored changes, and documents. Search Documents for `checkout retry`, open the runbook body, and inspect its source reference.

**1:15–1:45 — Show why relationships matter.** Investigate `demo:inc-payments`: payments depends on ledger, which has a relevant release. Investigate `demo:inc-queue`: no recent deployment is recorded, but prior similar incidents and Mei's resolution history are available.

**1:45–2:25 — Update knowledge.** Upload `data/resolution_update.json` in Data sources. Reinvestigate checkout to see the resolved status and new resolution note. Import the same file again: the report shows unchanged records, with no duplicates.

**2:25–3:00 — Ask and verify.** Ask “Investigate demo:inc-checkout. What changed, who can help, and which runbook should I read?” Show claim citations and the supporting directed graph. Open additional retrieved context separately. Without a key, demonstrate the explicit AI-unavailable state and continue using the structured feature screens.

For a repeat demo, explicit `docker compose run --rm seed knowgraph seed` merges the original fixture. It restores fields supplied by that fixture but does not delete the added resolution document or edges. Use a different `FALKORDB_GRAPH` name and recreate services for a completely fresh workspace.
