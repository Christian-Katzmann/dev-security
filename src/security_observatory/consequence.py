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
from collections import deque
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


# ---------------------------------------------------------------------------
# Decoy placement suggestion (Honeygraph 2 — the "worst node to guard")
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlacementSuggestion:
    """A proposal for where to plant a decoy — the highest-consequence node.

    This is a *suggestion only*: nothing is minted, bound, or written. The caller
    presents it to a human who confirms before anything is planted.

    ``ranked_by`` is ``"crown_jewel_reachability"`` when a labeled crown jewel is
    reachable from the chosen node (the sharp signal), or ``"blast_radius"`` when no
    crown jewel is labeled and we fall back to raw reach. ``auto_plant_safe`` is the
    honesty gate: it is ``False`` for a weak/low-confidence node so the UI never
    pre-offers auto-placement on an unproven surface — Campaign 1 proved only
    strong-edge dependency reachability on real data.
    """

    node: dict[str, Any]
    consequence: Consequence
    ranked_by: str
    crown_jewels_defined: bool
    auto_plant_safe: bool
    reason: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": dict(self.node),
            "consequence": self.consequence.to_dict(),
            "ranked_by": self.ranked_by,
            "crown_jewels_defined": self.crown_jewels_defined,
            "auto_plant_safe": self.auto_plant_safe,
            "reason": self.reason,
            "warnings": list(self.warnings),
        }


def _placement_is_confident(node_confidence: str, consequence: Consequence) -> bool:
    """Whether a node is solid enough to pre-offer for auto-placement.

    Conservative on purpose: the node itself must be ``strong``; a crown-jewel path
    must also be ``strong`` end to end (no weak/unknown hop); and a node that reaches
    nothing at all (blast radius 0, no crown jewel) illuminates no path, so guarding
    it teaches an operator nothing.
    """
    if node_confidence != "strong":
        return False
    if consequence.reaches_crown_jewel:
        return consequence.confidence == "strong"
    return consequence.blast_radius > 0


