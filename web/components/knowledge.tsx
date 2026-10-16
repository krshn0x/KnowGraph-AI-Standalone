"use client";

import { useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, Check, CheckCircle2, Database, Download, FileJson, FileSpreadsheet, FileText, GitPullRequest, Info, Network, Search, ShieldCheck, Upload } from "lucide-react";
import { api, ApiError, date, emptyEvidence, initials, shortId } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { useWorkspace } from "@/lib/workspace";
import type { DocumentResult, Entity, Evidence, Expert, ExpertResult, ImportResult } from "@/lib/types";
import { EvidenceGraph } from "./evidence-graph";
import { Empty, ErrorNotice, KindBadge, KindIcon, Loading, Modal } from "./ui";
import { PageHeading } from "./investigations";

export function Experts() {
  const { services, revision, inspect, setLatestEvidence, navigate } = useWorkspace();
  const [input, setInput] = useState("demo:checkout");
  const [query, setQuery] = useState("demo:checkout");
  const result = useResource<ExpertResult>(`/experts?q=${encodeURIComponent(query)}`, revision);
  const firstScore = result.data?.experts[0]?.score || 1;
  return <><PageHeading eyebrow="PEOPLE & EXPERIENCE" title="Find the person behind the context." description="Discover relevant experience, with a clear explanation for every match." />
    <SearchForm label="Service, incident ID, or topic" placeholder="Search a service, incident ID, or topic…" input={input} setInput={setInput} submit={() => { if (input.trim()) setQuery(input.trim()); }} button="Find experts" />
    <div className="filter-row"><span>QUICK CONTEXT</span>{services.data?.map(service => <button className={`filter-chip ${query === service.id ? "active" : ""}`} key={service.id} onClick={() => { setInput(service.id); setQuery(service.id); }}><KindIcon kind="Service" size={12} />{service.title}</button>)}</div>
    <div className="results-heading"><h2>Relevant experts<span className="count-badge">{result.data?.experts.length ?? "—"}</span></h2><span>Ranked by recorded experience</span></div>
    {result.loading ? <Loading label="Connecting people to relevant experience…" /> : result.error ? <ErrorNotice message={result.error} /> : result.data?.experts.length ? <div className="experts-grid">{result.data.experts.map((expert, index) => <ExpertCard key={expert.person.id} expert={expert} index={index} maxScore={firstScore} evidence={result.data!.evidence} onInspect={inspect} onEvidence={() => { setLatestEvidence(result.data!.evidence); navigate("graph"); }} />)}</div> : <Empty title="No supported expert matches">Try a known service, an incident ID, or a more specific topic.</Empty>}
    <div className="scoring-note"><ShieldCheck size={18} /><div><strong>Experience you can verify</strong><p>3 points per resolved incident · 2 per authored change · 1 per authored document. Each record is counted once. Recent activity breaks ties.</p></div></div>
  </>;
}

export function ExpertCard({ expert, index = 0, maxScore = 1, evidence, onInspect, onEvidence }: {
  expert: Expert; index?: number; maxScore?: number; evidence: Evidence; onInspect: (entity: Entity) => void; onEvidence?: () => void;
}) {
  return <article className={`panel expert-card ${index === 0 ? "top-match" : ""}`}>
    <div className="expert-card-top"><span className={`person-avatar avatar-${index % 4}`}>{initials(expert.person.title)}</span><span className="expert-rank">{index === 0 ? "Strongest match" : `Match ${index + 1}`}</span></div>
    <button className="expert-name" onClick={() => onInspect(expert.person)}>{expert.person.title}<ArrowUpRight size={14} /></button>
    <p className="expert-description">{expert.person.body || "Relevant experience connected through company knowledge."}</p>
    <div className="expert-score"><div><strong>{expert.score}</strong><span>relevance score</span></div><span>{expert.reasons.length} linked records</span></div>
    <div className="score-bar"><span style={{ width: `${Math.min(100, expert.score / maxScore * 100)}%` }} /></div>
    <div className="expert-reasons"><span className="eyebrow">WHY THIS PERSON</span>{expert.reasons.map(reason => {
      const match = reason.match(/^(\d+) points: (resolved|authored) (.*) \(([^()]+)\)$/);
      const record = match ? evidence.nodes.find(n => n.id === match[4]) : undefined;
      return <button key={reason} className="expert-reason" disabled={!record} onClick={() => record && onInspect(record)}><span className="reason-icon">{match?.[2] === "resolved" ? <CheckCircle2 size={13} /> : <GitPullRequest size={13} />}</span><span>{match ? <><span className="reason-action">{match[2] === "resolved" ? "Resolved" : "Authored"}</span>{match[3]}</> : reason}</span>{match && <code>+{match[1]}</code>}</button>;
    })}</div>
    {onEvidence && <button className="expert-evidence" onClick={onEvidence}><Network size={13} />View supporting evidence<ArrowRight size={13} /></button>}
  </article>;
}

