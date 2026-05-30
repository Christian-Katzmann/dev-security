"""Reset command: wipe a repo's observatory state for clean-slate testing.

Deletes per-repo rows from sqlite tables (transactionally), removes the report
directory at ``~/.security-observatory/reports/<repo>/``, and optionally removes
the target repo's rotation scaffold files (``--include-rotation-scaffold``).

The confirmation phrase mirrors the Tier 5R structure from the rotation trigger.
"""
from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .rotation import history_file_path, receipts_dir, state_file_path
from .storage import ObservatoryDB


SCAN_RESULT_TABLES = [
    "findings",
    "sbom_components",
    "dependency_manifest_entries",
    "dependency_trust_enrichments",
    "platform_posture_snapshots",
    "case_decisions",
    "agent_lab_proposals",
    "scans",
]


def reset_confirmation_phrase(repo: str) -> str:
    return f"Yes, wipe `{repo}` and accept that this is irreversible."


def list_known_repos(db: ObservatoryDB) -> list[str]:
    rows = db.conn.execute(
        "SELECT DISTINCT repo_name FROM scans ORDER BY repo_name"
    ).fetchall()
    return [row["repo_name"] for row in rows]


def list_scan_result_repos(db: ObservatoryDB) -> list[str]:
    repos: set[str] = set()
    for table in SCAN_RESULT_TABLES:
        try:
            rows = db.conn.execute(f"SELECT DISTINCT repo_name FROM {table}").fetchall()
        except sqlite3.OperationalError:
            continue
        repos.update(str(row["repo_name"]) for row in rows if row["repo_name"])
    return sorted(repos)


def reset_scan_results_confirmation_phrase(scope: str, repo: str | None = None) -> str:
    if scope == "repo" and repo:
        return f"RESET SCAN RESULTS FOR {repo}"
    return "RESET ALL LOCAL SCAN RESULTS"


def plan_scan_results_reset(
    db: ObservatoryDB,
    home: Path,
    *,
    repos: list[str] | None = None,
) -> dict[str, Any]:
    target_repos = sorted(set(repos or list_scan_result_repos(db)))
    plan: dict[str, Any] = {
        "scope": "repo" if len(target_repos) == 1 else "all",
        "repos": target_repos,
        "tables": [],
        "files": [],
        "preserved": [
            "scanned repositories",
            "Honey Keys and Honey Key events",
            "managed tools and install records",
            "tool credentials and setup config",
            "DëvSec app settings",
        ],
    }
    if not target_repos:
        return plan

    for table in SCAN_RESULT_TABLES:
        try:
            count = _count_repo_rows(db, table, target_repos)
        except sqlite3.OperationalError:
            count = 0
        if count > 0:
            plan["tables"].append({"table": table, "rows": count})

    reports_root = home / "reports"
    for repo in target_repos:
        report_dir = reports_root / repo
        if report_dir.exists():
            plan["files"].append(str(_safe_report_dir(reports_root, repo)))
    return plan


def backup_scan_results(
    db: ObservatoryDB,
    home: Path,
    backup_dir: Path,
    *,
    repos: list[str] | None = None,
) -> dict[str, str]:
    target_repos = sorted(set(repos or list_scan_result_repos(db)))
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = _backup_label(target_repos[0]) if len(target_repos) == 1 else "all-scan-results"
    result: dict[str, str] = {}

    dump_path = backup_dir / f"{label}-{ts}.scan-results.json"
    _write_scan_results_dump(db, target_repos, dump_path)
    result["scan_results_json"] = str(dump_path)

    reports_root = home / "reports"
    report_dirs = [
        _safe_report_dir(reports_root, repo)
        for repo in target_repos
        if (reports_root / repo).exists()
    ]
    if report_dirs:
        tar_path = backup_dir / f"{label}-{ts}-reports.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            for report_dir in report_dirs:
                tar.add(report_dir, arcname=str(report_dir.relative_to(reports_root)))
        result["reports_tarball"] = str(tar_path)

    return result


