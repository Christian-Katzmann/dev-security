import {useEffect, useMemo, useRef, useState} from 'react';
import {
  forceCenter,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force';
import {AlertTriangle, Crown, Gem, RefreshCw, ShieldAlert, Target} from 'lucide-react';
import {
  GraphActiveIncident,
  GraphEdge,
  GraphNode,
  GraphPayload,
  ProjectRepo,
  TargetSelection,
} from '../dashboardData';
import NeedsRepoTarget from './NeedsRepoTarget';

// The blast-radius graph view (Honeygraph 2, step 3.1). It renders the asset
// graph the scanner builds — nodes sized by how far a blast from them spreads,
// coloured by reachable consequence, crown jewels marked — and, when a decoy is
// tripped, lights the real blast-radius path from the tripped node. The honest
// boundary holds here: a lit path proves an adversary reached that region and
// took the bait, NOT that any specific finding was exploited (the server hands us
// `active_incident.message`, the single source of that wording, and we show it
// verbatim).
//
// Layout: a force simulation run *once* to a static settle (no animation loop —
// kinder to the laptop, deterministic enough to read), then plain SVG. SVG keeps
// us in full control of the glow filter and the path highlight without pulling in
// a heavy graph framework; see the receipt for the library trade-off.

// Above this many nodes, an all-SVG force graph stops being legible *and* starts
// costing DOM. We render the highest-consequence slice and say so, rather than
// silently dropping the tail or melting the frame.
const MAX_RENDERED_NODES = 240;
const VIEW_W = 960;
const VIEW_H = 600;

type SimNode = SimulationNodeDatum & {data: GraphNode};
type SimLink = SimulationLinkDatum<SimNode> & {data: GraphEdge};

type ConsequenceTone = 'crit' | 'high' | 'warn' | 'low' | 'info';

const toneVar: Record<ConsequenceTone, string> = {
  crit: 'var(--sev-crit)',
  high: 'var(--sev-high)',
  warn: 'var(--sev-warn)',
  low: 'var(--sev-low)',
  info: 'var(--sev-info)',
};

// A node's colour is its *consequence*, not its raw severity: can a blast from
// here reach something labeled precious (crit), and failing that, how much does
// it touch. `blastCeiling` is the graph's own max so the scale is relative to
// what this repo actually contains.
function nodeTone(node: GraphNode, blastCeiling: number): ConsequenceTone {
  if (node.reaches_crown_jewel) return 'crit';
  if (node.blast_radius <= 0) return 'low';
  const share = blastCeiling > 0 ? node.blast_radius / blastCeiling : 0;
  if (share >= 0.66) return 'high';
  if (share >= 0.25) return 'warn';
  return 'info';
}

function nodeRadius(node: GraphNode, blastCeiling: number): number {
  const share = blastCeiling > 0 ? node.blast_radius / blastCeiling : 0;
  return 7 + Math.round(Math.sqrt(share) * 15);
}

function prettyType(nodeType: string): string {
  if (!nodeType) return 'node';
  return nodeType.replace(/[_-]+/g, ' ');
}

async function fetchGraph(repo: ProjectRepo): Promise<GraphPayload> {
  const params = new URLSearchParams({repoPath: repo.path, repoName: repo.name});
  const response = await fetch(`/api/graph?${params.toString()}`, {cache: 'no-store'});
  const text = await response.text();
  let payload: unknown = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = {};
    }
  }
  if (!response.ok) {
    const data = payload && typeof payload === 'object' ? (payload as {error?: string}) : {};
    throw new Error(data.error || `Graph request failed with ${response.status}`);
  }
  return payload as GraphPayload;
}

// Run the force simulation synchronously to a settled layout, then freeze. We
// never animate: the positions are computed once per data change and the SVG is
// static thereafter.
function computeLayout(nodes: GraphNode[], edges: GraphEdge[]): {
  positions: Map<string, {x: number; y: number}>;
} {
  const simNodes: SimNode[] = nodes.map((data) => ({data}));
  const byKey = new Map<string, SimNode>();
  simNodes.forEach((n) => byKey.set(n.data.identity_key, n));

  const simLinks: SimLink[] = [];
  for (const edge of edges) {
    const source = byKey.get(edge.src_identity_key);
    const target = byKey.get(edge.dst_identity_key);
    if (source && target) simLinks.push({source, target, data: edge});
  }

  const simulation = forceSimulation(simNodes)
    .force('charge', forceManyBody().strength(-260))
    .force('link', forceLink<SimNode, SimLink>(simLinks).id((n) => n.data.identity_key).distance(70).strength(0.6))
    .force('center', forceCenter(VIEW_W / 2, VIEW_H / 2))
    .force('x', forceX(VIEW_W / 2).strength(0.05))
    .force('y', forceY(VIEW_H / 2).strength(0.05))
    .stop();

  const ticks = Math.min(400, Math.max(120, simNodes.length * 4));
  for (let i = 0; i < ticks; i += 1) simulation.tick();

  const positions = new Map<string, {x: number; y: number}>();
  simNodes.forEach((n) => positions.set(n.data.identity_key, {x: n.x ?? VIEW_W / 2, y: n.y ?? VIEW_H / 2}));
  return {positions};
}