def suggest_placement_node(
    node_rows: Iterable[Any],
    edge_rows: Iterable[Any],
) -> PlacementSuggestion | None:
    """Pick the single highest-consequence node to guard with a decoy.

    Ranks every node by reachable consequence (``_consequence_score`` — prefer
    reaching a crown jewel, then a stronger path, then nearer, then a larger blast
    radius). When a crown jewel is labeled, the winner is the surface whose
    compromise most threatens it; when none is labeled — the common case, since
    crown jewels are human-declared and may be absent — it degrades honestly to the
    largest raw blast radius and says so in ``warnings``.

    Returns ``None`` when there is no graph to rank. Pure and side-effect free.
    """
    rows = list(node_rows)
    if not rows:
        return None
    consequences = compute_node_consequences(rows, edge_rows)
    if not consequences:
        return None

    ranked: list[tuple[Any, tuple[str, str], Consequence]] = []
    for row in rows:
        key = (str(_get(row, "node_type") or ""), str(_get(row, "identity_key") or ""))
        consequence = consequences.get(key)
        if consequence is not None:
            ranked.append((row, key, consequence))
    if not ranked:
        return None

    best_row, best_key, best = max(ranked, key=lambda item: _consequence_score(item[2]))
    node_type, identity_key = best_key
    node_confidence = str(_get(best_row, "confidence") or "unknown")
    node = {
        "asset_node_id": _get(best_row, "id"),
        "node_type": node_type,
        "identity_key": identity_key,
        "label": str(_get(best_row, "label") or identity_key),
        "confidence": node_confidence,
        "is_crown_jewel": bool(_get(best_row, "is_crown_jewel")),
    }

    auto_plant_safe = _placement_is_confident(node_confidence, best)
    warnings: list[str] = []

    if best.reaches_crown_jewel:
        ranked_by = "crown_jewel_reachability"
        jewel_label = (best.crown_jewel or {}).get("label", "a crown jewel")
        hops = best.distance if best.distance is not None else "?"
        reason = (
            f"Highest-consequence dependency surface: if compromised, a blast from "
            f"this node reaches the crown jewel '{jewel_label}' in {hops} hop(s), "
            f"touching {best.blast_radius} asset(s) on the way. Guard it with a decoy "
            f"and an intruder probing this surface trips the wire before reaching "
            f"what matters."
        )
        if best.confidence != "strong":
            warnings.append(
                f"The path to the crown jewel leans on a '{best.confidence}'-confidence "
                f"hop, so treat the reachability as unproven, not certain."
            )
    else:
        ranked_by = "blast_radius"
        reason = (
            f"Highest-consequence dependency surface: if compromised, the blast from "
            f"this node reaches {best.blast_radius} other asset(s) — the largest "
            f"reachable surface in this graph."
        )

    if not best.crown_jewels_defined:
        warnings.append(
            "No crown jewel is labeled, so this is ranked by raw blast radius. Label "
            "one in .devsec/crown-jewels.json so DëvSec can rank by what an intruder "
            "could actually reach, not just how far the blast spreads."
        )

    if not auto_plant_safe:
        if node_confidence != "strong":
            warnings.append(
                f"This node's classification confidence is '{node_confidence}', not "
                f"'strong'. DëvSec will not pre-offer auto-placement here — confirm "
                f"manually if you still want to guard this surface."
            )
        elif not best.reaches_crown_jewel and best.blast_radius == 0:
            warnings.append(
                "This node reaches nothing else in the graph (blast radius 0); a "
                "decoy here illuminates no path."
            )

    return PlacementSuggestion(
        node=node,
        consequence=best,
        ranked_by=ranked_by,
        crown_jewels_defined=best.crown_jewels_defined,
        auto_plant_safe=auto_plant_safe,
        reason=reason,
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Tripwire bridge (Honeygraph 2 — trigger → flip the case → light the path)
# ---------------------------------------------------------------------------


#: The only honest thing a tripped decoy proves. A trip means an adversary
#: reached this region of the graph and took the bait — it does NOT prove this
#: specific finding was the entry vector, nor that it was "exploited". Every
#: surface that renders an active incident reuses this exact wording so the
#: honesty boundary can never drift between Python and the dashboard.
ACTIVE_INCIDENT_MESSAGE = (
    "Confirmed intrusion near this node: a decoy guarding this high-consequence "
    "dependency surface was triggered. This proves an adversary reached this region "
    "and took the bait — not that this specific finding was exploited. Treat every "
    "asset on the illuminated blast-radius path as potentially within reach."
)


def blast_radius_from(
    node_key: tuple[str, str],
    node_rows: Iterable[Any],
    edge_rows: Iterable[Any],
) -> dict[str, Any] | None:
    """The reachable blast region from a *tripped* node, as real graph data.

    A breadth-first walk over the same blast-propagation adjacency the consequence
    score uses (``reachable_from``/``stored_in``/``unlocks`` forward, ``depends_on``
    reversed). Returns the ordered set of reachable nodes — each tagged with its hop
    ``distance`` and the ``via`` edge it was first reached through — plus the BFS-tree
    edges actually traversed, so a caller (or the graph view) lights a path that is
    real edges, never a guess. The nearest-crown-jewel path rides along when one is
    labeled and reachable.

    Returns ``None`` when the node is not in the graph. Pure and side-effect free.
    """
    graph = _build_graph_nodes(node_rows)
    nodes = graph.nodes
    if node_key not in nodes:
        return None
    adjacency = _build_adjacency(graph, edge_rows)
    crown_keys = {key for key, node in nodes.items() if node.is_crown_jewel}
    crown_jewels_defined = bool(crown_keys)

    # BFS in blast-propagation direction: distance is hop count; the first edge to
    # reach each node defines its place in the spanning tree (a stable, readable
    # "how the blast spreads" view, not every possible path).
    distance: dict[tuple[str, str], int] = {node_key: 0}
    parent: dict[tuple[str, str], tuple[tuple[str, str], str, str]] = {}
    order: list[tuple[str, str]] = []
    queue: deque[tuple[str, str]] = deque([node_key])
    while queue:
        current = queue.popleft()
        for neighbor, edge_type, edge_conf in adjacency.get(current, ()):
            if neighbor in distance:
                continue
            distance[neighbor] = distance[current] + 1
            parent[neighbor] = (current, edge_type, edge_conf)
            order.append(neighbor)
            queue.append(neighbor)

    reachable = [
        {**_node_summary(nodes[key], parent[key][1]), "distance": distance[key]}
        for key in order
    ]
    edges = [
        {
            "src_identity_key": parent[key][0][1],
            "dst_identity_key": key[1],
            "edge_type": parent[key][1],
            "confidence": parent[key][2],
        }
        for key in order
    ]

    # Reuse the consequence search for the nearest-crown-jewel path + weakest-link
    # confidence — identical traversal, so the two views can never disagree.
    consequence = _consequence_from(node_key, nodes, adjacency, crown_keys, crown_jewels_defined)
    return {
        "node": _node_summary(nodes[node_key]),
        "reachable": reachable,
        "edges": edges,
        "blast_radius": len(order),
        "reaches_crown_jewel": consequence.reaches_crown_jewel,
        "crown_jewel": dict(consequence.crown_jewel) if consequence.crown_jewel else None,
        "crown_jewel_path": [dict(step) for step in consequence.path],
        "confidence": consequence.confidence,
        "crown_jewels_defined": crown_jewels_defined,
    }


def apply_active_incidents(
    cases: Iterable[Any],
    incidents: Iterable[dict[str, Any]],
) -> list[str]:
    """Flip the case sitting AT each tripped, bound node to ``active_incident``.

    **The rule (the campaign's open question, answered):** only the case *at* the
    guarded node escalates — never every case along the blast path. A trip proves an
    adversary reached *this* node and took the bait; the downstream nodes are blast
    radius (what they could reach *next*), not confirmed-touched, so escalating them
    too would outrun the evidence. The path is attached to the flipped case for
    illumination, not escalation.

    Honesty is structural: the attached context and the prepended reason both use
    :data:`ACTIVE_INCIDENT_MESSAGE` — "intrusion near this node", never "this finding
    was exploited". Mutates the matching case dicts in place; returns the flipped
    ``case_id`` list. A serve-time overlay (cases are derived per scan, so the flip
    can't be a stored mutation), mirroring how ``_attach_case_decision`` overlays a
    suppression onto a freshly derived case.
    """
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for incident in incidents:
        key = (str(incident.get("node_type") or ""), str(incident.get("identity_key") or ""))
        if key[1]:
            # Newest trip wins if two open incidents somehow guard the same node;
            # callers pass them newest-first, so keep the first seen.
            by_key.setdefault(key, incident)
    if not by_key:
        return []

    flipped: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        match = next((by_key[key] for key in case_node_identities(case) if key in by_key), None)
        if match is None:
            continue
        case["action_level"] = "active_incident"
        case["active_incident"] = {
            "event_id": match.get("event_id"),
            "honey_key_id": match.get("honey_key_id"),
            "triggered_at": match.get("triggered_at"),
            "node": match.get("node"),
            "path": list(match.get("path") or []),
            "edges": list(match.get("edges") or []),
            "blast_radius": match.get("blast_radius"),
            "reaches_crown_jewel": bool(match.get("reaches_crown_jewel")),
            "crown_jewel": match.get("crown_jewel"),
            "crown_jewel_path": list(match.get("crown_jewel_path") or []),
            "message": ACTIVE_INCIDENT_MESSAGE,
        }
        reasons = [reason for reason in (case.get("priority_reasons") or []) if reason != ACTIVE_INCIDENT_MESSAGE]
        case["priority_reasons"] = [ACTIVE_INCIDENT_MESSAGE, *reasons]
        flipped.append(str(case.get("case_id") or case.get("id") or ""))
    return flipped
