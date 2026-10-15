"""Canonical node labels and relationship types used by the graph foundation."""

NODE_LABELS = (
    "Person", "Service", "PullRequest", "Commit", "Incident", "Ticket", "Document", "Deployment"
)

# All seeded relationships cite a synthetic artifact. Inferred edges are deliberately
# stored under a different relationship type and are never created by the seed process.
EVIDENCE_RELATIONSHIPS = {
    "AUTHORED": ("Person", "PullRequest"),
    "CHANGED": ("PullRequest", "Service"),
    "CONTAINS": ("PullRequest", "Commit"),
    "DEPLOYED": ("Deployment", "Service"),
    "TRIGGERED": ("Deployment", "Incident"),
    "TRACKED_BY": ("Incident", "Ticket"),
    "DOCUMENTED_IN": ("Service", "Document"),
    "REFERENCES": ("Ticket", "PullRequest"),
}
INFERRED_RELATIONSHIP = "INFERRED_LINK"
