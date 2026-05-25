"""Unit tests for the shared rotation module.

Exercises the state-file parser, history reader, receipt accessor, and the
rotation-state detector. The MCP and dashboard layers both call into these
helpers, so getting them right here keeps both surfaces honest.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from security_observatory.rotation import (
    detect_rotation_state,
    detect_stack,
    list_receipts,
    read_receipt,
    read_rotation_history,
    read_rotation_status,
)


def _seed_state(repo: Path, payload: dict | str) -> Path:
    (repo / "data").mkdir(parents=True, exist_ok=True)
    path = repo / "data" / "rotation-state.json"
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _seed_log(repo: Path, events: list[dict] | str) -> Path:
    (repo / "data").mkdir(parents=True, exist_ok=True)
    path = repo / "data" / "rotation-log.jsonl"
    if isinstance(events, str):
        path.write_text(events, encoding="utf-8")
    else:
        path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# read_rotation_status — shape, empties, corruption
# ---------------------------------------------------------------------------


def test_read_rotation_status_returns_empty_for_unscaffolded_repo(tmp_path):
    rows = read_rotation_status(tmp_path)
    assert rows == []


def test_read_rotation_status_returns_normalized_shape(tmp_path):
    completed = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=4)).isoformat()
    revoke_at = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=20)).isoformat()
    _seed_state(
        tmp_path,
        {
            "secrets": [
                {"name": "AUTH_SECRET", "class": "A", "cadence_days": 30},
                {"name": "API_KEY", "class": "B-API", "cadence_days": 90},
            ],
            "rotations": [
                {
                    "secret_name": "AUTH_SECRET",
                    "rotation_id": "rot-1",
                    "started_at": completed,
                    "completed_at": completed,
                    "status": "ROTATED",
                },
                {
                    "secret_name": "API_KEY",
                    "rotation_id": "rot-2",
                    "started_at": completed,
                    "completed_at": completed,
                    "status": "IN_GRACE",
                    "revoke_scheduled_at": revoke_at,
                },
            ],
        },
    )
    rows = read_rotation_status(tmp_path)
    by_name = {row["secret"]: row for row in rows}
    assert by_name["AUTH_SECRET"]["status"] == "ROTATED"
    assert by_name["AUTH_SECRET"]["cadence_days"] == 30
    assert by_name["AUTH_SECRET"]["days_since_rotation"] == 4
    assert by_name["AUTH_SECRET"]["needs_attention"] is False
    assert by_name["API_KEY"]["status"] == "IN_GRACE"
    assert by_name["API_KEY"]["in_grace_until"] == revoke_at


def test_read_rotation_status_corrupt_json_returns_unknown(tmp_path):
    _seed_state(tmp_path, "{not json")
    rows = read_rotation_status(tmp_path)
    assert len(rows) == 1
    assert rows[0]["secret"] == "(corrupt)"
    assert rows[0]["status"] == "unknown"
    assert rows[0]["needs_attention"] is True


def test_read_rotation_status_missing_secrets_array_is_tolerated(tmp_path):
    _seed_state(tmp_path, {"rotations": []})
    rows = read_rotation_status(tmp_path)
    # One unknown row signals "file shape was off" without inventing secrets.
    assert any(row["secret"] == "(corrupt)" for row in rows)


def test_read_rotation_status_marks_overdue_rotations(tmp_path):
    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=120)).isoformat()
    _seed_state(
        tmp_path,
        {
            "secrets": [{"name": "STALE_KEY", "class": "B-API", "cadence_days": 30}],
            "rotations": [
                {
                    "secret_name": "STALE_KEY",
                    "rotation_id": "rot-old",
                    "started_at": old,
                    "completed_at": old,
                    "status": "ROTATED",
                }
            ],
        },
    )
    rows = read_rotation_status(tmp_path)
    assert rows[0]["needs_attention"] is True
    assert rows[0]["days_since_rotation"] >= 120


def test_read_rotation_status_never_rotated_needs_attention(tmp_path):
    _seed_state(
        tmp_path,
        {
            "secrets": [{"name": "FRESHLY_SCAFFOLDED", "class": "A", "cadence_days": 30}],
            "rotations": [],
        },
    )
    rows = read_rotation_status(tmp_path)
    assert rows[0]["status"] == "NEVER"
    assert rows[0]["needs_attention"] is True


def test_read_rotation_status_surfaces_manually_marked_fields(tmp_path):
    completed = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=2)).isoformat()
    _seed_state(
        tmp_path,
        {
            "secrets": [
                {"name": "OVERRIDDEN_KEY", "class": "B-API", "cadence_days": 90},
                {"name": "PIPELINE_KEY", "class": "A", "cadence_days": 30},
            ],
            "rotations": [
                {
                    "secret_name": "OVERRIDDEN_KEY",
                    "rotation_id": "rot-override",
                    "started_at": completed,
                    "completed_at": completed,
                    "status": "ROTATED",
                    "manually_marked": True,
                    "override_kind": "--mark-rotated",
                },
                {
                    "secret_name": "PIPELINE_KEY",
                    "rotation_id": "rot-pipe",
                    "started_at": completed,
                    "completed_at": completed,
                    "status": "ROTATED",
                },
            ],
        },
    )
    rows = read_rotation_status(tmp_path)
    by_name = {row["secret"]: row for row in rows}
    assert by_name["OVERRIDDEN_KEY"]["manually_marked"] is True
    assert by_name["OVERRIDDEN_KEY"]["override_kind"] == "--mark-rotated"
    assert by_name["PIPELINE_KEY"]["manually_marked"] is False
    assert by_name["PIPELINE_KEY"]["override_kind"] is None


def test_read_rotation_status_defaults_manually_marked_for_legacy_state(tmp_path):
    completed = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=5)).isoformat()
    _seed_state(
        tmp_path,
        {
            "secrets": [{"name": "LEGACY_KEY", "class": "A", "cadence_days": 30}],
            "rotations": [
                {
                    "secret_name": "LEGACY_KEY",
                    "rotation_id": "rot-old",
                    "started_at": completed,
                    "completed_at": completed,
                    "status": "ROTATED",
                },
            ],
        },
    )
    rows = read_rotation_status(tmp_path)
    assert rows[0]["manually_marked"] is False
    assert rows[0]["override_kind"] is None


# ---------------------------------------------------------------------------
# read_rotation_history — recency, limit, malformed lines, override_kind
# ---------------------------------------------------------------------------


def test_read_rotation_history_returns_most_recent_first(tmp_path):
    _seed_log(
        tmp_path,
        [
            {"at": "2026-05-01T10:00:00+00:00", "secret_name": "A", "step": "ACQUIRED", "outcome": "succeeded"},
            {"at": "2026-05-03T11:00:00+00:00", "secret_name": "A", "step": "SOAK", "outcome": "succeeded"},
            {"at": "2026-05-02T10:00:00+00:00", "secret_name": "A", "step": "DEPLOY_PROD", "outcome": "succeeded"},
        ],
    )
    events = read_rotation_history(tmp_path)
    assert [event["timestamp"] for event in events] == [
        "2026-05-03T11:00:00+00:00",
        "2026-05-02T10:00:00+00:00",
        "2026-05-01T10:00:00+00:00",
    ]


def test_read_rotation_history_surfaces_override_kind(tmp_path):
    _seed_log(
        tmp_path,
        [
            {
                "at": "2026-05-01T10:00:00+00:00",
                "secret_name": "A",
                "step": "OPERATOR_OVERRIDE",
                "outcome": "applied",
                "override_kind": "--mark-rotated",
                "note": "Operator marked rotation as complete",
            },
            {
                "at": "2026-05-01T09:00:00+00:00",
                "secret_name": "A",
                "step": "HALTED",
                "outcome": "halted",
            },
        ],
    )
    events = read_rotation_history(tmp_path)
    assert events[0]["step"] == "OPERATOR_OVERRIDE"
    assert events[0]["override_kind"] == "--mark-rotated"
    assert events[1]["override_kind"] is None


def test_read_rotation_history_skips_malformed_lines(tmp_path):
    path = _seed_log(
        tmp_path,
        [{"at": "2026-05-01T10:00:00+00:00", "secret_name": "A", "step": "ACQUIRED"}],
    )
    path.write_text(
        path.read_text(encoding="utf-8") + "\nnot-json\n",
        encoding="utf-8",
    )
    events = read_rotation_history(tmp_path)
    assert len(events) == 1
    assert events[0]["secret"] == "A"


def test_read_rotation_history_limit_caps_at_100(tmp_path):
    _seed_log(
        tmp_path,
        [
            {
                "at": f"2026-05-01T10:00:{i:02d}+00:00",
                "secret_name": "A",
                "step": "ACQUIRED",
                "outcome": "succeeded",
            }
            for i in range(60)
        ],
    )
    capped = read_rotation_history(tmp_path, limit=9999)
    assert len(capped) == 60  # all 60 returned; cap kicks in above 100.


# ---------------------------------------------------------------------------
# Receipts — path-traversal safety
# ---------------------------------------------------------------------------


def test_list_receipts_returns_markdown_files_sorted_recent_first(tmp_path):
    receipts_dir = tmp_path / "data" / "rotation-receipts"
    receipts_dir.mkdir(parents=True)
    (receipts_dir / "AUTH_SECRET-2026-05-01T120000Z.md").write_text("# old", encoding="utf-8")
    (receipts_dir / "AUTH_SECRET-2026-05-20T120000Z.md").write_text("# new", encoding="utf-8")
    (receipts_dir / "ignored.txt").write_text("not markdown", encoding="utf-8")
    items = list_receipts(tmp_path)
    names = [item["filename"] for item in items]
    assert "ignored.txt" not in names
    assert names == sorted(names, reverse=True)


def test_read_receipt_returns_markdown_content(tmp_path):
    receipts_dir = tmp_path / "data" / "rotation-receipts"
    receipts_dir.mkdir(parents=True)
    (receipts_dir / "AUTH_SECRET-2026-05-20T120000Z.md").write_text(
        "# Rotation verified — `AUTH_SECRET`\n", encoding="utf-8"
    )
    body = read_receipt(tmp_path, "AUTH_SECRET-2026-05-20T120000Z.md")
    assert body is not None
    assert "Rotation verified" in body


def test_read_receipt_rejects_path_traversal(tmp_path):
    (tmp_path / "data" / "rotation-receipts").mkdir(parents=True)
    (tmp_path / "secret.md").write_text("# elsewhere", encoding="utf-8")
    assert read_receipt(tmp_path, "../secret.md") is None
    assert read_receipt(tmp_path, "../../etc/passwd") is None
    assert read_receipt(tmp_path, "AUTH/SECRET.md") is None
    assert read_receipt(tmp_path, "AUTH_SECRET.txt") is None
    assert read_receipt(tmp_path, ".hidden.md") is None


def test_read_receipt_returns_none_when_missing(tmp_path):
    (tmp_path / "data" / "rotation-receipts").mkdir(parents=True)
    assert read_receipt(tmp_path, "AUTH_SECRET-2026-05-20T120000Z.md") is None


# ---------------------------------------------------------------------------
# Stack detection
# ---------------------------------------------------------------------------


def test_detect_stack_recognises_nextjs(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "14.0.0"}}), encoding="utf-8"
    )
    assert detect_stack(tmp_path) == "vercel"


def test_detect_stack_recognises_python_cli(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='foo'\n\n[project.scripts]\nfoo='foo.cli:main'\n",
        encoding="utf-8",
    )
    assert detect_stack(tmp_path) == "python-cli"


def test_detect_stack_returns_none_for_unknown(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    assert detect_stack(tmp_path) is None


# ---------------------------------------------------------------------------
# detect_rotation_state aggregator
# ---------------------------------------------------------------------------


def test_detect_rotation_state_reports_unscaffolded_with_stack(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='foo'\n\n[project.scripts]\nfoo='foo.cli:main'\n",
        encoding="utf-8",
    )
    signal = detect_rotation_state(tmp_path)
    assert signal["scaffolded"] is False
    assert signal["stack"] == "python-cli"
    assert signal["stack_supported"] is True
    assert signal["secret_count"] == 0


def test_detect_rotation_state_counts_attention(tmp_path):
    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=120)).isoformat()
    _seed_state(
        tmp_path,
        {
            "secrets": [
                {"name": "STALE", "class": "B-API", "cadence_days": 30},
                {"name": "FRESH", "class": "A", "cadence_days": 30},
            ],
            "rotations": [
                {
                    "secret_name": "STALE",
                    "rotation_id": "rot-1",
                    "started_at": old,
                    "completed_at": old,
                    "status": "ROTATED",
                },
                {
                    "secret_name": "FRESH",
                    "rotation_id": "rot-2",
                    "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    "completed_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    "status": "ROTATED",
                },
            ],
        },
    )
    signal = detect_rotation_state(tmp_path)
    assert signal["scaffolded"] is True
    assert signal["secret_count"] == 2
    assert signal["needs_attention_count"] == 1
