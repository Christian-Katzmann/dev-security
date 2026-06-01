"""Direct state-machine tests for the canonical case lifecycle (S-035 seam).

``lifecycle.py`` is the single source of truth for the states a case can hold and
the transitions between them. These tests pin the state machine itself —
``ALLOWED_TRANSITIONS`` / ``can_transition`` and the diff-aware ``lifecycle_state``
verifying-beat fold — independently of any storage or MCP surface that consumes it.
"""

import pytest

from security_observatory import lifecycle as lc


# ---------------------------------------------------------------------------
# Vocabulary sanity — the constants the rest of the system derives from.
# ---------------------------------------------------------------------------


def test_decision_statuses_are_the_documented_five():
    assert lc.DECISION_STATUSES == frozenset(
        {"verified", "false_positive", "accepted_risk", "fixed", "in_progress"}
    )


def test_only_false_positive_and_accepted_risk_suppress():
    # Adding in_progress (S-035) must never change which states hide a case.
    assert lc.SUPPRESSING_STATUSES == frozenset({"false_positive", "accepted_risk"})
    assert lc.IN_PROGRESS not in lc.SUPPRESSING_STATUSES
    assert lc.is_suppressing(lc.FALSE_POSITIVE)
    assert lc.is_suppressing(lc.ACCEPTED_RISK)
    assert not lc.is_suppressing(lc.IN_PROGRESS)
    assert not lc.is_suppressing(lc.VERIFIED)


def test_lifecycle_states_are_the_documented_five():
    assert lc.LIFECYCLE_STATES == frozenset(
        {"open", "verified", "in_progress", "accepted_risk", "resolved"}
    )


# ---------------------------------------------------------------------------
# ALLOWED_TRANSITIONS structural invariants.
# ---------------------------------------------------------------------------


def test_transition_graph_only_references_lifecycle_states():
    # Every source and every target must be a real lifecycle state — a typo'd
    # node would otherwise be an unreachable / dead transition.
    assert set(lc.ALLOWED_TRANSITIONS) == set(lc.LIFECYCLE_STATES)
    for source, targets in lc.ALLOWED_TRANSITIONS.items():
        assert targets <= lc.LIFECYCLE_STATES, source
        assert source not in targets, f"{source} should not list a self-transition"


def test_resolved_only_reopens_to_open_or_in_progress():
    # A closed case can only be reopened or re-enter the verifying beat; it cannot
    # jump straight back to verified / accepted_risk without reopening first.
    assert lc.ALLOWED_TRANSITIONS[lc.RESOLVED] == frozenset({lc.OPEN, lc.IN_PROGRESS})


@pytest.mark.parametrize(
    "source,target",
    [
        ("open", "verified"),
        ("open", "in_progress"),
        ("open", "accepted_risk"),
        ("open", "resolved"),
        ("verified", "in_progress"),
        ("verified", "resolved"),
        ("verified", "open"),
        ("in_progress", "resolved"),
        ("in_progress", "verified"),
        ("accepted_risk", "open"),
        ("accepted_risk", "resolved"),
        ("resolved", "open"),
        ("resolved", "in_progress"),
    ],
)
def test_allowed_transitions_are_accepted(source, target):
    assert lc.can_transition(source, target) is True


@pytest.mark.parametrize(
    "source,target",
    [
        ("open", "open"),            # no self-transition
        ("resolved", "verified"),     # must reopen before re-verifying
        ("resolved", "accepted_risk"),
        ("resolved", "resolved"),
        ("verified", "verified"),
        ("bogus", "open"),            # unknown source
        ("open", "bogus"),            # unknown target
        ("", "open"),                 # empty source
    ],
)
def test_rejected_transitions_are_refused(source, target):
    assert lc.can_transition(source, target) is False


def test_can_transition_normalizes_case_and_whitespace():
    assert lc.can_transition("  OPEN ", "Verified") is True
    assert lc.can_transition("Resolved", " VERIFIED ") is False


# ---------------------------------------------------------------------------
# The diff-aware lifecycle_state fold — the verifying beat.
# ---------------------------------------------------------------------------


def test_fixed_but_still_present_is_the_in_progress_verifying_beat():
    # A 'fixed' decision on a case that still appears (no closing rescan) is
    # "awaiting rescan proof" — it folds to in_progress, NOT resolved.
    assert lc.lifecycle_state(lc.FIXED) == lc.IN_PROGRESS
    assert lc.lifecycle_state(lc.FIXED, diff_status=lc.DIFF_RECURRING) == lc.IN_PROGRESS
    assert lc.lifecycle_state(lc.IN_PROGRESS) == lc.IN_PROGRESS


def test_closing_rescan_proves_resolution_regardless_of_decision():
    # diff 'resolved' (a rescan no longer finds the case) is closure proof and
    # overrides everything, including an undecided or fixed case.
    assert lc.lifecycle_state(None, diff_status=lc.DIFF_RESOLVED) == lc.RESOLVED
    assert lc.lifecycle_state(lc.FIXED, diff_status=lc.DIFF_RESOLVED) == lc.RESOLVED
    assert lc.lifecycle_state(lc.VERIFIED, diff_status=lc.DIFF_RESOLVED) == lc.RESOLVED


def test_remaining_decision_folds():
    assert lc.lifecycle_state(lc.FALSE_POSITIVE) == lc.RESOLVED
    assert lc.lifecycle_state(lc.VERIFIED) == lc.VERIFIED
    assert lc.lifecycle_state(lc.ACCEPTED_RISK) == lc.ACCEPTED_RISK
    assert lc.lifecycle_state(None) == lc.OPEN
    assert lc.lifecycle_state("") == lc.OPEN


def test_every_lifecycle_state_is_reachable_through_the_fold():
    produced = {
        lc.lifecycle_state(None),
        lc.lifecycle_state(lc.VERIFIED),
        lc.lifecycle_state(lc.IN_PROGRESS),
        lc.lifecycle_state(lc.ACCEPTED_RISK),
        lc.lifecycle_state(lc.FALSE_POSITIVE),
    }
    assert produced == set(lc.LIFECYCLE_STATES)
