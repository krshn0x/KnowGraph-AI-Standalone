"use client";

import { useEffect, useRef } from "react";
import { Activity, Box, Check, ExternalLink, FileText, GitCommitHorizontal, GitPullRequest, LoaderCircle, Network, Ticket, Users, X } from "lucide-react";
import type { Entity, Kind } from "@/lib/types";
import { date, shortId } from "@/lib/api";

export const kindMeta: Record<Kind, { icon: typeof Activity; color: string; label: string }> = {
  Person: { icon: Users, color: "#b3b3b3", label: "Person" },
  Service: { icon: Box, color: "#b3b3b3", label: "Service" },
  PullRequest: { icon: GitPullRequest, color: "#b3b3b3", label: "Pull request" },
  Commit: { icon: GitCommitHorizontal, color: "#b3b3b3", label: "Commit" },
  Incident: { icon: Activity, color: "#b3b3b3", label: "Incident" },
  Ticket: { icon: Ticket, color: "#b3b3b3", label: "Ticket" },
  Document: { icon: FileText, color: "#b3b3b3", label: "Document" },
  Deployment: { icon: Network, color: "#b3b3b3", label: "Deployment" },
};

export function KindIcon({ kind, size = 16 }: { kind: Kind; size?: number }) {
  const { icon: Icon, color } = kindMeta[kind];
  return <Icon size={size} style={{ color }} strokeWidth={1.6} aria-hidden="true" />;
}

export function KindBadge({ kind }: { kind: Kind }) {
  return <span className="kind-badge"><KindIcon kind={kind} size={12} />{kindMeta[kind].label}</span>;
}

export function Status({ value }: { value: string }) {
  const resolved = value === "resolved";
  return <span className={`status-pill ${resolved ? "resolved" : "active"}`}>
    {resolved ? <Check size={11} /> : <span className="status-dot" />}
    {resolved ? "Resolved" : value === "investigating" ? "Investigating" : value || "Recorded"}
  </span>;
}

export function Loading({ label = "Following the evidence…" }: { label?: string }) {
  return <div className="loading-state" role="status"><LoaderCircle size={20} className="spin" /><span>{label}</span></div>;
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-notice" role="alert"><Activity size={16} /><span>{message}</span>
    {onRetry && <button onClick={onRetry}>Retry</button>}</div>;
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><Network size={24} /></div>
    <h3>{title}</h3><p>{children}</p></div>;
}

export function Modal({ title, onClose, children, wide = false }: {
  title: string; onClose: () => void; children: React.ReactNode; wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = before; dialog?.close(); };
  }, []);
  return <dialog className={`modal ${wide ? "wide" : ""}`} ref={ref} aria-label={title}
    onCancel={event => { event.preventDefault(); onClose(); }}
    onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="modal-header"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={18} /></button></div>
    <div className="modal-content">{children}</div>
  </dialog>;
}

export function SourceModal({ entity, onClose }: { entity: Entity; onClose: () => void }) {
  return <Modal title="Source record" onClose={onClose}>
    <div className="source-heading"><span className="large-kind-icon"><KindIcon kind={entity.kind} size={23} /></span><KindBadge kind={entity.kind} /></div>
    <h2 className="source-title">{entity.title}</h2>
    <p className="mono muted source-id">{entity.id}</p>
    <div className="source-meta"><div><span>Recorded</span><strong>{date(entity.occurred_at, { year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })}{entity.occurred_at ? " UTC" : ""}</strong></div>
      {entity.status && <div><span>Status</span><Status value={entity.status} /></div>}
      {entity.environment && <div><span>Environment</span><strong>{entity.environment}</strong></div>}</div>
    <div className="source-body">{entity.body || "No source body has been recorded."}</div>
    <div className="source-reference"><span className="eyebrow">SOURCE REFERENCE</span><code>{entity.source_ref || "Not recorded"}</code>
      {/^https?:\/\//.test(entity.source_ref) && <a className="button secondary" href={entity.source_ref} target="_blank" rel="noopener noreferrer">Open original<ExternalLink size={14} /></a>}</div>
  </Modal>;
}

export function SourceRow({ entity, onInspect, trailing }: { entity: Entity; onInspect: (entity: Entity) => void; trailing?: React.ReactNode }) {
  return <button className="source-row" onClick={() => onInspect(entity)}>
    <span className="record-icon"><KindIcon kind={entity.kind} /></span><span className="source-row-content"><strong>{entity.title}</strong><span className="mono">{shortId(entity.id)}</span></span>
    {trailing || <KindBadge kind={entity.kind} />}
  </button>;
}