def execute_scan_results_reset(
    db: ObservatoryDB,
    home: Path,
    *,
    repos: list[str] | None = None,
) -> dict[str, Any]:
    target_repos = sorted(set(repos or list_scan_result_repos(db)))
    deleted: dict[str, Any] = {"repos": target_repos, "tables": {}, "files": []}
    if not target_repos:
        return deleted

    with db.conn:
        for table in SCAN_RESULT_TABLES:
            cursor = _delete_repo_rows(db, table, target_repos)
            if cursor.rowcount:
                deleted["tables"][table] = cursor.rowcount

    reports_root = home / "reports"
    for repo in target_repos:
        report_dir = reports_root / repo
        if not report_dir.exists():
            continue
        safe_dir = _safe_report_dir(reports_root, repo)
        shutil.rmtree(safe_dir)
        deleted["files"].append(str(safe_dir))

    return deleted


def plan_reset(
    db: ObservatoryDB,
    repo: str,
    home: Path,
    *,
    include_rotation_scaffold: bool = False,
    repo_path: Path | None = None,
) -> dict[str, Any]:
    """Return a dry-run plan: what would be deleted, with row counts."""
    plan: dict[str, Any] = {"repo": repo, "tables": [], "files": []}

    tables_with_repo_filter = [
        "scans",
        "findings",
        "sbom_components",
        "dependency_manifest_entries",
        "dependency_trust_enrichments",
        "platform_posture_snapshots",
        "case_decisions",
        "agent_lab_proposals",
    ]
    for table in tables_with_repo_filter:
        try:
            row = db.conn.execute(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE repo_name = ?", (repo,)
            ).fetchone()
            count = row["cnt"] if row else 0
        except sqlite3.OperationalError:
            count = 0
        if count > 0:
            plan["tables"].append({"table": table, "rows": count})

    # honey_key_events scoped to this repo via the honey_keys.repo_id join
    try:
        row = db.conn.execute(
            """SELECT COUNT(*) as cnt FROM honey_key_events
               WHERE honey_key_id IN (SELECT id FROM honey_keys WHERE repo_id = ?)""",
            (repo,),
        ).fetchone()
        hke_count = row["cnt"] if row else 0
    except sqlite3.OperationalError:
        hke_count = 0
    if hke_count > 0:
        plan["tables"].append({"table": "honey_key_events (repo-scoped)", "rows": hke_count})

    try:
        row = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM honey_keys WHERE repo_id = ?", (repo,)
        ).fetchone()
        hk_count = row["cnt"] if row else 0
    except sqlite3.OperationalError:
        hk_count = 0
    if hk_count > 0:
        plan["tables"].append({"table": "honey_keys (repo-scoped)", "rows": hk_count})

    # security_project_status uses project_id, not repo_name — skip unless
    # the project_id matches the repo slug (it does for DëvSec's single-project repos)
    try:
        row = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM security_project_status WHERE project_id = ?",
            (repo,),
        ).fetchone()
        sps_count = row["cnt"] if row else 0
    except sqlite3.OperationalError:
        sps_count = 0
    if sps_count > 0:
        plan["tables"].append({"table": "security_project_status", "rows": sps_count})

    reports_dir = home / "reports" / repo
    if reports_dir.exists():
        plan["files"].append(str(reports_dir))

    if include_rotation_scaffold and repo_path:
        for path in _rotation_scaffold_paths(repo_path):
            if path.exists():
                plan["files"].append(str(path))

    return plan


