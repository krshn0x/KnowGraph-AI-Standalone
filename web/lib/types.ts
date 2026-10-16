export type Kind = "Person" | "Service" | "PullRequest" | "Commit" | "Incident" | "Ticket" | "Document" | "Deployment";
export type View = "overview" | "investigations" | "ask" | "experts" | "documents" | "graph" | "sources";
export interface Entity {
  id: string; kind: Kind; title: string; body: string; source_ref: string;
  occurred_at: string | null; status: string; environment: string;
}
export interface GraphEdge { id: string; source: string; target: string; kind: string; source_ref: string }
export interface EvidencePath { id: string; node_ids: string[]; edge_ids: string[] }
export interface Evidence { nodes: Entity[]; edges: GraphEdge[]; paths: EvidencePath[]; truncated: boolean }
export type Provider = "openai" | "agentrouter" | "gemini" | "ollama";
export interface Health { status: string; database: string; ai_configured: boolean; model: string; nodes: number; edges: number; provider?: Provider; configuration_message?: string | null }
export interface AISettings {
  provider: Provider; configured: boolean; storage: "environment" | "session";
  providers: Record<Provider, { model: string; base_url: string; has_api_key: boolean; deadline_seconds?: number }>;
}
export interface Investigation {
  incident: Entity; services: Entity[]; deployments: Entity[]; changes: Entity[];
  related_incidents: Entity[]; timeline: Entity[]; evidence: Evidence; warnings: string[];
}
export interface Expert { person: Entity; score: number; reasons: string[]; evidence_ids: string[] }
export interface ExpertResult { experts: Expert[]; evidence: Evidence }
export interface DocumentResult { documents: Entity[]; evidence: Evidence }
export interface Claim { text: string; evidence_ids: string[]; certainty: "observed" | "hypothesis" }
export interface Answer {
  summary: string; claims: Claim[]; insufficient_evidence: boolean; evidence: Evidence;
  retrieved_evidence: Evidence; sources: Entity[]; experts: Expert[]; warnings: string[];
  tool_calls: string[]; status: "ok" | "insufficient_evidence" | "provider_error" | "limit_reached";
}
export interface ImportResult { created: number; updated: number; unchanged: number; rejected: number; errors: string[] }
export interface ChatEntry { id: string; question: string; answer: Answer }
