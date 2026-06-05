from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import json
import re

from .enrichment import DependencyEnrichment, DependencyTrustRecord, extract_fixed_version
from .model import Finding, SecurityCase, normalize_severity


ACTION_LEVELS = {"fix_now", "verify", "watch", "info"}
EXPLOITED_RE = re.compile(r"\b(known exploited|likely exploited|exploited in the wild|cisa kev|active exploitation)\b", re.IGNORECASE)
DependencyContext = DependencyEnrichment | DependencyTrustRecord | dict[str, Any] | None


@dataclass(slots=True)
class PriorityDecision:
    action_level: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide_action_level(
    item: Finding | SecurityCase | dict[str, Any],
    enrichment: DependencyContext = None,
) -> PriorityDecision:
    category = str(_get(item, "category") or "").lower()
    severity = normalize_severity(_get(item, "severity"))
    confidence = str(_get(item, "confidence") or "medium").lower()
    scanner = str(_get(item, "scanner") or "").lower()
    scanners = [str(value).lower() for value in (_get(item, "scanners") or [])]
    text = _item_text(item, enrichment)
    fix_available = _fix_available(item, enrichment)
    known_exploited = _known_exploited(enrichment) or bool(EXPLOITED_RE.search(text))

    if category == "secrets" or scanner in {"gitleaks", "trufflehog"}:
        return PriorityDecision("fix_now", ["secret findings need rotation before cleanup"])

    if known_exploited:
        return PriorityDecision("fix_now", ["known or likely exploitation signal"])

    if severity == "critical":
        return _with_dependency_trust(
            PriorityDecision("fix_now" if confidence != "low" else "verify", ["critical severity"]),
            item,
            enrichment,
            severity,
        )

    if severity == "high" and fix_available:
        action = "fix_now" if confidence != "low" else "verify"
        return _with_dependency_trust(PriorityDecision(action, ["high severity with an available fix"]), item, enrichment, severity)

    if severity == "high":
        return _with_dependency_trust(PriorityDecision("verify", ["high severity needs confirmation or a fix path"]), item, enrichment, severity)

    if confidence == "low" or _scanner_only(item, scanners):
        if severity in {"info", "low"}:
            return _with_dependency_trust(PriorityDecision("watch", ["low-confidence scanner-only signal"]), item, enrichment, severity)
        return _with_dependency_trust(PriorityDecision("verify", ["low-confidence scanner-only signal"]), item, enrichment, severity)

    if severity == "medium":
        return _with_dependency_trust(PriorityDecision("verify", ["medium severity"]), item, enrichment, severity)

    if severity == "low":
        return _with_dependency_trust(PriorityDecision("watch", ["low severity"]), item, enrichment, severity)

    return _with_dependency_trust(PriorityDecision("info", ["informational finding"]), item, enrichment, severity)


def action_level_for(
    item: Finding | SecurityCase | dict[str, Any],
    enrichment: DependencyContext = None,
) -> str:
    return decide_action_level(item, enrichment).action_level


def with_consequence(decision: PriorityDecision, consequence: dict[str, Any] | None) -> PriorityDecision:
    """Additive reachable-consequence boost (Honeygraph Phase 2).

    A finding whose asset-graph node can reach a human-labeled crown jewel is more
    dangerous than its scanner severity alone suggests. Modeled on
    ``_with_dependency_trust``: it only ever *raises* attention and always explains
    itself, so it can re-order findings but never silently override severity.

      - A *strong* path (every hop confident, by the weakest-link rule) promotes the
        finding to ``fix_now`` and says why in plain English.
      - A *weak* or *unknown* path only adds a reason; it must never auto-promote,
        because we never escalate on a low-confidence edge.

    Promote-only for the MVP: a high-severity finding that reaches nothing is never
    hushed. A case with no consequence (``None``) or that reaches no crown jewel is
    returned untouched, so it ranks exactly as it does today.
    """
    if not consequence or not consequence.get("reaches_crown_jewel"):
        return decision

    confidence = str(consequence.get("confidence") or "unknown").lower()
    jewel = consequence.get("crown_jewel") or {}
    jewel_label = str(jewel.get("label") or jewel.get("identity_key") or "a crown-jewel asset")
    hops = _hop_phrase(consequence.get("distance"))
    reasons = list(decision.reasons)

    if confidence == "strong":
        reasons.append(
            f"This finding can reach {jewel_label} {hops}, so it outranks "
            "higher-severity findings that reach nothing."
        )
        if _attention_rank("fix_now") < _attention_rank(decision.action_level):
            return PriorityDecision("fix_now", reasons)
        return PriorityDecision(decision.action_level, reasons)

    reasons.append(
        f"This finding might reach {jewel_label} {hops}, but the path runs through a "
        "low-confidence link, so it is flagged for a human instead of being auto-promoted."
    )
    return PriorityDecision(decision.action_level, reasons)


def _hop_phrase(distance: Any) -> str:
    try:
        hops = int(distance)
    except (TypeError, ValueError):
        return "through the asset graph"
    return "in 1 hop" if hops <= 1 else f"in {hops} hops"


