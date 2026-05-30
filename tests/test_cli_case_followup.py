from __future__ import annotations

import json
from pathlib import Path

from security_observatory.case_followup import SCHEMA_VERSION
from security_observatory.cases import build_security_cases
from security_observatory.cli import main
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


def test_cases_prompt_command_prints_followup_prompt(tmp_path: Path, monkeypatch, capsys):
    _seed_home(tmp_path)
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(tmp_path))

    code = main(["cases", "prompt", "--repo", "repo", "--action", "verify_findings", "--scope", "critical"])

    out = capsys.readouterr().out
    assert code == 0
    assert "# AI case follow-up" in out
    assert SCHEMA_VERSION in out


def test_cases_import_resolutions_preview_and_apply(tmp_path: Path, monkeypatch, capsys):
    case_id = _seed_home(tmp_path)
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(tmp_path))
    input_path = tmp_path / "resolution.json"
    input_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "repo": "repo",
                "scan_id": "repo-20260101T000000Z",
                "action": "verify_findings",
                "scope": "critical",
                "summary": {"cases_reviewed": 1},
                "resolutions": [
                    {
                        "case_id": case_id,
                        "disposition": "confirmed_real",
                        "confidence": "high",
                        "reason": "The risky code is reachable in the application.",
                        "evidence": [{"path": "app.py", "line": 2, "interpretation": "live code path"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    preview_code = main(["cases", "import-resolutions", "--repo", "repo", "--input", str(input_path), "--preview"])
    preview_out = capsys.readouterr().out
    apply_code = main(["cases", "import-resolutions", "--repo", "repo", "--input", str(input_path), "--apply"])
    apply_out = capsys.readouterr().out

    assert preview_code == 0
    assert "Previewed 1 case resolution" in preview_out
    assert apply_code == 0
    assert "Applied 1 case resolution" in apply_out

    db = ObservatoryDB(tmp_path / "db" / "observatory.sqlite")
    try:
        assert db.case_decisions_map()[case_id]["status"] == "verified"
    finally:
        db.close()


def _seed_home(home: Path) -> str:
    db_path = home / "db" / "observatory.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    finding = Finding(repo="repo", scanner="semgrep", severity="critical", category="code-security", title="Unsafe SQL", file="app.py", line=2)
    cases = build_security_cases([finding], [{"scanner": "semgrep", "available": True, "findings": 1}], {"repo": "repo", "repo_path": str(home), "scan_id": "repo-20260101T000000Z"})
    db = ObservatoryDB(db_path)
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path=str(home),
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="quick",
            health_score=70,
            status="ok",
            scanner_statuses=[{"scanner": "semgrep", "available": True, "findings": 1}],
            findings=[finding],
            report_path=str(home / "normalized-report.json"),
            cases=cases,
        )
    finally:
        db.close()
    return cases[0].case_id
