"""Small fictional AcmePay fixture. All dates and artifacts are synthetic."""

NODES = [
    ("Person", "person-maya", {"name": "Maya Chen", "role": "Backend Engineer"}),
    ("Person", "person-omar", {"name": "Omar Reyes", "role": "SRE"}),
    ("Service", "service-checkout", {"name": "checkout", "team": "Payments", "criticality": "high"}),
    ("Service", "service-ledger", {"name": "ledger", "team": "Payments", "criticality": "high"}),
    ("PullRequest", "pr-1842", {"title": "Retry provider authorization on timeout", "number": 1842, "state": "merged"}),
    ("Commit", "commit-a91c2e", {"sha": "a91c2e", "message": "Add authorization retry path"}),
    ("Deployment", "deploy-2026-10-14-17", {"version": "checkout-2026.10.14.3", "environment": "production", "deployed_at": "2026-10-14T17:05:00Z"}),
    ("Incident", "inc-2026-104", {"title": "Elevated checkout authorization failures", "severity": "SEV-2", "started_at": "2026-10-14T17:18:00Z", "status": "investigating"}),
    ("Ticket", "ticket-pay-773", {"key": "PAY-773", "title": "Investigate provider timeout retries", "status": "in progress"}),
    ("Document", "doc-runbook-checkout", {"title": "Checkout payment operations runbook", "kind": "runbook", "uri": "synthetic://acmepay/runbooks/checkout"}),
]

# (type, start_id, end_id, evidence_source_id, evidence_excerpt)
EDGES = [
    ("AUTHORED", "person-maya", "pr-1842", "pr-1842", "PR author: Maya Chen"),
    ("CHANGED", "pr-1842", "service-checkout", "pr-1842", "Files changed: services/checkout/authorization.py"),
    ("CONTAINS", "pr-1842", "commit-a91c2e", "pr-1842", "Merge commit a91c2e"),
    ("DEPLOYED", "deploy-2026-10-14-17", "service-checkout", "deploy-2026-10-14-17", "Production release checkout-2026.10.14.3"),
    ("TRIGGERED", "deploy-2026-10-14-17", "inc-2026-104", "inc-2026-104", "Incident timeline: failures began 13 minutes after release"),
    ("TRACKED_BY", "inc-2026-104", "ticket-pay-773", "ticket-pay-773", "Incident linked to PAY-773"),
    ("DOCUMENTED_IN", "service-checkout", "doc-runbook-checkout", "doc-runbook-checkout", "Checkout runbook describes provider timeout handling"),
    ("REFERENCES", "ticket-pay-773", "pr-1842", "ticket-pay-773", "PAY-773 references PR 1842"),
]
