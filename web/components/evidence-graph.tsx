"use client";

import { useMemo, useState } from "react";
import { graphlib, layout } from "@dagrejs/dagre";
import { Background, BackgroundVariant, Controls, Handle, MarkerType, Position, ReactFlow, type Node, type NodeChange, type NodeProps, type XYPosition } from "@xyflow/react";
import { Download, Maximize2, Network, RotateCcw } from "lucide-react";
import type { Entity, Evidence } from "@/lib/types";
import { kindMeta, KindIcon, Empty } from "./ui";

type RecordNodeType = Node<{ entity: Entity; highlighted: boolean; dimmed: boolean }, "record">;

function RecordNode({ data }: NodeProps<RecordNodeType>) {
  return <div className={`record-node ${data.highlighted ? "highlighted" : ""} ${data.dimmed ? "dimmed" : ""}`}>
    <Handle type="target" position={Position.Top} /><div className="record-node-type"><KindIcon kind={data.entity.kind} size={12} />{kindMeta[data.entity.kind].label}</div>
    <div className="record-node-title" title={data.entity.title}>{data.entity.title}</div>
    <Handle type="source" position={Position.Bottom} />
  </div>;
}

const nodeTypes = { record: RecordNode };

export function EvidenceGraph({ evidence, onInspect, compact = false, title = "Evidence map", description = "Every connection leads back to a source." }: {
  evidence: Evidence; onInspect: (entity: Entity) => void; compact?: boolean; title?: string; description?: string;
}) {
  const [pathId, setPathId] = useState("");
  const [positions, setPositions] = useState<Record<string, XYPosition>>({});
  const [reset, setReset] = useState(0);
  const path = evidence.paths.find(p => p.id === pathId);
  const emphasizedNodes = new Set(path?.node_ids || []);
  const emphasizedEdges = new Set(path?.edge_ids || []);
  const basePositions = useMemo(() => {
    const graph = new graphlib.Graph();
    graph.setGraph({ rankdir: "TB", nodesep: 28, ranksep: 43, marginx: 30, marginy: 24 });
    graph.setDefaultEdgeLabel(() => ({}));
    evidence.nodes.forEach(node => graph.setNode(node.id, { width: 184, height: 62 }));
    const ids = new Set(evidence.nodes.map(n => n.id));
    evidence.edges.forEach(edge => { if (ids.has(edge.source) && ids.has(edge.target)) graph.setEdge(edge.source, edge.target); });
    layout(graph);
    return Object.fromEntries(evidence.nodes.map(n => {
      const point = graph.node(n.id);
      return [n.id, { x: point.x - 92, y: point.y - 31 }];
    }));
  }, [evidence]);
  const nodes: RecordNodeType[] = evidence.nodes.map(entity => ({
    id: entity.id, type: "record", position: positions[entity.id] || basePositions[entity.id],
    width: 184, height: 62, measured: { width: 184, height: 62 },
    data: { entity, highlighted: emphasizedNodes.has(entity.id), dimmed: !!path && !emphasizedNodes.has(entity.id) },
  }));
  const ids = new Set(evidence.nodes.map(n => n.id));
  const edges = evidence.edges.filter(e => ids.has(e.source) && ids.has(e.target)).map(edge => ({
    id: edge.id, source: edge.source, target: edge.target,
    type: "smoothstep", label: edge.kind.replaceAll("_", " ").toLowerCase(),
    markerEnd: { type: MarkerType.ArrowClosed, width: 13, height: 13, color: emphasizedEdges.has(edge.id) ? "#b4ec83" : "#61616e" },
    style: { stroke: emphasizedEdges.has(edge.id) ? "#b4ec83" : "#484850", strokeWidth: emphasizedEdges.has(edge.id) ? 2 : 1, opacity: path && !emphasizedEdges.has(edge.id) ? .2 : 1 },
    labelStyle: { fill: "#a7a7b4", fontSize: 9, fontWeight: 500 },
    labelBgStyle: { fill: "#17171b", fillOpacity: .98 }, labelBgPadding: [5, 3] as [number, number], labelBgBorderRadius: 4,
  }));
  const onNodesChange = (changes: NodeChange<RecordNodeType>[]) => {
    if (!changes.some(change => change.type === "position" && change.position)) return;
    setPositions(current => {
    const next = { ...current };
    for (const change of changes) if (change.type === "position" && change.position) next[change.id] = change.position;
    return next;
    });
  };
  const exportEvidence = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(evidence, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "knowgraph-evidence.json"; link.click(); URL.revokeObjectURL(url);
  };
  return <section className={`panel graph-panel ${compact ? "compact" : ""}`} aria-label={title}>
    <div className="panel-heading"><div><h2><Network size={16} />{title}</h2><p>{description}</p></div>
      <div className="inline-actions"><span className="subtle-tag">{evidence.nodes.length} nodes<span>·</span>{evidence.edges.length} links</span>
        <button className="icon-button" aria-label="Reset graph layout" onClick={() => { setPositions({}); setReset(v => v + 1); }}><RotateCcw size={14} /></button>
        <button className="icon-button" aria-label="Export evidence" onClick={exportEvidence} disabled={!evidence.nodes.length}><Download size={15} /></button></div></div>
    {evidence.nodes.length ? <>
      <div className="graph-canvas" data-testid="evidence-canvas"><ReactFlow key={reset} nodes={nodes} edges={edges} nodeTypes={nodeTypes}
        onNodesChange={onNodesChange} onNodeClick={(_, node) => onInspect(node.data.entity)}
        nodesConnectable={false} edgesFocusable={false} deleteKeyCode={null} minZoom={.15} maxZoom={1.8}
        fitView fitViewOptions={{ padding: .16, maxZoom: 1 }} proOptions={{ hideAttribution: true }}>
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#35353e" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow><div className="graph-hint"><Maximize2 size={11} />Drag to explore · select a node to inspect</div></div>
      <div className="graph-footer"><div className="graph-legend">{[...new Set(evidence.nodes.map(n => n.kind))].map(kind => <span key={kind}><i style={{ background: kindMeta[kind].color }} />{kindMeta[kind].label}</span>)}</div>
        {evidence.paths.length > 0 && <select aria-label="Highlight evidence path" value={path ? pathId : ""} onChange={e => setPathId(e.target.value)}>
          <option value="">All retrieved paths</option>{evidence.paths.map((p, i) => <option value={p.id} key={p.id}>Path {i + 1} · {p.node_ids.length} records</option>)}</select>}</div>
      {evidence.truncated && <div className="graph-truncated">Results are bounded. Narrow your query to inspect more connections.</div>}
    </> : <Empty title="No connected evidence yet">Investigate an incident or explore a source to populate this map.</Empty>}
  </section>;
}