def _get(source: Finding | SecurityCase | dict[str, Any], key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _item_text(item: Finding | SecurityCase | dict[str, Any], enrichment: DependencyContext) -> str:
    values = [
        _get(item, "title"),
        _get(item, "plain_english_risk"),
        _get(item, "remediation"),
        _get(item, "agent_prompt"),
        _stringify(_get(item, "evidence")),
        _stringify(enrichment),
    ]
    return "\n".join(str(value) for value in values if value)


def _fix_available(item: Finding | SecurityCase | dict[str, Any], enrichment: DependencyContext) -> bool:
    enrichment_data = _enrichment_dict(enrichment)
    if enrichment_data and (enrichment_data.get("fix_available") or enrichment_data.get("fixed_version")):
        return True
    return bool(extract_fixed_version(_as_finding_dict(item)))


def _known_exploited(enrichment: DependencyContext) -> bool:
    enrichment_data = _enrichment_dict(enrichment)
    if enrichment_data is None:
        return False
    kev = enrichment_data.get("cisa_kev")
    if isinstance(kev, dict) and kev.get("known_exploited") is True:
        return True
    epss = enrichment_data.get("epss")
    if isinstance(epss, dict):
        scores = epss.get("scores")
        if isinstance(scores, dict) and any(_float(value) >= 0.7 for value in scores.values()):
            return True
    return False


def _with_dependency_trust(
    decision: PriorityDecision,
    item: Finding | SecurityCase | dict[str, Any],
    enrichment: DependencyContext,
    severity: str,
) -> PriorityDecision:
    enrichment_data = _enrichment_dict(enrichment)
    if not _is_dependency(item) or enrichment_data is None:
        return decision

    facts = _dependency_trust_facts(enrichment_data)
    if not facts:
        return decision

    reasons = [*decision.reasons, *facts["reasons"]]
    if facts["boost"] and _attention_rank(decision.action_level) > _attention_rank("verify"):
        reasons.append(
            "This package appears widely used and its maintenance signals look weak, so it deserves a human check even though the scanner severity is only "
            f"{severity}."
        )
        return PriorityDecision("verify", reasons)
    return PriorityDecision(decision.action_level, reasons)


def _dependency_trust_facts(enrichment: dict[str, Any]) -> dict[str, Any] | None:
    has_trust_fields = any(
        key in enrichment
        for key in (
            "scorecard_score",
            "scorecard_status",
            "criticality_score",
            "criticality_status",
            "freshness",
            "status",
            "source_repo",
        )
    )
    if not has_trust_fields:
        return None

    freshness = str(enrichment.get("freshness") or enrichment.get("status") or "unknown").lower()
    scorecard = _optional_float(enrichment.get("scorecard_score"))
    criticality = _optional_float(enrichment.get("criticality_score"))
    scorecard_status = str(enrichment.get("scorecard_status") or "not_checked").lower()
    criticality_status = str(enrichment.get("criticality_status") or "not_checked").lower()
    reasons: list[str] = []

    if scorecard is not None:
        if scorecard <= 4.0:
            reasons.append(f"Project hygiene looks weak: the package's project-health score is {scorecard:g} out of 10.")
        elif scorecard >= 7.0:
            reasons.append(f"Project hygiene looks healthy: the package's project-health score is {scorecard:g} out of 10.")
        else:
            reasons.append(f"Project hygiene is mixed: the package's project-health score is {scorecard:g} out of 10.")
    elif scorecard_status in {"not_checked", "unavailable", "unknown_source"}:
        reasons.append("Project hygiene was not available, so it is not counted against this repo.")

    if criticality is not None:
        if criticality >= 0.7:
            reasons.append(f"Ecosystem importance is high: many projects are likely to depend on this package ({criticality:g}).")
        else:
            reasons.append(f"Ecosystem importance is lower: this package appears less central to the ecosystem ({criticality:g}).")
    elif criticality_status in {"not_checked", "unavailable", "not_found", "unknown_source"}:
        reasons.append("Ecosystem importance was not available, so it is not counted against this repo.")

    if freshness == "stale":
        reasons.append("The project trust data is stale, so treat it as an old clue, not proof.")
    elif freshness in {"unknown", "unavailable"}:
        reasons.append("Project trust freshness is unknown, so missing data is not treated as a problem.")

    boost = scorecard is not None and scorecard <= 4.0 and criticality is not None and criticality >= 0.7 and freshness != "stale"
    return {"boost": boost, "reasons": reasons}


def _enrichment_dict(enrichment: DependencyContext) -> dict[str, Any] | None:
    if enrichment is None:
        return None
    if isinstance(enrichment, dict):
        return enrichment
    if hasattr(enrichment, "to_dict"):
        data = enrichment.to_dict()
        return data if isinstance(data, dict) else None
    return None


def _is_dependency(item: Finding | SecurityCase | dict[str, Any]) -> bool:
    return str(_get(item, "category") or "").lower() == "dependencies" or str(_get(item, "scanner") or "").lower() in {
        "trivy",
        "osv-scanner",
        "grype",
    }


def _attention_rank(action_level: str) -> int:
    return {"fix_now": 0, "verify": 1, "watch": 2, "info": 3}.get(action_level, 3)


def _scanner_only(item: Finding | SecurityCase | dict[str, Any], scanners: list[str]) -> bool:
    if isinstance(item, Finding):
        return True
    if isinstance(item, dict) and item.get("scanner") and not item.get("evidence"):
        return True
    return len(scanners) <= 1 and not _get(item, "source_fingerprints")


def _as_finding_dict(item: Finding | SecurityCase | dict[str, Any]) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if isinstance(item, Finding):
        return item.to_dict()
    return {"title": item.title, "remediation": "\n".join(item.fix_steps), "category": item.category, "severity": item.severity}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "to_dict"):
        return json.dumps(value.to_dict(), sort_keys=True)
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