export function Documents() {
  const { revision, inspect, setLatestEvidence, navigate } = useWorkspace();
  const [input, setInput] = useState("checkout retry");
  const [query, setQuery] = useState("checkout retry");
  const [filter, setFilter] = useState("All knowledge");
  const result = useResource<DocumentResult>(`/documents?q=${encodeURIComponent(query)}`, revision);
  const documents = result.data?.documents.filter(doc => filter === "All knowledge" || (filter === "Tickets" ? doc.kind === "Ticket" : filter === "Runbooks" ? /runbook/i.test(doc.title) : doc.kind === "Document")) || [];
  return <><PageHeading eyebrow="COMPANY KNOWLEDGE" title="The right knowledge, in context." description="Find the runbook, ticket, or decision connected to the work in front of you." />
    <SearchForm label="Search documents and tickets" placeholder="Search knowledge or enter a service / incident ID…" input={input} setInput={setInput} submit={() => { if (input.trim()) setQuery(input.trim()); }} button="Search knowledge" />
    <div className="document-toolbar"><div className="segmented-control" aria-label="Knowledge type">{["All knowledge", "Runbooks", "Documents", "Tickets"].map(value => <button key={value} aria-pressed={filter === value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{value}</button>)}</div>
      {result.data && <button className="text-button" onClick={() => { setLatestEvidence(result.data!.evidence); navigate("graph"); }}><Network size={13} />Explore relationships<ArrowUpRight size={12} /></button>}</div>
    <div className="results-heading"><h2>Knowledge results<span className="count-badge">{result.loading ? "—" : documents.length}</span></h2><span>{result.loading ? "Searching connected records…" : `Results for “${query}”`}</span></div>
    {result.loading ? <Loading label="Searching documents and connected evidence…" /> : result.error ? <ErrorNotice message={result.error} /> : documents.length ? <div className="documents-grid">{documents.map(document => <button className="panel document-card" key={document.id} onClick={() => inspect(document)}><div className="document-card-header"><span className="document-icon"><KindIcon kind={document.kind} size={21} /></span><KindBadge kind={document.kind} /><ArrowUpRight size={15} /></div><h3>{document.title}</h3><p>{document.body || "Open the source record to inspect its details."}</p><div className="document-meta"><code>{shortId(document.id)}</code><span>{date(document.occurred_at)}</span></div></button>)}</div> : <Empty title="No matching knowledge">Try fewer search terms or an exact service ID. All search terms must match.</Empty>}
  </>;
}

export function GraphExplorer() {
  const { latestEvidence, investigation, selectedId, revision, inspect } = useWorkspace();
  const [mode, setMode] = useState("context");
  const [root, setRoot] = useState(selectedId || "demo:inc-checkout");
  const [hops, setHops] = useState(2);
  const [path, setPath] = useState<string | null>(null);
  const explored = useResource<Evidence>(path, revision);
  const evidence = mode === "context" ? latestEvidence.nodes.length ? latestEvidence : investigation.data?.evidence || emptyEvidence : explored.data || emptyEvidence;
  return <><PageHeading eyebrow="FOLLOW THE CONNECTIONS" title="See how the pieces fit together." description="Inspect real relationships, highlight a path, and open the source behind any node." />
    <div className="graph-explorer-toolbar"><div className="segmented-control"><button className={mode === "context" ? "active" : ""} aria-pressed={mode === "context"} onClick={() => setMode("context")}><Network size={13} />Investigation context</button><button className={mode === "explore" ? "active" : ""} aria-pressed={mode === "explore"} onClick={() => setMode("explore")}><Search size={13} />Explore a source</button></div><span className="muted">Up to 3 hops · 100 records per exploration</span></div>
    {mode === "explore" && <form className="graph-search" onSubmit={e => { e.preventDefault(); if (root.trim()) setPath(`/graph/neighborhood?node_id=${encodeURIComponent(root.trim())}&hops=${hops}`); }}><label><span>Starting source ID</span><input aria-label="Starting source ID" value={root} onChange={e => setRoot(e.target.value)} required maxLength={200} placeholder="company:service-name" /></label><label><span>Relationship depth</span><select value={hops} onChange={e => setHops(Number(e.target.value))} aria-label="Relationship depth">{[1, 2, 3].map(n => <option value={n} key={n}>{n} {n === 1 ? "hop" : "hops"}</option>)}</select></label><button className="button primary" type="submit">Explore graph<ArrowRight size={14} /></button></form>}
    {(mode === "explore" ? explored.loading : investigation.loading && !latestEvidence.nodes.length) ? <Loading label="Retrieving connected sources…" /> : mode === "explore" && explored.error ? <ErrorNotice message={explored.error} /> : <EvidenceGraph evidence={evidence} onInspect={inspect} title={mode === "context" ? "Retrieved evidence" : "Source neighborhood"} description={mode === "context" ? "Context from your latest answer or investigation." : "Additional exploration, separate from any answer’s cited evidence."} />}
    <div className="scoring-note"><Info size={18} /><div><strong>The graph shows what is recorded.</strong><p>Arrows preserve relationship direction. Additional context is separate from the paths cited in an AI answer. Select a path to highlight its source records.</p></div></div>
  </>;
}

export function Sources() {
  const { imported, health } = useWorkspace();
  const [format, setFormat] = useState<"json" | "csv">("json");
  const [bundle, setBundle] = useState<File | null>(null);
  const [nodes, setNodes] = useState<File | null>(null);
  const [edges, setEdges] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [contract, setContract] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(""); setResult(null);
    const files = format === "json" ? [bundle] : [nodes, edges];
    if (!files.some(Boolean)) { setError("Choose a file before importing."); return; }
    if (files.reduce((total, file) => total + (file?.size || 0), 0) > 8 * 1024 * 1024) { setError("The combined upload exceeds the 8 MiB limit."); return; }
    const body = new FormData();
    if (format === "json" && bundle) body.append("bundle_file", bundle);
    if (format === "csv") { if (nodes) body.append("nodes_file", nodes); if (edges) body.append("edges_file", edges); }
    setPending(true);
    try {
      const data = await api<ImportResult>("/ingest", { method: "POST", body });
      setResult(data); setBundle(null); setNodes(null); setEdges(null); form.current?.reset(); imported();
    } catch (problem) {
      if (problem instanceof ApiError && problem.details && typeof problem.details === "object" && "rejected" in problem.details) setResult(problem.details as ImportResult);
      setError(problem instanceof Error ? problem.message : "The import could not be completed.");
    } finally { setPending(false); }
  };
  return <><PageHeading eyebrow="BUILD YOUR COMPANY BRAIN" title="Keep your knowledge connected." description="Add source records and relationships. Stable IDs keep repeat imports free of duplicates." action={<button className="button secondary" onClick={() => setContract(true)}><FileJson size={14} />View data format<ArrowUpRight size={13} /></button>} />
    <div className="sources-grid"><section className="panel import-panel"><div className="panel-heading"><div><h2><Upload size={16} />Import company knowledge</h2><p>Validated source records, added directly to your graph.</p></div><span className="subtle-tag">CSV / JSON</span></div>
      <form onSubmit={submit} ref={form}><div className="import-format segmented-control"><button type="button" className={format === "json" ? "active" : ""} aria-pressed={format === "json"} onClick={() => setFormat("json")}><FileJson size={14} />JSON bundle</button><button type="button" className={format === "csv" ? "active" : ""} aria-pressed={format === "csv"} onClick={() => setFormat("csv")}><FileSpreadsheet size={14} />CSV files</button></div>
        {format === "json" ? <FileDrop id="bundle-upload" label="JSON bundle" accept=".json,application/json" file={bundle} onFile={setBundle} /> : <div className="csv-drop-grid"><FileDrop id="nodes-upload" label="Nodes CSV" accept=".csv,text/csv" file={nodes} onFile={setNodes} /><FileDrop id="edges-upload" label="Edges CSV" accept=".csv,text/csv" file={edges} onFile={setEdges} /></div>}
        <div className="import-details"><span><ShieldCheck size={13} />Validated before writes</span><span><Check size={13} />Safe to import again</span><span>8 MiB maximum</span></div>
        {error && <ErrorNotice message={error} />}
        <div className="import-action"><span>Existing records update only the fields you supply.</span><button className="button primary" type="submit" disabled={pending}><Upload size={14} />{pending ? "Importing…" : "Validate & import"}</button></div>
      </form>
      {result && <div className="import-result" role="status"><h3>{result.rejected ? "Import rejected — no changes written" : "Knowledge is up to date"}{!result.rejected && <CheckCircle2 size={17} />}</h3><div className="import-counts">{(["created", "updated", "unchanged", "rejected"] as const).map(key => <div key={key}><strong>{result[key]}</strong><span>{key}</span></div>)}</div></div>}
    </section><aside className="source-sidebar"><section className="panel graph-storage"><div className="storage-icon"><Database size={24} /></div><h3>Your knowledge graph</h3><p>Company records connected in FalkorDB.</p><div className="storage-counts"><div><strong>{health.data?.nodes ?? "—"}</strong><span>records</span></div><div><strong>{health.data?.edges ?? "—"}</strong><span>relationships</span></div></div><div className="storage-footer"><span className={`connection-dot ${health.data ? "connected" : "disconnected"}`} />{health.data ? "Connected to FalkorDB" : "Service unavailable"}</div></section>
      <section className="panel sample-panel"><div className="panel-heading"><h2><FileText size={15} />Try the demo data</h2></div><p>Download an example or add the checkout resolution to see knowledge change.</p>{[{ file: "demo.json", title: "Company knowledge bundle", note: "113 records · JSON" }, { file: "resolution_update.json", title: "Checkout resolution update", note: "Update an existing investigation" }, { file: "nodes.csv", title: "Node records", note: "CSV format" }, { file: "edges.csv", title: "Relationships", note: "CSV format" }].map(sample => <a href={`/samples/${sample.file}`} download className="sample-link" key={sample.file}><span><strong>{sample.title}</strong><span>{sample.note}</span></span><Download size={14} /></a>)}</section></aside></div>
    {contract && <Modal title="Knowledge import format" onClose={() => setContract(false)} wide><p className="helper-text">New nodes need a source-qualified ID, kind, title, and source reference. Incidents and deployments also need a timezone-aware occurred_at timestamp.</p><pre className="code-block">{JSON.stringify({ nodes: [{ id: "company:checkout", kind: "Service", title: "Checkout API", source_ref: "https://example.com/services/checkout" }], edges: [{ source: "company:checkout", kind: "DEPENDS_ON", target: "company:payments" }] }, null, 2)}</pre><p className="helper-text">Both relationship endpoints must exist in the graph or the upload. Omitted fields preserve their existing values. For CSV, use the same field names as column headers.</p><a className="button secondary" href="https://github.com/krshn0x/KnowGraph-AI-Standalone#ingestion-contract" target="_blank" rel="noreferrer">Full data contract<ArrowUpRight size={13} /></a></Modal>}
  </>;
}

