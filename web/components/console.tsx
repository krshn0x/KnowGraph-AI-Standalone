"use client";

import { useDeferredValue, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, ArrowUpRight, BookOpen, Check, ChevronRight, CircleDot, Command, Database, ExternalLink, FileText, LayoutDashboard, Menu, MessageSquare, Network, RefreshCw, Search, Users, X } from "lucide-react";
import type { Entity, Evidence, Health, Investigation, ChatEntry, View } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { emptyEvidence } from "@/lib/api";
import { WorkspaceContext } from "@/lib/workspace";
import { Empty, ErrorNotice, Loading, Modal, SourceModal, SourceRow } from "./ui";
import { Overview, Investigations } from "./investigations";
import { Experts, Documents, GraphExplorer, Sources } from "./knowledge";
import { Ask } from "./ask";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, section: "WORKSPACE" },
  { id: "investigations", label: "Investigations", icon: Activity },
  { id: "ask", label: "Ask KnowGraph", icon: MessageSquare },
  { id: "experts", label: "Experts", icon: Users, section: "KNOWLEDGE" },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "graph", label: "Evidence graph", icon: Network },
  { id: "sources", label: "Data sources", icon: Database },
] as const;

export function Console({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const view = (pathname.split("/")[1] || "overview") as View;
  const [revision, setRevision] = useState(0);
  const [incidentId, setIncidentId] = useState("");
  const [lookback, setLookback] = useState(24);
  const [mobile, setMobile] = useState(false);
  const [search, setSearch] = useState(false);
  const [system, setSystem] = useState(false);
  const [source, setSource] = useState<Entity | null>(null);
  const [latestEvidence, setLatestEvidence] = useState<Evidence>(emptyEvidence);
  const [toast, setToast] = useState("");
  const [chat, setChat] = useState<ChatEntry[]>([]);
  const [askPending, setAskPending] = useState(false);
  const [chatError, setChatError] = useState("");
  const health = useResource<Health>("/health", revision);
  const incidents = useResource<Entity[]>("/entities?kind=Incident", revision);
  const services = useResource<Entity[]>("/entities?kind=Service", revision);
  const selectedId = incidentId || incidents.data?.find(i => i.id === "demo:inc-checkout")?.id || incidents.data?.[0]?.id || "";
  const investigation = useResource<Investigation>(selectedId ? `/incidents/${encodeURIComponent(selectedId)}/investigation?lookback_hours=${lookback}` : null, revision);
  const refresh = () => setRevision(n => n + 1);
  const navigate = (next: View) => { router.push(next === "overview" ? "/" : `/${next}`); setMobile(false); };
  const selectIncident = (id: string) => { setIncidentId(id); navigate("investigations"); };
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setSearch(open => !open);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  const title = navigation.find(item => item.id === view)?.label || "Overview";
  const activeCount = incidents.data?.filter(i => i.status !== "resolved").length || 0;
  return <WorkspaceContext.Provider value={{ health, incidents, services, investigation, selectedId, selectIncident, lookback, setLookback,
    revision, refresh, imported: () => { refresh(); setLatestEvidence(emptyEvidence); setToast("Knowledge updated. New queries will use the latest evidence."); },
    inspect: setSource, navigate, latestEvidence, setLatestEvidence, notify: setToast,
    chat, setChat, askPending, setAskPending, chatError, setChatError }}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    {mobile && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMobile(false)} />}
    <aside className={`sidebar ${mobile ? "mobile-open" : ""}`} aria-label="Main navigation">
      <div className="brand-row"><Link href="/" className="brand" onClick={() => setMobile(false)}><BrandMark /><span>KnowGraph<span className="brand-ai">AI</span></span></Link><button className="mobile-close icon-button" onClick={() => setMobile(false)} aria-label="Close menu"><X size={16} /></button></div>
      <div className="workspace-switch"><span className="workspace-avatar">N</span><div><strong>Northstar Labs</strong><span>Engineering workspace</span></div><span className="workspace-dot" /></div>
      <button className="sidebar-search" onClick={() => setSearch(true)}><Search size={15} /><span>Search knowledge</span><kbd>⌘ K</kbd></button>
      <nav>{navigation.map(item => <div key={item.id}>
        {"section" in item && <div className="nav-section">{item.section}</div>}
        <Link href={item.id === "overview" ? "/" : `/${item.id}`} className={`nav-link ${view === item.id ? "selected" : ""}`} aria-current={view === item.id ? "page" : undefined} onClick={() => setMobile(false)}>
          <item.icon size={17} strokeWidth={1.7} /><span>{item.label}</span>
          {item.id === "investigations" && incidents.data && <span className="nav-count">{activeCount}</span>}
          {item.id === "ask" && <span className="new-label">AI</span>}
        </Link></div>)}</nav>
      <div className="sidebar-bottom"><div className="graph-status"><span className={`connection-dot ${health.data ? "connected" : health.loading ? "pending" : "disconnected"}`} /><span>{health.data ? "FalkorDB connected" : health.loading ? "Connecting to graph" : "Connection unavailable"}</span><button className="icon-button" aria-label="Refresh workspace" onClick={refresh}><RefreshCw size={12} /></button></div>
        <div className="sidebar-note">Northstar Labs is a fictional demo workspace.</div><a href="https://github.com/krshn0x/KnowGraph-AI#readme" className="help-link" target="_blank" rel="noreferrer"><BookOpen size={14} />Documentation<ArrowUpRight size={12} /></a></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobile(true)}><Menu size={19} /></button><span>Workspace</span><ChevronRight size={12} /><strong>{title}</strong></div>
      <div className="topbar-actions"><span className="workspace-mode">DEMO WORKSPACE</span><span className="topbar-divider" /><button className="system-button" onClick={() => setSystem(true)}><CircleDot size={14} /><span>System status</span></button><span className="profile-avatar" title="Northstar Labs demo workspace">N</span></div></header>
      <main id="main-content" className={`page-content view-${view}`}>
        {children}
        {health.error && <ErrorNotice message={health.error} onRetry={refresh} />}
        {view === "overview" && <Overview />}
        {view === "investigations" && <Investigations />}
        {view === "ask" && <Ask />}
        {view === "experts" && <Experts />}
        {view === "documents" && <Documents />}
        {view === "graph" && <GraphExplorer />}
        {view === "sources" && <Sources />}
      </main><footer className="app-footer"><span><span className="tiny-logo">◈</span>KnowGraph AI</span><span>Connected knowledge. Verifiable answers.</span></footer>
    </div>
    {search && <SearchPalette onClose={() => setSearch(false)} onInspect={entity => { setSearch(false); setSource(entity); }} />}
    {source && <SourceModal key={source.id} entity={source} onClose={() => setSource(null)} />}
    {system && <Modal title="System status" onClose={() => setSystem(false)}><div className="system-intro"><span className={`connection-dot ${health.data ? "connected" : "disconnected"}`} /><h3>{health.data ? "Knowledge service is connected" : "Knowledge service is unavailable"}</h3></div>
      <div className="system-row"><span>Graph database</span><strong>FalkorDB</strong></div><div className="system-row"><span>Knowledge records</span><strong>{health.data?.nodes ?? "—"}</strong></div><div className="system-row"><span>Relationships</span><strong>{health.data?.edges ?? "—"}</strong></div><div className="system-row"><span>AI model</span><code>{health.data?.model || "Unavailable"}</code></div><div className="system-row"><span>AI configuration</span><strong>{health.data?.ai_configured ? "Key configured" : "Key not configured"}</strong></div>
      <p className="helper-text">{health.data?.ai_configured ? "Model access is checked when you ask a question." : "Add OPENAI_API_KEY to the backend environment to enable AI answers. All structured graph tools work without it."}</p>
      <button className="button secondary full-width" onClick={() => { refresh(); setToast("Workspace status refreshed."); }}><RefreshCw size={14} />Refresh status</button></Modal>}
    {toast && <div className="toast" role="status"><Check size={16} />{toast}</div>}
  </WorkspaceContext.Provider>;
}

