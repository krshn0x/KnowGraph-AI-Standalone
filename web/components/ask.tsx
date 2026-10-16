"use client";

import { useRef, useState } from "react";
import { Activity, ArrowRight, ArrowUp, ArrowUpRight, CheckCheck, FileText, LoaderCircle, Network, Plus, ShieldCheck, Users } from "lucide-react";
import type { Answer, Evidence } from "@/lib/types";
import { api, emptyEvidence } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { EvidenceGraph } from "./evidence-graph";
import { ErrorNotice, KindIcon, Modal, SourceRow } from "./ui";
import { PageHeading } from "./investigations";

export function Ask() {
  const { health, investigation, selectedId, chat, setChat, askPending, setAskPending, chatError, setChatError, inspect, setLatestEvidence, navigate } = useWorkspace();
  const [input, setInput] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [citation, setCitation] = useState<Evidence | null>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const lastAnswer = chat.at(-1)?.answer;
  const sources = lastAnswer ? lastAnswer.sources : investigation.data?.evidence.nodes.filter(n => ["Document", "Incident", "PullRequest"].includes(n.kind)).slice(0, 6) || [];
  const examples = [
    { icon: Activity, title: "Investigate a failure", description: "Trace what changed before an incident.", question: `Investigate ${selectedId || "demo:inc-checkout"}. What changed, who can help, and which runbook is relevant?` },
    { icon: Users, title: "Find the right expert", description: "Connect a service to relevant experience.", question: "Who has experience resolving checkout incidents? Explain the evidence behind each recommendation." },
    { icon: Network, title: "Follow a dependency", description: "Look beyond the affected service.", question: "Investigate demo:inc-payments and trace deployments in its dependencies." },
  ];
  const send = async (value: string) => {
    const question = value.trim();
    if (!question || askPending) return;
    setInput(""); setPendingQuestion(question); setAskPending(true); setChatError("");
    const history = chat.flatMap(entry => [{ role: "user", content: entry.question }, { role: "assistant", content: entry.answer.summary.slice(0, 4000) }]).slice(-12);
    try {
      const answer = await api<Answer>("/ask", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question, history }) });
      setChat(entries => [...entries, { id: crypto.randomUUID(), question, answer }]);
      setLatestEvidence(answer.evidence.nodes.length ? answer.evidence : answer.retrieved_evidence || emptyEvidence);
    } catch (problem) {
      setChatError(problem instanceof Error ? problem.message : "The investigation could not be completed.");
      setInput(question);
    } finally { setAskPending(false); setPendingQuestion(""); }
  };
  return <><PageHeading eyebrow="YOUR COMPANY BRAIN" title="Ask a question. Follow the evidence." description="Reason across incidents, deployments, people, and company knowledge." action={<button className="button secondary" disabled={askPending || !chat.length} onClick={() => { setChat([]); setChatError(""); textarea.current?.focus(); }}><Plus size={14} />New conversation</button>} />
    <div className="ask-grid"><div className="conversation-panel">
      <div className="conversation-header"><span><span className="ai-mark">◈</span>KnowGraph assistant</span><span className="model-tag"><span className={`connection-dot ${health.data?.ai_configured ? "connected" : "pending"}`} />{health.data?.model || "AI model"}</span></div>
      <div className="conversation-messages" aria-live="polite">
        {!chat.length && !askPending && <div className="chat-welcome"><span className="welcome-mark">◈</span><span className="eyebrow">KNOWLEDGE, WITH CONTEXT</span><h2>What would you like to understand?</h2><p>Start with an incident, a service, or a question.<br />KnowGraph connects the evidence behind the answer.</p><div className="chat-examples">{examples.map(example => <button key={example.title} onClick={() => void send(example.question)}><example.icon size={17} /><span><strong>{example.title}</strong><span>{example.description}</span></span><ArrowUpRight size={14} /></button>)}</div></div>}
        {chat.map(entry => <div className="chat-turn" key={entry.id}><div className="user-message"><span className="message-avatar user">Y</span><div><span className="message-author">You</span><p>{entry.question}</p></div></div><div className="assistant-message"><span className="message-avatar ai">◈</span><div className="assistant-content"><span className="message-author">KnowGraph<span>Evidence-backed investigation</span></span><p className="answer-summary">{entry.answer.summary}</p>{entry.answer.warnings.map(warning => <div className="answer-warning" key={warning}><Activity size={14} /><span>{warning}</span></div>)}
          {entry.answer.claims.map((claim, index) => <div className={`claim ${claim.certainty}`} key={index}><span className="claim-kind">{claim.certainty === "observed" ? <CheckCheck size={12} /> : <Activity size={12} />}{claim.certainty === "observed" ? "Finding" : "Hypothesis"}</span><p>{claim.text}</p><div className="claim-citations">{claim.evidence_ids.map(id => {
            const evidence = entry.answer.retrieved_evidence || entry.answer.evidence;
            const source = evidence.nodes.find(n => n.id === id);
            const path = evidence.paths.find(p => p.id === id);
            return <button key={id} className="citation-chip" onClick={() => source ? inspect(source) : setCitation(evidenceForCitation(evidence, id))}>{source ? <KindIcon kind={source.kind} size={11} /> : <Network size={11} />}{source?.title || (path ? `Evidence path · ${path.node_ids.length} sources` : "Relationship evidence")}<ArrowUpRight size={10} /></button>;
          })}</div></div>)}
          {entry.answer.experts.length > 0 && <div className="answer-experts"><span className="eyebrow">PEOPLE WHO CAN HELP</span>{entry.answer.experts.map(expert => <button key={expert.person.id} onClick={() => inspect(expert.person)}><Users size={13} />{expert.person.title}<span>{expert.score} points</span><ArrowUpRight size={11} /></button>)}</div>}
          <div className="answer-footer"><ShieldCheck size={12} /><span>{entry.answer.sources.length} source records</span>{entry.answer.tool_calls.length > 0 && <><span>·</span><span>{entry.answer.tool_calls.length} graph tools used</span></>}</div>
        </div></div></div>)}
        {askPending && <div className="chat-turn">{pendingQuestion && <div className="user-message"><span className="message-avatar user">Y</span><div><span className="message-author">You</span><p>{pendingQuestion}</p></div></div>}<div className="assistant-message"><span className="message-avatar ai">◈</span><div className="thinking" role="status"><LoaderCircle className="spin" size={15} />Following connected evidence…</div></div></div>}
        {chatError && <ErrorNotice message={chatError} />}
      </div>
      <form className="chat-composer" onSubmit={e => { e.preventDefault(); void send(input); }}><div className="composer-input"><textarea ref={textarea} aria-label="Ask KnowGraph" placeholder="Ask about an incident, a service, or the people who know…" value={input} maxLength={4000} onChange={e => setInput(e.target.value)} disabled={askPending} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(input); } }} /><button type="submit" className="send-button" aria-label="Send question" disabled={!input.trim() || askPending}>{askPending ? <LoaderCircle size={18} className="spin" /> : <ArrowUp size={18} />}</button></div><div className="composer-footer"><span><ShieldCheck size={11} />Answers grounded in your knowledge graph</span><span>Enter to send<span className="key-separator">·</span>Shift + Enter for a new line</span></div></form>
    </div><aside className="ask-aside"><section className="panel answer-sources"><div className="panel-heading"><div><h2><FileText size={15} />{lastAnswer ? "Answer sources" : "Workspace context"}<span className="count-badge">{sources.length}</span></h2><p>{lastAnswer ? "Records cited or returned by this answer." : "A few starting points in the company graph."}</p></div></div>{sources.length ? sources.map(entity => <SourceRow key={entity.id} entity={entity} onInspect={inspect} trailing={<ArrowUpRight size={13} />} />) : <div className="panel-empty">Source records will appear here when evidence is retrieved.</div>}</section>
      {lastAnswer?.evidence.nodes.length ? <button className="graph-callout" onClick={() => { setLatestEvidence(lastAnswer.evidence); navigate("graph"); }}><span className="graph-callout-icon"><Network size={21} /></span><strong>See the connections</strong><p>Open the actual graph evidence behind the latest answer.</p><span>Explore evidence<ArrowRight size={13} /></span></button> : <div className="grounding-card"><ShieldCheck size={22} /><h3>Evidence comes first.</h3><p>Findings cite retrieved source records. Tentative explanations are labeled as hypotheses.</p><button className="text-button" onClick={() => navigate("investigations")}>Explore an incident<ArrowRight size={13} /></button></div>}
      {health.data && !health.data.ai_configured && <div className="ai-configuration-note"><InfoMark /><strong>AI answers aren’t configured</strong><p>The structured investigation, experts, documents, and graph views are available now.</p><button className="text-button" onClick={() => navigate("investigations")}>Open investigations<ArrowRight size={12} /></button></div>}
    </aside></div>
    {citation && <Modal title="Supporting graph evidence" onClose={() => setCitation(null)} wide><EvidenceGraph evidence={citation} onInspect={inspect} title="Cited evidence" description="Only the source records and relationships for this citation." /></Modal>}
  </>;
}

function InfoMark() { return <span className="info-mark">i</span>; }

function evidenceForCitation(evidence: Evidence, id: string): Evidence {
  const paths = evidence.paths.filter(p => p.id === id || p.edge_ids.includes(id));
  const edgeIds = new Set([id, ...paths.flatMap(p => p.edge_ids)]);
  const edges = evidence.edges.filter(e => edgeIds.has(e.id));
  const nodeIds = new Set([id, ...paths.flatMap(p => p.node_ids), ...edges.flatMap(e => [e.source, e.target])]);
  return { nodes: evidence.nodes.filter(n => nodeIds.has(n.id)), edges, paths, truncated: evidence.truncated };
}
