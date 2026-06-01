"""Canonical case-lifecycle state machine for Security Observatory.

This module is the single source of truth for the states a security case can
hold and the transitions between them. Before it existed, two divergent
four-value enums described the same case across surfaces:

* the storage/decision view — ``verified`` / ``false_positive`` /
  ``accepted_risk`` / ``fixed`` (what a human records on a case; formerly
  ``decisions.CASE_DECISION_STATUSES``), enforced by a storage CHECK constraint;
* the MCP presentation view — ``open`` / ``verified`` / ``accepted_risk`` /
  ``resolved`` (what an agent querying MCP sees; formerly
  ``mcp_server.SUPPORTED_CASE_STATUSES``).

They are now expressed as ONE canonical lifecycle plus an explicit, documented
presentation mapping. ``decisions.py``, ``cases.py``, ``storage.py`` (the CHECK
constraint), and ``mcp_server.py`` all derive their state vocabulary from here.

Three layers, one place
-----------------------
1. **Decision statuses (stored)** — what a human records. Persisted in the
   ``case_decisions.status`` column and validated by ``set_case_decision``.
   See :data:`DECISION_STATUSES`.
2. **Lifecycle / presentation states (shown)** — what a case *is* at a glance,
   in the dashboard and the MCP ``cases(status=...)`` filter. See
   :data:`LIFECYCLE_STATES` and :data:`MCP_PRESENTATION_STATES`.
3. **The scan-diff axis** (``new`` / ``recurring`` / ``resolved``) — a SEPARATE
   state machine describing how a case *moved between two scans*. It is NOT a
   case lifecycle state; it is namespaced here as ``DIFF_*`` so the bare word
   "resolved" no longer names two unrelated machines. See :data:`DIFF_STATUSES`.

Mapping table
-------------
=========================  ==============================  =====================
Canonical lifecycle state  Stored decision form            MCP presentation form
=========================  ==============================  =====================
``open``                   (no decision)                   ``open``
``verified``               ``verified``                    ``verified``
``in_progress``            ``fixed`` / ``in_progress`` [*]  ``resolved`` [**]
``accepted_risk``          ``accepted_risk``               ``accepted_risk``
``resolved``               ``false_positive``, OR any      ``resolved``
                           case closed by a rescan
                           (diff ``resolved``)
=========================  ==============================  =====================

[*]  ``in_progress`` (a.k.a. *awaiting_rescan* / *verifying*) means "fix applied,
     awaiting rescan proof". A case with a ``fixed`` decision that still appears
     in the latest scan is verifying; once a rescan no longer finds it
     (diff ``resolved``) it becomes proof-bound ``resolved``.
[**] The MCP label is deliberately coarse — it has no per-scan diff context, so
     it folds ``fixed`` / ``false_positive`` → ``resolved`` for backward
     compatibility. An agent querying MCP ``status=resolved`` finds, in one
     place (this table + :data:`DECISION_PRESENTATION`), that ``resolved`` is a
     display fold of ``fixed`` + ``false_positive``. The dashboard, which has
     the diff axis, shows the richer ``in_progress`` beat (see
     :func:`lifecycle_state`).
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Layer 1 — stored decision statuses (the human disposition on a case)
# ---------------------------------------------------------------------------

VERIFIED = "verified"
FALSE_POSITIVE = "false_positive"
ACCEPTED_RISK = "accepted_risk"
FIXED = "fixed"
# New intermediate state (S-035): a fix has been applied but no rescan has yet
# confirmed the finding is gone. Non-terminal, non-suppressing.
IN_PROGRESS = "in_progress"

#: The canonical set of decision statuses a human can record on a case. This is
#: the single source of truth re-exported as ``decisions.CASE_DECISION_STATUSES``
#: and enforced by the ``case_decisions.status`` CHECK constraint in storage.
DECISION_STATUSES = frozenset({VERIFIED, FALSE_POSITIVE, ACCEPTED_RISK, FIXED, IN_PROGRESS})

#: Decisions that hide a case from the attention list. Re-exported as
#: ``decisions.SUPPRESSING_DECISION_STATUSES``. UNCHANGED by the lifecycle work:
#: adding ``in_progress`` must never change *which* states suppress — only
#: ``false_positive`` and ``accepted_risk`` suppress, and the high/critical
#: human-confirmation hold rides on exactly this set.
SUPPRESSING_STATUSES = frozenset({FALSE_POSITIVE, ACCEPTED_RISK})

# ---------------------------------------------------------------------------
# Layer 2 — lifecycle / presentation states (what a case *is* at a glance)
# ---------------------------------------------------------------------------

OPEN = "open"
RESOLVED = "resolved"
# VERIFIED, ACCEPTED_RISK, IN_PROGRESS reuse the same string tokens as the
# decision layer on purpose — they name the same human-visible state.

#: The canonical lifecycle states the dashboard renders.
LIFECYCLE_STATES = frozenset({OPEN, VERIFIED, IN_PROGRESS, ACCEPTED_RISK, RESOLVED})

#: The MCP presentation enum (coarse, diff-free). Backward compatible with the
#: original ``("open", "verified", "accepted_risk", "resolved")`` plus the new
#: ``in_progress`` beat. Re-exported as ``mcp_server.SUPPORTED_CASE_STATUSES``.
MCP_PRESENTATION_STATES = (OPEN, VERIFIED, IN_PROGRESS, ACCEPTED_RISK, RESOLVED)

# ---------------------------------------------------------------------------
# Layer 3 — scan-diff axis (a SEPARATE machine; namespaced to disambiguate)
# ---------------------------------------------------------------------------

DIFF_NEW = "new"
DIFF_RECURRING = "recurring"
DIFF_RESOLVED = "resolved"
#: How a case moved between two scans. This is NOT a lifecycle state — a case can
#: be diff ``recurring`` *and* lifecycle ``in_progress`` at the same time. The
#: ``DIFF_`` prefix keeps the word "resolved" from naming two machines at once.
DIFF_STATUSES = frozenset({DIFF_NEW, DIFF_RECURRING, DIFF_RESOLVED})

# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

#: Allowed lifecycle transitions. A case starts ``open``. A human can verify it,
#: accept its risk, mark it a false positive (→ ``resolved``), or record a fix
#: applied (→ ``in_progress``, awaiting rescan proof). From ``in_progress`` a
#: rescan that no longer finds the case proves closure (→ ``resolved``); a rescan
#: that still finds it stays ``in_progress``. Any state can be reopened to
#: ``open``; a ``resolved`` case that recurs reopens (→ ``open`` /
#: ``in_progress``). Mirrors the rotation state machine's "in-flight → verify →
#: terminal" shape (see ``rotation.ROTATION_INFLIGHT_STATUSES``).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    OPEN: frozenset({VERIFIED, IN_PROGRESS, ACCEPTED_RISK, RESOLVED}),
    VERIFIED: frozenset({IN_PROGRESS, ACCEPTED_RISK, RESOLVED, OPEN}),
    IN_PROGRESS: frozenset({RESOLVED, ACCEPTED_RISK, VERIFIED, OPEN}),
    ACCEPTED_RISK: frozenset({OPEN, VERIFIED, IN_PROGRESS, RESOLVED}),
    RESOLVED: frozenset({OPEN, IN_PROGRESS}),
}


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def can_transition(source: str, target: str) -> bool:
    """Return whether moving a case from ``source`` to ``target`` is allowed."""
    return _norm(target) in ALLOWED_TRANSITIONS.get(_norm(source), frozenset())


# ---------------------------------------------------------------------------
# Presentation mappings (the one documented place the folds live)
# ---------------------------------------------------------------------------

#: Stored decision status → coarse MCP presentation label (diff-free fold). This
#: is the documented presentation mapping referenced in the module docstring's
#: table; ``mcp_server._case_status_label`` is driven by it rather than an
#: ad-hoc inline fold.
DECISION_PRESENTATION: dict[str, str] = {
    VERIFIED: VERIFIED,
    ACCEPTED_RISK: ACCEPTED_RISK,
    FALSE_POSITIVE: RESOLVED,
    FIXED: RESOLVED,
    IN_PROGRESS: IN_PROGRESS,
}


def mcp_status_label(decision_status: Any, *, change_status: Any = None) -> str:
    """Coarse MCP presentation label for a case.

    Mirrors the historical ``_case_status_label`` fold: a case with no decision
    reads ``open``; ``fixed`` and ``false_positive`` fold to ``resolved``. The
    optional ``change_status`` is accepted for callers that want a rescan that
    closed an undecided case to read ``resolved`` rather than ``open`` — MCP
    itself keeps the legacy "no decision → open" behaviour by not passing it.
    """
    status = _norm(decision_status)
    if not status:
        return RESOLVED if _norm(change_status) == DIFF_RESOLVED else OPEN
    return DECISION_PRESENTATION.get(status, OPEN)


def lifecycle_state(decision_status: Any, *, diff_status: Any = None) -> str:
    """Resolve a case's rich, diff-aware canonical lifecycle state.

    Used where the scan-diff axis is available (dashboard / storage). Unlike the
    coarse MCP fold, this surfaces the ``in_progress`` (verifying) beat: a
    ``fixed`` decision on a case that still appears is "awaiting rescan proof",
    and a rescan that no longer finds the case (``diff_status == DIFF_RESOLVED``)
    is closure proof regardless of whether a human recorded a decision.
    """
    status = _norm(decision_status)
    if _norm(diff_status) == DIFF_RESOLVED:
        return RESOLVED
    if status == FALSE_POSITIVE:
        return RESOLVED
    if status in (FIXED, IN_PROGRESS):
        return IN_PROGRESS
    if status == VERIFIED:
        return VERIFIED
    if status == ACCEPTED_RISK:
        return ACCEPTED_RISK
    return OPEN


def is_suppressing(decision_status: Any) -> bool:
    """Whether a decision status hides a case (false_positive / accepted_risk)."""
    return _norm(decision_status) in SUPPRESSING_STATUSES