// Fit the settled cloud into the viewBox with padding so the graph fills the
// frame regardless of how the simulation drifted.
function fitViewBox(positions: Map<string, {x: number; y: number}>): string {
  if (positions.size === 0) return `0 0 ${VIEW_W} ${VIEW_H}`;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  positions.forEach(({x, y}) => {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  });
  const pad = 48;
  const w = Math.max(maxX - minX, 1) + pad * 2;
  const h = Math.max(maxY - minY, 1) + pad * 2;
  return `${minX - pad} ${minY - pad} ${w} ${h}`;
}

export type BlastRadiusViewProps = {
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  onTargetChange: (value: string) => void;
};

export default function BlastRadiusView({target, targetRepos, onTargetChange}: BlastRadiusViewProps) {
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const requestRef = useRef(0);

  const repo = target.mode === 'repo' ? target.repo : null;

  useEffect(() => {
    if (!repo) {
      setGraph(null);
      return;
    }
    const token = (requestRef.current += 1);
    setLoading(true);
    setError(null);
    fetchGraph(repo)
      .then((payload) => {
        if (token !== requestRef.current) return;
        setGraph(payload);
        setSelectedKey(null);
      })
      .catch((err: unknown) => {
        if (token !== requestRef.current) return;
        setError(err instanceof Error ? err.message : 'Unable to load the asset graph.');
        setGraph(null);
      })
      .finally(() => {
        if (token === requestRef.current) setLoading(false);
      });
  }, [repo?.path, repo?.name]);

  if (!repo) {
    return (
      <div className="view-stack">
        <NeedsRepoTarget
          targetRepos={targetRepos}
          onTargetChange={onTargetChange}
          message="Pick a repo to map its blast radius."
        />
      </div>
    );
  }

  return (
    <div className="view-stack blast-view">
      {error && (
        <div className="blast-banner blast-banner-error" role="alert">
          <AlertTriangle size={15} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}
      {loading && !graph && <BlastSkeleton />}
      {graph && <BlastGraph graph={graph} selectedKey={selectedKey} onSelect={setSelectedKey} loading={loading} />}
    </div>
  );
}

function BlastSkeleton() {
  return (
    <div className="blast-canvas-shell blast-canvas-loading" aria-busy="true">
      <RefreshCw size={18} className="blast-spin" aria-hidden="true" />
      <span>Building the asset graph…</span>
    </div>
  );
}

function BlastGraph({
  graph,
  selectedKey,
  onSelect,
  loading,
}: {
  graph: GraphPayload;
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
  loading: boolean;
}) {
  // Render the highest-consequence slice when a graph is enormous, so the DOM
  // stays sane. Sort by blast radius (crown-jewel reachers first) and cap.
  const {renderNodes, truncated, totalNodes} = useMemo(() => {
    const sorted = [...graph.nodes].sort((a, b) => {
      if (a.reaches_crown_jewel !== b.reaches_crown_jewel) return a.reaches_crown_jewel ? -1 : 1;
      return b.blast_radius - a.blast_radius;
    });
    const slice = sorted.slice(0, MAX_RENDERED_NODES);
    return {renderNodes: slice, truncated: sorted.length > slice.length, totalNodes: graph.nodes.length};
  }, [graph.nodes]);

  const visibleKeys = useMemo(() => new Set(renderNodes.map((n) => n.identity_key)), [renderNodes]);
  const renderEdges = useMemo(
    () => graph.edges.filter((e) => visibleKeys.has(e.src_identity_key) && visibleKeys.has(e.dst_identity_key)),
    [graph.edges, visibleKeys],
  );

  const layout = useMemo(() => computeLayout(renderNodes, renderEdges), [renderNodes, renderEdges]);
  const viewBox = useMemo(() => fitViewBox(layout.positions), [layout]);

  const blastCeiling = useMemo(
    () => renderNodes.reduce((max, n) => Math.max(max, n.blast_radius), 0),
    [renderNodes],
  );

  const incident = graph.active_incident;
  // The lit path: the tripped node + every node on the BFS blast tree, and the
  // exact tree edges (src→dst by identity key) the server walked.
  const litNodeKeys = useMemo(() => keysForIncident(incident), [incident]);
  const litEdgeKeys = useMemo(() => edgeKeysForIncident(incident), [incident]);

  const nodeByKey = useMemo(() => {
    const map = new Map<string, GraphNode>();
    renderNodes.forEach((n) => map.set(n.identity_key, n));
    return map;
  }, [renderNodes]);

  const selected = selectedKey ? nodeByKey.get(selectedKey) ?? null : null;
  const crownCount = renderNodes.filter((n) => n.is_crown_jewel).length;

  if (graph.nodes.length === 0) {
    return (
      <BlastEmpty
        title="No asset graph yet"
        body={
          graph.reason_none ||
          'This repo has no asset-graph nodes. Run a scan to map its dependencies and surfaces, then the blast radius shows up here.'
        }
      />
    );
  }

  return (
    <div className="blast-layout">
      <div className="blast-main">
        <BlastSummaryStrip graph={graph} renderedCount={renderNodes.length} crownCount={crownCount} />
        {incident ? (
          <IncidentBanner incident={incident} />
        ) : (
          <div className="blast-banner blast-banner-calm" role="status">
            <ShieldAlert size={15} aria-hidden="true" />
            <span>No active incident. Nodes are coloured by consequence; trip a bound decoy to light its blast path.</span>
          </div>
        )}
        {!graph.crown_jewels_defined && (
          <div className="blast-banner blast-banner-info" role="note">
            <Gem size={15} aria-hidden="true" />
            <span>
              No crown jewel is labeled, so nodes are ranked by raw blast radius. Label one in{' '}
              <code>.devsec/crown-jewels.json</code> to colour by what an intruder could actually reach.
            </span>
          </div>
        )}
        <div className="blast-canvas-shell">
          {loading && (
            <div className="blast-canvas-refreshing" aria-hidden="true">
              <RefreshCw size={14} className="blast-spin" />
            </div>
          )}
          <svg
            className="blast-canvas"
            viewBox={viewBox}
            role="img"
            aria-label={`Asset graph for ${graph.repo}: ${renderNodes.length} nodes${incident ? ', one active incident path lit' : ''}.`}
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              <filter id="blast-glow" x="-60%" y="-60%" width="220%" height="220%">
                <feGaussianBlur stdDeviation="3.4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <marker
                id="blast-arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M0,0 L10,5 L0,10 z" fill="var(--ink-faint)" />
              </marker>
              <marker
                id="blast-arrow-lit"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M0,0 L10,5 L0,10 z" fill="var(--sev-crit)" />
              </marker>
            </defs>

            <g className="blast-edges">
              {renderEdges.map((edge, i) => {
                const a = layout.positions.get(edge.src_identity_key);
                const b = layout.positions.get(edge.dst_identity_key);
                if (!a || !b) return null;
                const lit = litEdgeKeys.has(`${edge.src_identity_key}->${edge.dst_identity_key}`);
                return (
                  <line
                    key={`${edge.src_identity_key}->${edge.dst_identity_key}-${i}`}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    className={lit ? 'blast-edge blast-edge-lit' : 'blast-edge'}
                    markerEnd={lit ? 'url(#blast-arrow-lit)' : 'url(#blast-arrow)'}
                    filter={lit ? 'url(#blast-glow)' : undefined}
                  />
                );
              })}
            </g>

            <g className="blast-nodes">
              {renderNodes.map((node) => {
                const pos = layout.positions.get(node.identity_key);
                if (!pos) return null;
                const tone = nodeTone(node, blastCeiling);
                const r = nodeRadius(node, blastCeiling);
                const lit = litNodeKeys.has(node.identity_key);
                const isTripped = incident?.identity_key === node.identity_key;
                const isSelected = selectedKey === node.identity_key;
                return (
                  <g
                    key={node.identity_key}
                    transform={`translate(${pos.x} ${pos.y})`}
                    className={`blast-node${lit ? ' is-lit' : ''}${isTripped ? ' is-tripped' : ''}${isSelected ? ' is-selected' : ''}`}
                    onClick={() => onSelect(isSelected ? null : node.identity_key)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        onSelect(isSelected ? null : node.identity_key);
                      }
                    }}
                    aria-label={`${node.label}, ${prettyType(node.node_type)}, blast radius ${node.blast_radius}${node.is_crown_jewel ? ', crown jewel' : ''}${isTripped ? ', tripped decoy' : ''}`}
                  >
                    {(lit || isSelected) && (
                      <circle className="blast-node-halo" r={r + 7} style={{fill: toneVar[tone]}} />
                    )}
                    <circle
                      className="blast-node-core"
                      r={r}
                      style={{fill: toneVar[tone]}}
                      filter={isTripped ? 'url(#blast-glow)' : undefined}
                    />
                    {node.is_crown_jewel && (
                      <Crown className="blast-node-crown" width={Math.max(11, r)} height={Math.max(11, r)} x={-Math.max(11, r) / 2} y={-Math.max(11, r) / 2} aria-hidden="true" />
                    )}
                    {isTripped && (
                      <Target className="blast-node-trip" width={r * 1.7} height={r * 1.7} x={-r * 0.85} y={-r * 0.85} aria-hidden="true" />
                    )}
                    <text className="blast-node-label" y={r + 13} textAnchor="middle">
                      {node.label.length > 26 ? `${node.label.slice(0, 24)}…` : node.label}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
          {truncated && (
            <p className="blast-truncate-note">
              Showing the {renderNodes.length} highest-consequence nodes of {totalNodes}. The rest are lower blast radius and
              omitted to keep the map readable.
            </p>
          )}
        </div>
        <BlastLegend crownJewelsDefined={graph.crown_jewels_defined} hasIncident={Boolean(incident)} />
      </div>
      <aside className="blast-aside">
        {selected ? (
          <NodeDetail node={selected} isTripped={incident?.identity_key === selected.identity_key} />
        ) : incident ? (
          <IncidentDetail incident={incident} />
        ) : (
          <div className="blast-aside-empty">
            <p>Select a node to inspect its consequence, or trip a bound decoy to light an incident path.</p>
          </div>
        )}
      </aside>
    </div>
  );
}

function keysForIncident(incident: GraphActiveIncident | null): Set<string> {
  const keys = new Set<string>();
  if (!incident) return keys;
  keys.add(incident.identity_key);
  for (const step of incident.path) keys.add(step.identity_key);
  return keys;
}

function edgeKeysForIncident(incident: GraphActiveIncident | null): Set<string> {
  const keys = new Set<string>();
  if (!incident) return keys;
  for (const edge of incident.edges) keys.add(`${edge.src_identity_key}->${edge.dst_identity_key}`);
  return keys;
}

function BlastSummaryStrip({
  graph,
  renderedCount,
  crownCount,
}: {
  graph: GraphPayload;
  renderedCount: number;
  crownCount: number;
}) {
  const reachers = graph.nodes.filter((n) => n.reaches_crown_jewel).length;
  return (
    <section className="summary-strip">
      <MetricBlock label="Asset nodes" value={String(graph.nodes.length)} detail={`${renderedCount} mapped`} />
      <MetricBlock label="Relationships" value={String(graph.edges.length)} detail="directed edges" />
      <MetricBlock
        label="Crown jewels"
        value={graph.crown_jewels_defined ? String(crownCount) : '—'}
        detail={graph.crown_jewels_defined ? 'labeled' : 'none labeled'}
      />
      <MetricBlock
        label="Reach a jewel"
        value={graph.crown_jewels_defined ? String(reachers) : '—'}
        detail="nodes"
        tone={reachers > 0 ? 'crit' : undefined}
      />
      <MetricBlock
        label="Active incidents"
        value={String(graph.active_incidents.length)}
        detail={graph.active_incidents.length > 0 ? 'path lit' : 'none'}
        tone={graph.active_incidents.length > 0 ? 'crit' : undefined}
      />
    </section>
  );
}

function MetricBlock({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone?: ConsequenceTone;
}) {
  // Match the shared `.metric-block` DOM shape (div > strong > span) so it
  // inherits the dashboard's metric styling; tone only recolours the value.
  return (
    <div className="metric-block">
      <div>
        <span className="eyebrow">{label}</span>
      </div>
      <strong style={tone ? {color: toneVar[tone]} : undefined}>{value}</strong>
      <span>{detail}</span>
    </div>
  );
}

function IncidentBanner({incident}: {incident: GraphActiveIncident}) {
  return (
    <div className="blast-banner blast-banner-incident" role="alert">
      <Target size={16} aria-hidden="true" />
      <div className="blast-banner-body">
        <strong>Confirmed intrusion near {incident.node.label || incident.identity_key}</strong>
        <span>{incident.message}</span>
      </div>
    </div>
  );
}

function IncidentDetail({incident}: {incident: GraphActiveIncident}) {
  const path = incident.path;
  return (
    <div className="blast-detail">
      <header className="blast-detail-head">
        <Target size={16} aria-hidden="true" />
        <h3>Active incident</h3>
      </header>
      <dl className="blast-detail-grid">
        <dt>Tripped node</dt>
        <dd>{incident.node.label || incident.identity_key}</dd>
        <dt>Triggered</dt>
        <dd>{incident.triggered_at ? new Date(incident.triggered_at).toLocaleString() : 'unknown'}</dd>
        <dt>Blast radius</dt>
        <dd>{incident.blast_radius ?? 0} reachable node(s)</dd>
        {incident.reaches_crown_jewel && incident.crown_jewel && (
          <>
            <dt>Reaches</dt>
            <dd className="blast-detail-jewel">
              <Crown size={13} aria-hidden="true" /> {incident.crown_jewel.label}
            </dd>
          </>
        )}
      </dl>
      <p className="blast-detail-honest">{incident.message}</p>
      {path.length > 0 && (
        <div className="blast-path">
          <h4>Blast-radius path</h4>
          <ol>
            <li className="blast-path-origin">
              <span className="blast-path-dot" /> {incident.node.label || incident.identity_key}
            </li>
            {path.map((step) => (
              <li key={step.identity_key}>
                <span className="blast-path-dot" />
                <span>
                  {step.label}
                  {step.via && <em className="blast-path-via"> via {step.via.replace(/[_-]+/g, ' ')}</em>}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function NodeDetail({node, isTripped}: {node: GraphNode; isTripped: boolean}) {
  return (
    <div className="blast-detail">
      <header className="blast-detail-head">
        {node.is_crown_jewel ? <Crown size={16} aria-hidden="true" /> : <Gem size={16} aria-hidden="true" />}
        <h3>{node.label}</h3>
      </header>
      <dl className="blast-detail-grid">
        <dt>Type</dt>
        <dd>{prettyType(node.node_type)}</dd>
        <dt>Blast radius</dt>
        <dd>{node.blast_radius} reachable node(s)</dd>
        <dt>Reaches a jewel</dt>
        <dd>
          {node.reaches_crown_jewel
            ? `Yes${node.distance_to_crown_jewel != null ? `, ${node.distance_to_crown_jewel} hop(s)` : ''} (${node.consequence_confidence})`
            : 'No'}
        </dd>
        <dt>Confidence</dt>
        <dd>{node.confidence}</dd>
      </dl>
      {isTripped && (
        <p className="blast-detail-honest">
          A decoy guarding this node was tripped — confirmed intrusion near here, not proof this specific finding was
          exploited.
        </p>
      )}
      {node.is_crown_jewel && <p className="blast-detail-note">Human-labeled crown jewel — the thing worth protecting.</p>}
    </div>
  );
}

function BlastLegend({crownJewelsDefined, hasIncident}: {crownJewelsDefined: boolean; hasIncident: boolean}) {
  return (
    <div className="blast-legend" aria-hidden="true">
      <span className="blast-legend-item">
        <span className="blast-legend-swatch" style={{background: 'var(--sev-crit)'}} /> Reaches a crown jewel
      </span>
      <span className="blast-legend-item">
        <span className="blast-legend-swatch" style={{background: 'var(--sev-high)'}} /> Large blast radius
      </span>
      <span className="blast-legend-item">
        <span className="blast-legend-swatch" style={{background: 'var(--sev-warn)'}} /> Moderate reach
      </span>
      <span className="blast-legend-item">
        <span className="blast-legend-swatch" style={{background: 'var(--sev-low)'}} /> Reaches nothing
      </span>
      {crownJewelsDefined && (
        <span className="blast-legend-item">
          <Crown size={12} aria-hidden="true" /> Crown jewel
        </span>
      )}
      {hasIncident && (
        <span className="blast-legend-item">
          <Target size={12} aria-hidden="true" /> Tripped decoy
        </span>
      )}
    </div>
  );
}

function BlastEmpty({title, body}: {title: string; body: string}) {
  return (
    <div className="blast-empty">
      <Gem size={26} aria-hidden="true" />
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}