function FileDrop({ id, label, accept, file, onFile }: { id: string; label: string; accept: string; file: File | null; onFile: (file: File | null) => void }) {
  return <label className={`file-drop ${file ? "has-file" : ""}`} htmlFor={id} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); onFile(e.dataTransfer.files[0] || null); }}>
    <input className="file-input" type="file" id={id} aria-label={label} accept={accept} onChange={e => onFile(e.target.files?.[0] || null)} />
    <span className="upload-icon">{file ? <FileText size={23} /> : <Upload size={23} />}</span><strong>{file ? file.name : `Drop your ${label.toLowerCase()} here`}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KiB · choose a different file` : <>or <span className="accent">browse files</span> to upload</>}</span><small>{label} · up to 8 MiB combined</small>
  </label>;
}

function SearchForm({ label, placeholder, input, setInput, submit, button }: {
  label: string; placeholder: string; input: string; setInput: (value: string) => void; submit: () => void; button: string;
}) {
  return <form className="search-form" onSubmit={e => { e.preventDefault(); submit(); }}><div><Search size={17} /><input aria-label={label} value={input} onChange={e => setInput(e.target.value)} placeholder={placeholder} required maxLength={500} /></div><button className="button primary" type="submit">{button}<ArrowRight size={14} /></button></form>;
}
