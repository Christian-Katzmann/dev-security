"""Reachable-consequence scoring over the asset graph.

Phase 1 of the Honeygraph campaign built the asset graph — the *things worth
protecting* (nodes) and how they connect (edges). This module answers the
question the whole product rests on: **for each finding, can it reach something
that actually matters, and how much does it touch on the way?**

Two honest, readable signals per finding node:

  - ``reaches_crown_jewel`` — can a blast starting at this node arrive at a
    human-labeled crown jewel? Plus the *min hop distance* and the *path*.
  - ``blast_radius`` — how many other nodes can this node reach at all (a coarse
    "how much does this touch" count).

Both carry the **weakest-link confidence** along the path: the campaign's honesty
rule says one weak edge (or weak node) makes the whole consequence weak. We never
present a consequence more certain than its least-certain hop.

Edge orientation (blast propagation — "src compromised => dst at risk"):

  - ``reachable_from`` (secret -> resource) and ``stored_in`` (resource ->
    datastore) and ``unlocks`` are already oriented this way: follow them forward.
  - ``depends_on`` points *consumer -> provider* (A depends_on B). If the provider
    B is compromised, the blast flows to its consumers, so for blast propagation we
    walk ``depends_on`` **backward**. (This is why a vulnerable transitive package
    "reaches" the things that pull it in, not the other way round.)

No crown jewels labeled is not the same as "reaches nothing": the first is
*unknown* (we have nothing to assess against), the second is a definite
"reaches no crown jewel". A finding whose node is not in the graph at all gets no
consequence (``None``) and must rank exactly as it does today.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any, Iterable

from .asset_graph import CONFIDENCE_LEVELS

# Edge types already oriented in blast-propagation direction (follow forward).
_FORWARD_EDGE_TYPES = frozenset({"reachable_from", "stored_in", "unlocks"})
# Edge types pointing the opposite way to blast propagation (follow reversed).
_REVERSE_EDGE_TYPES = frozenset({"depends_on"})

_CONFIDENCE_RANK = {level: rank for rank, level in enumerate(CONFIDENCE_LEVELS)}


def _rank(confidence: str) -> int:
    return _CONFIDENCE_RANK.get(confidence, 0)


def _weaker(a: str, b: str) -> str:
    """Return the lower-confidence of two labels (the weakest-link rule)."""
    return a if _rank(a) <= _rank(b) else b


@dataclass(frozen=True, slots=True)
class Consequence:
    """What a finding's node can reach, and how sure we are.

    ``confidence`` is the weakest link on the path to the nearest crown jewel; it
    is ``"unknown"`` when there is no such path (either none labeled, or the node
    reaches none). ``crown_jewels_defined`` tells those two apart so a caller can
    say "we don't know" instead of falsely claiming "reaches nothing".
    """

    reaches_crown_jewel: bool
    distance: int | None
    blast_radius: int
    confidence: str
    crown_jewels_defined: bool
    path: tuple[dict[str, str], ...] = ()
    crown_jewel: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reaches_crown_jewel": self.reaches_crown_jewel,
            "distance": self.distance,
            "blast_radius": self.blast_radius,
            "confidence": self.confidence,
            "crown_jewels_defined": self.crown_jewels_defined,
            "path": [dict(step) for step in self.path],
            "crown_jewel": dict(self.crown_jewel) if self.crown_jewel else None,
        }


@dataclass(frozen=True, slots=True)
class _Node:
    key: tuple[str, str]  # (node_type, identity_key)
    node_type: str
    identity_key: str
    label: str
    confidence: str
    is_crown_jewel: bool


def _get(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


@dataclass(frozen=True, slots=True)
class _Graph:
    nodes: dict[tuple[str, str], _Node]
    id_to_key: dict[Any, tuple[str, str]]
    identity_to_key: dict[str, tuple[str, str]]


def _build_graph_nodes(node_rows: Iterable[Any]) -> _Graph:
    """Index nodes by identity key, numeric id (storage), and bare identity_key.

    Supports both input shapes without the caller caring which it has:
      - in-memory ``AssetNode`` objects (identity, no numeric id);
      - storage-reader dicts (carry the numeric ``id``).
    """
    nodes: dict[tuple[str, str], _Node] = {}
    id_to_key: dict[Any, tuple[str, str]] = {}
    identity_to_key: dict[str, tuple[str, str]] = {}
    for row in node_rows:
        node_type = str(_get(row, "node_type") or "")
        identity_key = str(_get(row, "identity_key") or "")
        if not identity_key:
            continue
        key = (node_type, identity_key)
        nodes[key] = _Node(
            key=key,
            node_type=node_type,
            identity_key=identity_key,
            label=str(_get(row, "label") or identity_key),
            confidence=str(_get(row, "confidence") or "unknown"),
            is_crown_jewel=bool(_get(row, "is_crown_jewel")),
        )
        node_id = _get(row, "id")
        if node_id is not None:
            id_to_key[node_id] = key
        # Bare-identity resolution mirrors storage.replace_asset_edges: edges are
        # addressed by identity_key alone (the edge doesn't know the node_type).
        identity_to_key.setdefault(identity_key, key)
    return _Graph(nodes=nodes, id_to_key=id_to_key, identity_to_key=identity_to_key)


def _build_adjacency(
    graph: _Graph,
    edge_rows: Iterable[Any],
) -> dict[tuple[str, str], list[tuple[tuple[str, str], str, str]]]:
    """Adjacency in *blast-propagation* direction: src compromised => dst at risk.

    Each entry is ``(neighbor_key, edge_type, confidence)``. An edge whose endpoint
    can't be resolved to a known node is skipped (it can't propagate to a node we
    don't have).
    """
    adjacency: dict[tuple[str, str], list[tuple[tuple[str, str], str, str]]] = {
        key: [] for key in graph.nodes
    }
    for row in edge_rows:
        edge_type = str(_get(row, "edge_type") or "")
        confidence = str(_get(row, "confidence") or "unknown")
        src_key = _edge_endpoint_key(row, "src", graph)
        dst_key = _edge_endpoint_key(row, "dst", graph)
        if src_key is None or dst_key is None or src_key == dst_key:
            continue
        if edge_type in _REVERSE_EDGE_TYPES:
            adjacency[dst_key].append((src_key, edge_type, confidence))
        else:
            # Forward + any unknown type both propagate src -> dst.
            adjacency[src_key].append((dst_key, edge_type, confidence))
    return adjacency


def _edge_endpoint_key(row: Any, side: str, graph: _Graph) -> tuple[str, str] | None:
    """Resolve one end of an edge row to a node key, across both edge shapes.

      - storage-reader form: numeric ``{side}_node_id`` -> resolved via id map;
      - in-memory ``AssetEdge`` form: ``{side}_identity_key`` (no node_type) ->
        resolved by identity, mirroring ``storage.replace_asset_edges``.
    """
    node_id = _get(row, f"{side}_node_id")
    if node_id is not None:
        return graph.id_to_key.get(node_id)
    identity_key = _get(row, f"{side}_identity_key")
    if identity_key:
        return graph.identity_to_key.get(str(identity_key).strip())
    return None


def compute_node_consequences(
    node_rows: Iterable[Any],
    edge_rows: Iterable[Any],
) -> dict[tuple[str, str], Consequence]:
    """Score every node by reachable consequence. Pure and side-effect free.

    Returns a map ``(node_type, identity_key) -> Consequence``. A node with no
    outgoing blast path still gets a Consequence (blast_radius 0). The crown-jewel
    fields reflect whether *any* crown jewel is labeled in this graph.
    """
    graph = _build_graph_nodes(node_rows)
    nodes = graph.nodes
    adjacency = _build_adjacency(graph, edge_rows)
    crown_keys = {key for key, node in nodes.items() if node.is_crown_jewel}
    crown_jewels_defined = bool(crown_keys)

    results: dict[tuple[str, str], Consequence] = {}
    for start in nodes:
        results[start] = _consequence_from(
            start, nodes, adjacency, crown_keys, crown_jewels_defined
        )
    return results


def _consequence_from(
    start: tuple[str, str],
    nodes: dict[tuple[str, str], _Node],
    adjacency: dict[tuple[str, str], list[tuple[tuple[str, str], str, str]]],
    crown_keys: set[tuple[str, str]],
    crown_jewels_defined: bool,
) -> Consequence:
    """Search the blast graph from ``start``.

    Lexicographic objective per node: smallest hop distance first, then strongest
    weakest-link confidence among equal-distance paths. Distance grows by exactly
    one per hop, so a Dijkstra ordered by ``(distance, -weakest_rank)`` settles the
    dominant key (distance) correctly and uses the weakest-link as an honest,
    readable tiebreak for which equal-length path to show.
    """
    start_conf = nodes[start].confidence
    best: dict[tuple[str, str], tuple[int, int]] = {start: (0, _rank(start_conf))}
    # parent[node] = (previous_node_key, edge_type used to arrive here)
    parent: dict[tuple[str, str], tuple[tuple[str, str], str]] = {}
    reachable: set[tuple[str, str]] = set()
    pq: list[tuple[int, int, tuple[str, str]]] = [(0, -_rank(start_conf), start)]

    while pq:
        dist, neg_rank, node = heapq.heappop(pq)
        weak_rank = -neg_rank
        if best.get(node) != (dist, weak_rank):
            continue  # stale priority-queue entry
        reachable.add(node)
        for neighbor, edge_type, edge_conf in adjacency.get(node, ()):
            step_rank = min(weak_rank, _rank(edge_conf), _rank(nodes[neighbor].confidence))
            candidate = (dist + 1, step_rank)
            current = best.get(neighbor)
            if (
                current is None
                or candidate[0] < current[0]
                or (candidate[0] == current[0] and candidate[1] > current[1])
            ):
                best[neighbor] = candidate
                parent[neighbor] = (node, edge_type)
                heapq.heappush(pq, (candidate[0], -candidate[1], neighbor))

    blast_radius = len(reachable) - 1  # exclude the start node itself

    # Nearest crown jewel (min distance, then strongest weakest-link), excluding
    # the start node even if it is itself a crown jewel — consequence is about what
    # a finding can *reach*, not what it already is.
    reachable_crowns = [
        key for key in crown_keys if key in best and key != start
    ]
    if not reachable_crowns:
        return Consequence(
            reaches_crown_jewel=False,
            distance=None,
            blast_radius=blast_radius,
            confidence="unknown",
            crown_jewels_defined=crown_jewels_defined,
        )

    target = min(reachable_crowns, key=lambda key: (best[key][0], -best[key][1]))
    distance, weakest_rank = best[target]
    confidence = CONFIDENCE_LEVELS[weakest_rank]
    path = _reconstruct_path(start, target, parent, nodes)
    return Consequence(
        reaches_crown_jewel=True,
        distance=distance,
        blast_radius=blast_radius,
        confidence=confidence,
        crown_jewels_defined=True,
        path=path,
        crown_jewel=_node_summary(nodes[target]),
    )


def _reconstruct_path(
    start: tuple[str, str],
    target: tuple[str, str],
    parent: dict[tuple[str, str], tuple[tuple[str, str], str]],
    nodes: dict[tuple[str, str], _Node],
) -> tuple[dict[str, str], ...]:
    """Walk parent pointers back to ``start``, recording the edge into each step.

    Each step carries ``via`` — the edge_type traversed to *arrive* at that node
    (``""`` for the start node) — so the UI can render "api-key → unlocks → db".
    """
    chain: list[tuple[tuple[str, str], str]] = [(target, "")]
    while chain[-1][0] != start:
        prev = parent.get(chain[-1][0])
        if prev is None:
            break
        prev_key, edge_type = prev
        # The edge_type belongs to the hop arriving at the current node; carry it
        # onto the current node's step, then move to its predecessor.
        chain[-1] = (chain[-1][0], edge_type)
        chain.append((prev_key, ""))
    chain.reverse()
    return tuple(_node_summary(nodes[key], via) for key, via in chain)


def _node_summary(node: _Node, via: str = "") -> dict[str, str]:
    summary = {
        "identity_key": node.identity_key,
        "node_type": node.node_type,
        "label": node.label,
    }
    if via:
        summary["via"] = via
    return summary


# ---------------------------------------------------------------------------
# Case <-> node mapping + attachment
# ---------------------------------------------------------------------------


def case_node_identities(case: Any) -> list[tuple[str, str]]:
    """Candidate ``(node_type, identity_key)`` keys a case may correspond to.

    A case is the cluster of findings the dashboard shows; its node is whatever
    the finding sits on. We reuse DëvSec's existing identities (same as
    ``asset_graph`` node derivation):

      - dependency / component findings -> ``component`` keyed by
        ``component_fingerprint`` (carried on each evidence item);
      - secret findings -> ``secret`` keyed by the affected file path;
      - IaC findings -> coarse ``resource`` keyed by the affected file path.

    Returns every plausible key; ``attach_consequences`` keeps only those that
    resolve to a real node and picks the most consequential.
    """
    keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(node_type: str, identity_key: str | None) -> None:
        identity_key = (identity_key or "").strip()
        if not identity_key:
            return
        key = (node_type, identity_key)
        if key not in seen:
            seen.add(key)
            keys.append(key)

    for item in _get(case, "evidence") or []:
        if isinstance(item, dict):
            _add("component", item.get("component_fingerprint"))

    for file_path in _get(case, "affected_files") or []:
        _add("secret", str(file_path))
        _add("resource", str(file_path))

    for surface in _get(case, "rotation_surfaces") or []:
        _add("secret", str(surface))

    return keys


def _consequence_score(consequence: Consequence) -> tuple:
    """Order key for picking a case's most significant consequence.

    Prefer: reaches a crown jewel > not; then a stronger path; then nearer; then a
    larger blast radius. (``distance`` negated so nearer sorts higher.)
    """
    return (
        1 if consequence.reaches_crown_jewel else 0,
        _rank(consequence.confidence) if consequence.reaches_crown_jewel else -1,
        -(consequence.distance if consequence.distance is not None else 1_000_000),
        consequence.blast_radius,
    )


def attach_consequences(
    cases: Iterable[Any],
    node_rows: Iterable[Any],
    edge_rows: Iterable[Any],
) -> None:
    """Compute consequence for every case and set ``case.consequence`` in place.

    A case that maps to no graph node is left untouched (``consequence`` stays
    ``None``) so findings with no consequence data rank exactly as they do today.
    """
    node_consequences = compute_node_consequences(node_rows, edge_rows)
    if not node_consequences:
        return
    for case in cases:
        candidates = [
            node_consequences[key]
            for key in case_node_identities(case)
            if key in node_consequences
        ]
        if not candidates:
            continue
        best = max(candidates, key=_consequence_score)
        _set_consequence(case, best.to_dict())


def _set_consequence(case: Any, value: dict[str, Any]) -> None:
    if isinstance(case, dict):
        case["consequence"] = value
    else:
        setattr(case, "consequence", value)