def backup_repo_state(
    db: ObservatoryDB,
    repo: str,
    home: Path,
    backup_dir: Path,
    *,
    include_rotation_scaffold: bool = False,
    repo_path: Path | None = None,
) -> dict[str, str]:
    """Write a sqldump and reports tarball to ``backup_dir``.

    Returns paths to the created backup files.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result: dict[str, str] = {}

    dump_path = backup_dir / f"{repo}-{ts}.sqldump"
    _write_sqldump(db, repo, dump_path)
    result["sqldump"] = str(dump_path)

    reports_dir = home / "reports" / repo
    if reports_dir.exists():
        tar_path = backup_dir / f"{repo}-{ts}-reports.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(reports_dir, arcname=repo)
        result["reports_tarball"] = str(tar_path)

    if include_rotation_scaffold and repo_path:
        scaffold_paths = [p for p in _rotation_scaffold_paths(repo_path) if p.exists()]
        if scaffold_paths:
            scaffold_tar_path = backup_dir / f"{repo}-{ts}-rotation-scaffold.tar.gz"
            with tarfile.open(scaffold_tar_path, "w:gz") as tar:
                for path in scaffold_paths:
                    tar.add(path, arcname=str(path.relative_to(repo_path)))
            result["rotation_scaffold_tarball"] = str(scaffold_tar_path)

    return result


def execute_reset(
    db: ObservatoryDB,
    repo: str,
    home: Path,
    *,
    include_rotation_scaffold: bool = False,
    repo_path: Path | None = None,
) -> dict[str, Any]:
    """Execute the destructive reset. Returns a summary of what was deleted.

    All sqlite deletes happen in a single transaction. Filesystem operations
    follow. If a filesystem operation fails and no backup was taken, the
    function raises with a clear message (sqlite transaction is already committed
    at that point — the caller must have taken a backup first for full safety).
    """
    deleted: dict[str, Any] = {"tables": {}, "files": []}

    with db.conn:
        # Child tables first (no FK cascades declared in the schema)
        for child_table in (
            "findings",
            "sbom_components",
            "dependency_manifest_entries",
            "dependency_trust_enrichments",
            "platform_posture_snapshots",
        ):
            cursor = db.conn.execute(
                f"DELETE FROM {child_table} WHERE repo_name = ?", (repo,)
            )
            if cursor.rowcount:
                deleted["tables"][child_table] = cursor.rowcount

        cursor = db.conn.execute(
            "DELETE FROM case_decisions WHERE repo_name = ?", (repo,)
        )
        if cursor.rowcount:
            deleted["tables"]["case_decisions"] = cursor.rowcount

        cursor = db.conn.execute(
            "DELETE FROM agent_lab_proposals WHERE repo_name = ?", (repo,)
        )
        if cursor.rowcount:
            deleted["tables"]["agent_lab_proposals"] = cursor.rowcount

        # honey_key_events for repo-scoped honey keys
        cursor = db.conn.execute(
            """DELETE FROM honey_key_events
               WHERE honey_key_id IN (SELECT id FROM honey_keys WHERE repo_id = ?)""",
            (repo,),
        )
        if cursor.rowcount:
            deleted["tables"]["honey_key_events"] = cursor.rowcount

        cursor = db.conn.execute(
            "DELETE FROM honey_keys WHERE repo_id = ?", (repo,)
        )
        if cursor.rowcount:
            deleted["tables"]["honey_keys"] = cursor.rowcount

        cursor = db.conn.execute(
            "DELETE FROM security_project_status WHERE project_id = ?", (repo,)
        )
        if cursor.rowcount:
            deleted["tables"]["security_project_status"] = cursor.rowcount

        # Parent table last
        cursor = db.conn.execute(
            "DELETE FROM scans WHERE repo_name = ?", (repo,)
        )
        if cursor.rowcount:
            deleted["tables"]["scans"] = cursor.rowcount

    # Filesystem cleanup
    reports_dir = home / "reports" / repo
    if reports_dir.exists():
        shutil.rmtree(reports_dir)
        deleted["files"].append(str(reports_dir))

    if include_rotation_scaffold and repo_path:
        for path in _rotation_scaffold_paths(repo_path):
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                deleted["files"].append(str(path))
        _remove_rotate_npm_script(repo_path)

    return deleted


def _rotation_scaffold_paths(repo_path: Path) -> list[Path]:
    return [
        state_file_path(repo_path),
        history_file_path(repo_path),
        receipts_dir(repo_path),
        repo_path / "src" / "lib" / "rotation",
    ]


def _remove_rotate_npm_script(repo_path: Path) -> None:
    """Remove the 'rotate' script from package.json if present."""
    pkg_json = repo_path / "package.json"
    if not pkg_json.exists():
        return
    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    scripts = data.get("scripts")
    if isinstance(scripts, dict) and "rotate" in scripts:
        del scripts["rotate"]
        pkg_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_sqldump(db: ObservatoryDB, repo: str, dump_path: Path) -> None:
    """Write all rows for ``repo`` as a JSON dump (portable, no sqlite3 CLI needed)."""
    tables = [
        "scans",
        "findings",
        "sbom_components",
        "dependency_manifest_entries",
        "dependency_trust_enrichments",
        "platform_posture_snapshots",
        "case_decisions",
        "agent_lab_proposals",
    ]
    dump: dict[str, list[dict[str, Any]]] = {}
    for table in tables:
        try:
            rows = db.conn.execute(
                f"SELECT * FROM {table} WHERE repo_name = ?", (repo,)
            ).fetchall()
            dump[table] = [dict(row) for row in rows]
        except sqlite3.OperationalError:
            dump[table] = []

    # Repo-scoped honey keys + events
    try:
        hk_rows = db.conn.execute(
            "SELECT * FROM honey_keys WHERE repo_id = ?", (repo,)
        ).fetchall()
        dump["honey_keys"] = [dict(row) for row in hk_rows]
    except sqlite3.OperationalError:
        dump["honey_keys"] = []

    try:
        hke_rows = db.conn.execute(
            """SELECT * FROM honey_key_events
               WHERE honey_key_id IN (SELECT id FROM honey_keys WHERE repo_id = ?)""",
            (repo,),
        ).fetchall()
        dump["honey_key_events"] = [dict(row) for row in hke_rows]
    except sqlite3.OperationalError:
        dump["honey_key_events"] = []

    try:
        sps_rows = db.conn.execute(
            "SELECT * FROM security_project_status WHERE project_id = ?", (repo,)
        ).fetchall()
        dump["security_project_status"] = [dict(row) for row in sps_rows]
    except sqlite3.OperationalError:
        dump["security_project_status"] = []

    dump_path.write_text(json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _repo_placeholders(repos: list[str]) -> str:
    return ",".join("?" for _ in repos)


def _backup_label(repo: str) -> str:
    clean = "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in repo)
    return clean.strip("-") or "repo"


def _count_repo_rows(db: ObservatoryDB, table: str, repos: list[str]) -> int:
    row = db.conn.execute(
        f"SELECT COUNT(*) as cnt FROM {table} WHERE repo_name IN ({_repo_placeholders(repos)})",
        tuple(repos),
    ).fetchone()
    return int(row["cnt"] if row else 0)


def _delete_repo_rows(db: ObservatoryDB, table: str, repos: list[str]) -> sqlite3.Cursor:
    return db.conn.execute(
        f"DELETE FROM {table} WHERE repo_name IN ({_repo_placeholders(repos)})",
        tuple(repos),
    )


def _write_scan_results_dump(db: ObservatoryDB, repos: list[str], dump_path: Path) -> None:
    dump: dict[str, list[dict[str, Any]]] = {}
    if not repos:
        for table in SCAN_RESULT_TABLES:
            dump[table] = []
        dump_path.write_text(json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    for table in SCAN_RESULT_TABLES:
        try:
            rows = db.conn.execute(
                f"SELECT * FROM {table} WHERE repo_name IN ({_repo_placeholders(repos)})",
                tuple(repos),
            ).fetchall()
            dump[table] = [dict(row) for row in rows]
        except sqlite3.OperationalError:
            dump[table] = []
    dump_path.write_text(json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_report_dir(reports_root: Path, repo: str) -> Path:
    root = reports_root.resolve()
    target = (reports_root / repo).resolve()
    if target == root or root not in target.parents:
        raise ValueError("Refusing to delete a report path outside the DëvSec reports directory.")
    return target