function BrandMark() {
  return <svg className="brand-mark" width="27" height="27" viewBox="0 0 40 40" fill="none" aria-hidden="true"><rect width="40" height="40" rx="10" fill="#b4ec83" /><path d="m12 12 16 8-16 8V12Z" stroke="#24341a" strokeWidth="2" /><circle cx="12" cy="12" r="3" fill="#24341a" /><circle cx="28" cy="20" r="3" fill="#24341a" /><circle cx="12" cy="28" r="3" fill="#24341a" /></svg>;
}

function SearchPalette({ onClose, onInspect }: { onClose: () => void; onInspect: (entity: Entity) => void }) {
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());
  const result = useResource<Entity[]>(deferred.length >= 2 ? `/entities?q=${encodeURIComponent(deferred)}` : null);
  return <Modal title="Search company knowledge" onClose={onClose} wide>
    <div className="command-input"><Search size={20} /><input autoFocus aria-label="Search company knowledge" placeholder="Search incidents, people, documents, or a source ID…" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && result.data?.[0]) onInspect(result.data[0]); }} /><kbd>ESC</kbd></div>
    <div className="command-results">{result.loading ? <Loading label="Searching knowledge…" /> : result.error ? <ErrorNotice message={result.error} /> : result.data?.length ? result.data.map(entity => <SourceRow entity={entity} onInspect={onInspect} key={entity.id} />) : <Empty title={deferred.length < 2 ? "Find the right starting point" : "No matching source records"}>{deferred.length < 2 ? "Search across the connected company graph." : "Try a service name, a shorter phrase, or an exact source ID."}</Empty>}</div>
    <div className="command-footer"><span><Command size={12} />K to open anywhere</span><span><ExternalLink size={12} />Select a result to inspect its source</span></div>
  </Modal>;
}
