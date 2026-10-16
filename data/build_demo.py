"""Rebuild the deterministic fictional-company fixtures; standard library only."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent
nodes, edges = [], []


def node(id, kind, title, body="", at=None, **extra):
    item = dict(
        id=f"demo:{id}",
        kind=kind,
        title=title,
        body=body,
        source_ref=f"fixture://northstar/{id}",
        **extra,
    )
    if at:
        item["occurred_at"] = at
    nodes.append(item)
    return item["id"]


def edge(source, kind, target):
    edges.append(
        dict(
            source=f"demo:{source}",
            kind=kind,
            target=f"demo:{target}",
            source_ref=f"fixture://northstar/links/{source}/{kind}/{target}",
        )
    )


people = {
    "ada": "Ada Chen",
    "nina": "Nina Patel",
    "bruno": "Bruno Silva",
    "mei": "Mei Tan",
    "omar": "Omar Khan",
    "lena": "Lena Ortiz",
    "sam": "Sam Okafor",
    "priya": "Priya Rao",
}
for key, name in people.items():
    node(key, "Person", name, f"Engineer at fictional Northstar Labs. Contact handle: @{key}.")

services = {
    "checkout": "Checkout API: shopping cart, retry policy and order submission.",
    "payments": "Payments API: payment authorization and ledger integration.",
    "ledger": "Ledger service: transaction storage and database connection pooling.",
    "queue-worker": "Queue worker: background jobs, delivery retries and queue lag.",
    "notifications": "Notifications service: email and message delivery.",
    "analytics": "Analytics service: event aggregation and reporting.",
}
for key, body in services.items():
    node(key, "Service", key, body)
for a, b in [("checkout", "payments"), ("payments", "ledger"), ("notifications", "queue-worker")]:
    edge(a, "DEPENDS_ON", b)

incidents = [
    (
        "inc-checkout",
        "Checkout errors after morning release",
        "checkout",
        "2026-10-15T10:00:00Z",
        "HTTP 503 rate rose to 18%. Retry volume increased. Root cause is not yet confirmed.",
        None,
    ),
    (
        "inc-payments",
        "Payment authorization timeouts",
        "payments",
        "2026-10-15T11:00:00Z",
        "Authorization p99 reached 8 seconds. Ledger connection waits increased. Investigate dependency changes.",
        None,
    ),
    (
        "inc-queue",
        "Recurring queue lag and duplicate retries",
        "queue-worker",
        "2026-10-15T12:00:00Z",
        "Queue age exceeded 15 minutes. Similar retry storms occurred in September. No new worker deployment today.",
        None,
    ),
    (
        "inc-checkout-old",
        "Checkout retry saturation in September",
        "checkout",
        "2026-09-12T09:00:00Z",
        "Unbounded retries saturated downstream connections. Nina restored bounded exponential backoff.",
        "nina",
    ),
    (
        "inc-checkout-older",
        "Checkout retry budget exhausted in August",
        "checkout",
        "2026-08-20T09:00:00Z",
        "Retry budget and jitter configuration corrected by Nina after investigating checkout overload.",
        "nina",
    ),
    (
        "inc-ledger-old",
        "Ledger database pool saturation",
        "ledger",
        "2026-09-20T08:00:00Z",
        "Bruno restored pool limits after identifying idle transaction growth.",
        "bruno",
    ),
    (
        "inc-queue-old",
        "Queue poison-message retry storm",
        "queue-worker",
        "2026-09-24T08:00:00Z",
        "Mei isolated a poison message and configured dead-letter routing.",
        "mei",
    ),
    (
        "inc-queue-older",
        "Queue dead-letter routing disabled",
        "queue-worker",
        "2026-08-24T08:00:00Z",
        "Mei restored dead-letter routing to stop repeated job delivery.",
        "mei",
    ),
    (
        "inc-analytics",
        "Analytics report delay",
        "analytics",
        "2026-10-14T08:00:00Z",
        "Slow report job. Unrelated to checkout, payments and queue incidents.",
        "omar",
    ),
]
for key, title, service, at, body, resolver in incidents:
    node(
        key,
        "Incident",
        title,
        body,
        at,
        status="resolved" if resolver else "investigating",
        environment="production",
    )
    edge(key, "AFFECTS", service)
    if resolver:
        edge(resolver, "RESOLVED", key)

changes = [
    ("checkout-retry", "checkout", "ada", "Adjust checkout retry policy", "2026-10-15T09:20:00Z"),
    (
        "ledger-pool",
        "ledger",
        "bruno",
        "Reduce ledger connection pool size",
        "2026-10-15T10:10:00Z",
    ),
    ("analytics-chart", "analytics", "omar", "Add analytics report chart", "2026-10-15T09:30:00Z"),
    ("checkout-future", "checkout", "sam", "Checkout response headers", "2026-10-15T10:20:00Z"),
    (
        "checkout-staging",
        "checkout",
        "lena",
        "Staging checkout cache experiment",
        "2026-10-15T09:10:00Z",
    ),
    ("checkout-old", "checkout", "nina", "Document checkout retry budgets", "2026-10-01T08:00:00Z"),
    (
        "queue-routing",
        "queue-worker",
        "mei",
        "Enable queue dead-letter routing",
        "2026-09-24T10:00:00Z",
    ),
    ("payments-trace", "payments", "priya", "Add payment trace context", "2026-10-13T08:00:00Z"),
    (
        "notifications-template",
        "notifications",
        "lena",
        "Update notification templates",
        "2026-10-14T08:00:00Z",
    ),
    ("ledger-metrics", "ledger", "bruno", "Expose ledger pool utilization", "2026-09-21T08:00:00Z"),
    ("queue-jitter", "queue-worker", "mei", "Queue retry jitter limits", "2026-09-25T08:00:00Z"),
    ("analytics-export", "analytics", "omar", "Analytics CSV export", "2026-10-12T08:00:00Z"),
    ("payments-audit", "payments", "priya", "Payment audit event IDs", "2026-10-10T08:00:00Z"),
    (
        "notifications-metrics",
        "notifications",
        "sam",
        "Notification delivery metrics",
        "2026-10-11T08:00:00Z",
    ),
    ("ledger-read", "ledger", "bruno", "Ledger read timeout", "2026-10-09T08:00:00Z"),
    ("checkout-cart", "checkout", "ada", "Checkout cart validation", "2026-10-08T08:00:00Z"),
    ("queue-health", "queue-worker", "mei", "Queue worker readiness probe", "2026-10-07T08:00:00Z"),
    ("analytics-cache", "analytics", "omar", "Analytics report cache", "2026-10-06T08:00:00Z"),
]
for index, (key, service, author, title, at) in enumerate(changes):
    body = (
        f"Change in {service}. {title}. Review deployment lineage before attributing an incident."
    )
    if key == "checkout-retry":
        body = "Changes retry configuration and timeout handling in checkout/client.py. Reviewed and merged; impact under investigation."
    node(f"pr-{key}", "PullRequest", title, body, at, status="merged")
    node(f"commit-{key}", "Commit", f"{title} — implementation", body, at)
    edge(author, "AUTHORED", f"pr-{key}")
    edge(author, "AUTHORED", f"commit-{key}")
    edge(f"pr-{key}", "INCLUDES", f"commit-{key}")
    edge(f"pr-{key}", "MODIFIES", service)
    edge(f"commit-{key}", "MODIFIES", service)
    if index < 6:
        node(
            f"commit-{key}-test",
            "Commit",
            f"Tests for {title}",
            f"Regression tests for {service}.",
            at,
        )
        edge(author, "AUTHORED", f"commit-{key}-test")
        edge(f"pr-{key}", "INCLUDES", f"commit-{key}-test")

deployments = [
    ("checkout-retry", "2026-10-15T09:50:00Z", "production"),
    ("ledger-pool", "2026-10-15T10:40:00Z", "production"),
    ("analytics-chart", "2026-10-15T09:55:00Z", "production"),
    ("checkout-future", "2026-10-15T10:30:00Z", "production"),
    ("checkout-staging", "2026-10-15T09:40:00Z", "staging"),
    ("checkout-old", "2026-10-01T09:00:00Z", "production"),
    ("queue-routing", "2026-09-24T11:00:00Z", "production"),
    ("payments-trace", "2026-10-13T09:00:00Z", "production"),
    ("notifications-template", "2026-10-14T09:00:00Z", "production"),
    ("ledger-metrics", "2026-09-21T09:00:00Z", "production"),
    ("queue-jitter", "2026-09-25T09:00:00Z", "production"),
    ("analytics-export", "2026-10-12T09:00:00Z", "production"),
]
service_for = {c[0]: c[1] for c in changes}
for index, (key, at, env) in enumerate(deployments):
    node(
        f"deploy-{key}",
        "Deployment",
        f"Deploy {key}",
        f"Release to {env}.",
        at,
        environment=env,
        status="completed",
    )
    edge(f"deploy-{key}", "DEPLOYED", service_for[key])
    edge(f"deploy-{key}", "INCLUDES", f"commit-{key}")
    if index < 6:
        edge(f"deploy-{key}", "INCLUDES", f"commit-{key}-test")

for index, (service, body) in enumerate(services.items()):
    owner = {
        "checkout": "nina",
        "payments": "priya",
        "ledger": "bruno",
        "queue-worker": "mei",
        "notifications": "lena",
        "analytics": "omar",
    }[service]
    for suffix, title, content in [
        (
            "runbook",
            "runbook",
            f"Check {service} metrics, identify recent deployments, compare historical incidents, and escalate to @{owner}.",
        ),
        ("architecture", "architecture guide", body),
        (
            "operations",
            "operations checklist",
            f"Verify {service} readiness, error rate, retry volume and dependency health.",
        ),
    ]:
        if service == "checkout" and suffix == "runbook":
            content += " For retry saturation, inspect retry budget, exponential backoff and jitter before proposing rollback."
        if service == "queue-worker" and suffix == "runbook":
            content += " For recurring lag, inspect poison messages and dead-letter routing. Mei handled both previous incidents."
        if service == "ledger" and suffix == "runbook":
            content += " Inspect database wait time and connection pool limits; Bruno investigated pool saturation."
        node(
            f"doc-{service}-{suffix}",
            "Document",
            f"{service} {title}",
            content,
            "2026-10-02T08:00:00Z",
        )
        edge(owner, "AUTHORED", f"doc-{service}-{suffix}")
        edge(f"doc-{service}-{suffix}", "DESCRIBES", service)
    for i in range(1, 4):
        node(
            f"ticket-{service}-{i}",
            "Ticket",
            f"{service}: {['review alerts', 'operational follow-up', 'on-call handoff'][i - 1]}",
            f"Track {service} reliability and link operational evidence. Owner: @{owner}.",
            "2026-10-14T08:00:00Z",
            status="open",
        )
        edge(f"ticket-{service}-{i}", "AFFECTS", service)
edge("doc-checkout-runbook", "DESCRIBES", "inc-checkout-old")
edge("doc-queue-worker-runbook", "DESCRIBES", "inc-queue-old")
edge("ticket-checkout-1", "LINKED_TO", "inc-checkout")
edge("ticket-payments-1", "LINKED_TO", "inc-payments")
edge("ticket-queue-worker-1", "LINKED_TO", "inc-queue")

bundle = {"nodes": nodes, "edges": edges}
(ROOT / "demo.json").write_text(json.dumps(bundle, indent=2) + "\n")
for name, records in [("nodes", nodes), ("edges", edges)]:
    fields = list(dict.fromkeys(k for record in records for k in record))
    with (ROOT / f"{name}.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)

resolution = {
    "nodes": [
        {
            "id": "demo:inc-checkout",
            "kind": "Incident",
            "status": "resolved",
            "body": "Resolved after rollback. Investigation confirmed the retry-policy change removed the retry budget and exhausted downstream connections. See the resolution note.",
        },
        {
            "id": "demo:doc-checkout-resolution",
            "kind": "Document",
            "title": "Checkout incident resolution — retry budget regression",
            "source_ref": "fixture://northstar/doc-checkout-resolution",
            "occurred_at": "2026-10-15T13:00:00Z",
            "body": "Nina confirmed deploy-checkout-retry introduced commit-checkout-retry from pr-checkout-retry. The retry budget was removed, causing downstream connection exhaustion. Rollback restored the 503 rate from 18% to below 0.1%. Restore bounded backoff and add a retry-budget regression test.",
        },
    ],
    "edges": [
        {"source": "demo:nina", "kind": "RESOLVED", "target": "demo:inc-checkout"},
        {"source": "demo:nina", "kind": "AUTHORED", "target": "demo:doc-checkout-resolution"},
        {
            "source": "demo:doc-checkout-resolution",
            "kind": "DESCRIBES",
            "target": "demo:inc-checkout",
        },
        {"source": "demo:doc-checkout-resolution", "kind": "DESCRIBES", "target": "demo:checkout"},
        {
            "source": "demo:doc-checkout-resolution",
            "kind": "LINKED_TO",
            "target": "demo:pr-checkout-retry",
        },
    ],
}
(ROOT / "resolution_update.json").write_text(json.dumps(resolution, indent=2) + "\n")
print(f"Wrote {len(nodes)} fictional nodes and {len(edges)} edges.")
