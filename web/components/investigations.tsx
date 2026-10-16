"use client";

import { Activity, ArrowRight, ArrowUpRight, Box, Clock3, GitPullRequest, Link2, MessageSquare, Network, ShieldCheck } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import { date, emptyEvidence, shortId } from "@/lib/api";
import { EvidenceGraph } from "./evidence-graph";
import { Empty, ErrorNotice, KindIcon, Loading, SourceRow, Status } from "./ui";

export function PageHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h1>{title}</h1><p>{description}</p></div>{action}</div>;
}

export function Overview() {
  const { health, incidents, services, investigation, inspect, navigate, selectIncident } = useWorkspace();
  const active = incidents.data?.filter(n => n.status !== "resolved").length;
  const stats = [
    { title: "Knowledge records", value: health.data?.nodes, subtitle: "Across 8 connected record types", icon: Box },
    { title: "Relationships", value: health.data?.edges, subtitle: "Connections you can trace", icon: Network },
    { title: "Services mapped", value: services.data?.length, subtitle: "With changes, people, and context", icon: Link2 },
    { title: "Open incidents", value: active, subtitle: `${incidents.data?.length ?? "—"} incidents in company knowledge`, icon: Activity },
  ];
  const recent = [...(incidents.data || [])].sort((a, b) => (b.occurred_at || "").localeCompare(a.occurred_at || "")).slice(0, 5);
  return <>
    <PageHeading eyebrow="ENGINEERING INTELLIGENCE" title="Your company, connected." description="Follow the context behind incidents, changes, and the people who know." action={<button className="button primary" onClick={() => navigate("ask")}><MessageSquare size={15} />Ask KnowGraph<ArrowUpRight size={15} /></button>} />
    <div className="stats-grid">{stats.map(stat => <div className="stat-card" key={stat.title}><div className="stat-label">{stat.title}<stat.icon size={16} /></div><div className="stat-value">{stat.value ?? <span className="skeleton-value">—</span>}</div><div className="stat-subtitle">{stat.subtitle}</div></div>)}</div>
    <div className="section-caption"><span><span className="live-dot" />THE CONNECTED WORKSPACE</span><span>Source-backed context, one relationship at a time</span></div>
    <div className="overview-grid"><div>{investigation.loading ? <div className="panel"><Loading label="Building the investigation map…" /></div> : investigation.error ? <ErrorNotice message={investigation.error} /> : <EvidenceGraph compact evidence={investigation.data?.evidence || emptyEvidence} onInspect={inspect} title="Connected evidence" description={investigation.data ? `Context for ${investigation.data.incident.title.toLowerCase()}.` : "Start with an incident to see the connections."} />}</div>
      <section className="panel focus-panel"><div className="panel-heading"><div><h2><Activity size={16} />In focus</h2><p>A starting point for your next investigation.</p></div><span className="square-icon"><ArrowUpRight size={16} /></span></div>
        {investigation.data ? <><div className="focus-content"><Status value={investigation.data.incident.status} /><h3>{investigation.data.incident.title}</h3><p>{investigation.data.incident.body}</p><div className="focus-facts"><span><Clock3 size={13} />{date(investigation.data.incident.occurred_at, { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC</span><span><Box size={13} />{investigation.data.services.length} connected services</span><span><GitPullRequest size={13} />{investigation.data.changes.filter(n => n.kind === "PullRequest").length} related pull requests</span></div><button className="button secondary full-width" onClick={() => navigate("investigations")}>Open investigation<ArrowRight size={14} /></button></div><div className="focus-note"><ShieldCheck size={15} /><span>Connections are supported by graph evidence. Causation requires a recorded resolution.</span></div></> : <Empty title="Your next investigation starts here">Import incident data to connect the first pieces.</Empty>}
      </section></div>
    <section className="panel incident-list"><div className="panel-heading"><div><h2><Activity size={16} />Recent incidents<span className="count-badge">{incidents.data?.length ?? "—"}</span></h2><p>Current investigations and past events, connected to their evidence.</p></div><button className="text-button" onClick={() => navigate("investigations")}>View investigations<ArrowUpRight size={14} /></button></div>
      {incidents.loading ? <Loading /> : incidents.error ? <ErrorNotice message={incidents.error} /> : recent.length ? <div className="table-scroll"><table><thead><tr><th>INCIDENT</th><th>STATUS</th><th>ENVIRONMENT</th><th>RECORDED</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{recent.map(incident => <tr key={incident.id} onClick={() => selectIncident(incident.id)}><td><button className="table-incident" onClick={() => selectIncident(incident.id)}><span className={`incident-glyph ${incident.status === "resolved" ? "closed" : ""}`}><Activity size={14} /></span><span><strong>{incident.title}</strong><code>{shortId(incident.id)}</code></span></button></td><td><Status value={incident.status} /></td><td><span className="environment">{incident.environment || "Not recorded"}</span></td><td className="muted">{date(incident.occurred_at)}</td><td><ArrowUpRight size={15} className="muted" /></td></tr>)}</tbody></table></div> : <Empty title="No incidents recorded">Add your first incident in Data sources.</Empty>}
    </section>
  </>;
}

export function Investigations() {
  const { incidents, investigation, selectedId, selectIncident, lookback, setLookback, inspect, navigate } = useWorkspace();
  const data = investigation.data;
  return <>
    <PageHeading eyebrow="INCIDENT INTELLIGENCE" title="Find the story behind the failure." description="Connect deployments, dependencies, code changes, and past experience." action={<button className="button secondary" onClick={() => navigate("ask")}><MessageSquare size={15} />Ask about this incident<ArrowUpRight size={14} /></button>} />
    <div className="investigation-toolbar"><div className="field-inline"><span><Activity size={14} />Incident</span><select aria-label="Select incident" value={selectedId} onChange={e => selectIncident(e.target.value)}>{!incidents.data?.length && <option value="">No incidents available</option>}{incidents.data?.map(i => <option key={i.id} value={i.id}>{i.title}</option>)}</select></div><div className="field-inline lookback"><span><Clock3 size={14} />Lookback</span><select aria-label="Deployment lookback" value={lookback} onChange={e => setLookback(Number(e.target.value))}>{[6, 12, 24, 48, 72, 168].map(h => <option key={h} value={h}>{h} hours</option>)}</select></div></div>
    {investigation.loading || incidents.loading ? <div className="panel"><Loading label="Tracing deployments and connected changes…" /></div> : investigation.error ? <ErrorNotice message={investigation.error} /> : data ? <>
      <div className="incident-heading"><div className="incident-title"><span className="incident-glyph large"><Activity size={21} /></span><div><div className="incident-title-meta"><code>{shortId(data.incident.id)}</code><Status value={data.incident.status} /><span className="environment">{data.incident.environment || "Environment not recorded"}</span></div><h2>{data.incident.title}</h2></div></div><button className="text-button" onClick={() => inspect(data.incident)}>View source<ArrowUpRight size={14} /></button></div>
      <div className="investigation-grid"><div className="investigation-main"><EvidenceGraph evidence={data.evidence} onInspect={inspect} title="Investigation map" description="Actual relationships retrieved for this incident." />
        <section className="panel change-panel"><div className="panel-heading"><div><h2><GitPullRequest size={16} />Connected changes<span className="count-badge">{data.changes.length}</span></h2><p>Commits included in matching deployments, with their pull requests.</p></div></div>{data.changes.length ? data.changes.map(change => <SourceRow entity={change} onInspect={inspect} key={change.id} />) : <div className="panel-empty">No changes were recorded in deployments matching the selected window.</div>}</section>
      </div><aside className="investigation-aside"><section className="panel summary-panel"><div className="panel-heading"><h2><Activity size={16} />Incident brief</h2></div><div className="brief-body"><p>{data.incident.body}</p><div className="brief-counts"><div><strong>{data.services.length}</strong><span>Services</span></div><div><strong>{data.deployments.length}</strong><span>Deployments</span></div><div><strong>{data.changes.length}</strong><span>Changes</span></div></div><span className="eyebrow">CONNECTED SERVICES</span><div className="service-chips">{data.services.map(s => <button key={s.id} onClick={() => inspect(s)}><KindIcon kind="Service" size={12} />{s.title}<ArrowUpRight size={11} /></button>)}</div></div><div className="evidence-note"><ShieldCheck size={15} /><span>Timing identifies candidates. It does not establish a root cause.</span></div></section>
        <section className="panel timeline-panel"><div className="panel-heading"><h2><Clock3 size={15} />Evidence timeline<span className="count-badge">{data.timeline.length}</span></h2></div><div className="timeline-list">{data.timeline.map((record, index) => <button className="timeline-item" key={record.id} onClick={() => inspect(record)}><span className={`timeline-marker ${record.kind === "Incident" ? "incident" : ""}`}><KindIcon kind={record.kind} size={12} /></span><span><time>{date(record.occurred_at, { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })}</time><strong>{record.title}</strong><span className="timeline-kind">{record.kind === "PullRequest" ? "Pull request" : record.kind}</span></span>{index === 0 && <span className="sr-only">Earliest recorded event</span>}</button>)}</div></section>
      </aside></div>
      {data.warnings.filter(w => !w.startsWith("Deployments preceding")).map(warning => <div className="inline-notice" key={warning}><Activity size={14} />{warning}</div>)}
    </> : <Empty title="No incident to investigate">Import an incident and connect it to a service in Data sources.</Empty>}
  </>;
}
