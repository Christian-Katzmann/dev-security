from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from argparse import Namespace
from datetime import datetime, timezone
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import uuid
import webbrowser

from .cases import build_recovery_playbooks, build_security_cases, scanner_evidence_gaps
from .agent_lab import (
    AGENT_PROPOSAL_MAX_BYTES,
    AgentLabExecutionError,
    AgentLabProposalValidationError,
    build_agent_context_payload,
    build_agent_execution_preview,
    proposal_from_import_payload,
    validate_agent_proposal,
)
from .decisions import assemble_suppression
from .discovery import discover_repos
from .docs_render import render_markdown
from .honey_keys import (
    DEFAULT_PLACEMENT_PATHS,
    build_decoy_snippets,
    extract_honey_key_from_request,
    generate_honey_key,
    hash_honey_key,
    honey_key_is_well_formed,
    open_url_is_valid,
    project_id_for_repo_path,
    sanitize_headers,
    summarize_body,
)
from .managed_tools import (
    ManagedToolInstallError,
    install_managed_tool_files,
    managed_tool_evidence,
    uninstall_managed_tool_files,
)
from .scanners import scan_profile_catalog, scanner_names_for_profile, security_pack_catalog, tool_catalog
from .storage import ObservatoryDB


CHECK_JOBS: dict[str, dict[str, object]] = {}
CHECK_JOBS_LOCK = threading.Lock()


SCANNER_LABELS = {
    "ai-static": "Inspecting AI and agent configuration",
    "install-hooks": "Classifying install-time package hooks",
    "workflow-audit": "Auditing GitHub Actions supply-chain surfaces",
    "semgrep": "Checking code vulnerability patterns",
    "gitleaks": "Looking for leaked secrets",
    "trufflehog": "Looking deeper for exposed credentials",
    "trivy": "Checking filesystem, dependencies, secrets, and config",
    "osv-scanner": "Checking open-source dependency advisories",
    "syft": "Building a dependency inventory",
    "grype": "Checking dependency vulnerability reachability",
    "checkov": "Reviewing infrastructure exposure",
    "medusa": "Checking AI agent and MCP attack paths",
    "legitify": "Checking connected platform posture",
}

CATEGORY_LABELS = {
    "code-security": "Code vulnerabilities",
    "secrets": "Leaked secrets",
    "dependencies": "Dependency risks",
    "iac": "Infrastructure exposure",
    "workflow": "Workflow surfaces",
    "install-hooks": "Install hooks",
    "platform-posture": "Platform posture",
    "supply-chain-ioc": "Named-campaign matches",
    "silent-upgrade": "Silent dependency changes",
    "ai-risk": "AI agent risks",
    "system": "System checks",
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dashboard_environment_signal() -> dict[str, Any]:
    """Runtime hints the dashboard needs to surface gates honestly.

    Mirrors scanners._legitify_token: any of these env vars satisfies the
    platform-posture token requirement. Stays in the server layer because
    storage shouldn't know about the runtime environment.
    """
    token_env_names = ("SCM_TOKEN", "SECURITY_OBSERVATORY_SCM_TOKEN", "LEGITIFY_TOKEN")
    scm_token_present = any((os.environ.get(name) or "").strip() for name in token_env_names)
    return {"scm_token_present": scm_token_present}


def job_snapshot(job_id: str) -> dict[str, object] | None:
    with CHECK_JOBS_LOCK:
        job = CHECK_JOBS.get(job_id)
        return dict(job) if job else None


def update_job(job_id: str, **updates: object) -> None:
    with CHECK_JOBS_LOCK:
        if job_id in CHECK_JOBS:
            CHECK_JOBS[job_id].update(updates)


def args_for_audits(audits: list[str]) -> Namespace:
    args = Namespace(
        quick="quick" in audits,
        code="code" in audits,
        ai="ai" in audits,
        deps="deps" in audits,
        secrets="secrets" in audits,
        iac="iac" in audits,
        platform_posture="platform-posture" in audits,
        full="full" in audits,
    )
    if not any((args.quick, args.code, args.ai, args.deps, args.secrets, args.iac, args.platform_posture, args.full)):
        args.quick = True
    return args


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, re.sub(r"[-_]+", " ", category).title())


def format_location(finding: dict[str, object]) -> str:
    file = finding.get("file") or "repository"
    line = finding.get("line")
    return f"{file}:{line}" if line else str(file)


def summarize_counts(findings: list[dict[str, object]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        value = str(finding.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _case_decisions_for_report(cases: list[dict[str, object]]) -> list[dict[str, object]]:
    return [case["decision"] for case in cases if isinstance(case.get("decision"), dict)]


def _suppression_view(
    scan: dict[str, object],
    cases: list[dict[str, object]],
    findings: list[dict[str, object]],
) -> dict[str, object]:
    if "active_findings" in scan or "active_cases" in scan or "suppressed_cases" in scan:
        active_cases = [case for case in list(scan.get("active_cases") or []) if isinstance(case, dict)]
        suppressed_cases = [case for case in list(scan.get("suppressed_cases") or []) if isinstance(case, dict)]
        annotated_cases = [case for case in list(scan.get("cases") or cases) if isinstance(case, dict)]
        active_findings = [finding for finding in list(scan.get("active_findings") or []) if isinstance(finding, dict)]
        suppressed_findings = [finding for finding in list(scan.get("suppressed_findings") or []) if isinstance(finding, dict)]
        annotated_findings = [finding for finding in list(scan.get("findings") or findings) if isinstance(finding, dict)]
        suppressed_counts = scan.get("suppressed_counts")
        return {
            "cases": annotated_cases,
            "active_cases": active_cases,
            "suppressed_cases": suppressed_cases,
            "findings": annotated_findings,
            "active_findings": active_findings,
            "suppressed_findings": suppressed_findings,
            "suppressed_counts": suppressed_counts if isinstance(suppressed_counts, dict) else {"cases": len(suppressed_cases), "findings": len(suppressed_findings), "reasons": []},
        }
    return assemble_suppression(cases, findings, _case_decisions_for_report(cases))


def raw_report_fallback(scan: dict[str, object]) -> dict[str, object]:
    findings = list(scan.get("findings", []))
    scanners = list(scan.get("scanners", []))
    scanner_dicts = [item for item in scanners if isinstance(item, dict)]
    cases = list(scan.get("cases") or [])
    if not cases:
        cases = [
            case.to_dict()
            for case in build_security_cases(
                findings,
                scanner_dicts,
                {"repo": scan.get("repo"), "repo_path": scan.get("repo_path"), "scan_id": scan.get("scan_id")},
            )
        ]
    suppression = _suppression_view(
        scan,
        [case for case in cases if isinstance(case, dict)],
        [finding for finding in findings if isinstance(finding, dict)],
    )
    active_findings = list(suppression["active_findings"])
    return {
        "scan_id": scan["scan_id"],
        "repo": scan["repo"],
        "repo_path": scan["repo_path"],
        "report_path": scan.get("report_path"),
        "started_at": scan["started_at"],
        "finished_at": scan.get("finished_at"),
        "profile": scan["profile"],
        "health_score": scan["health_score"],
        "status": scan["status"],
        "severity_counts": summarize_counts(active_findings, "severity"),
        "category_counts": summarize_counts(active_findings, "category"),
        "raw_severity_counts": summarize_counts([finding for finding in suppression["findings"] if isinstance(finding, dict)], "severity"),
        "raw_category_counts": summarize_counts([finding for finding in suppression["findings"] if isinstance(finding, dict)], "category"),
        "scanners": scanners,
        "evidence_gaps": scanner_evidence_gaps(scanner_dicts, profile=str(scan.get("profile") or "")),
        "cases": suppression["cases"],
        "active_cases": suppression["active_cases"],
        "suppressed_cases": suppression["suppressed_cases"],
        "findings": suppression["findings"],
        "active_findings": active_findings,
        "suppressed_findings": suppression["suppressed_findings"],
        "suppressed_counts": suppression["suppressed_counts"],
        "platform_posture": scan.get("platform_posture"),
    }


def raw_report_export(scan: dict[str, object]) -> bytes:
    fallback = raw_report_fallback(scan)
    report_path = Path(str(scan.get("report_path") or ""))
    if report_path.exists() and report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = None
        if isinstance(report, dict):
            for key in (
                "severity_counts",
                "category_counts",
                "raw_severity_counts",
                "raw_category_counts",
                "cases",
                "active_cases",
                "suppressed_cases",
                "findings",
                "active_findings",
                "suppressed_findings",
                "suppressed_counts",
            ):
                report[key] = fallback[key]
            report["evidence_gaps"] = fallback["evidence_gaps"]
            return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return (json.dumps(fallback, indent=2, sort_keys=True) + "\n").encode("utf-8")


def report_page(scan: dict[str, object], kind: str) -> str:
    if kind == "prompt":
        return prompt_report_page(scan)
    return raw_report_page(scan)


def prompt_report_page(scan: dict[str, object]) -> str:
    prompt = build_ai_prompt(scan)
    cases = _scan_cases(scan)
    case_cards = "\n".join(_case_card(case) for case in cases) or '<p class="muted">No cases were saved for this scan.</p>'
    download_prompt_url = f"/api/report?scanId={_url_text(scan.get('scan_id'))}&kind=prompt"
    raw_page_url = f"/report/?scanId={_url_text(scan.get('scan_id'))}&kind=raw"
    return _page_shell(
        title="AI Handoff Prompt",
        scan=scan,
        active="prompt",
        body=f"""
        <section class="hero">
          <p class="eyebrow">Agent-ready security handoff</p>
          <h1>AI Handoff Prompt</h1>
          <p class="lede">This page turns the local scan into a focused brief for an AI coding agent. It is generated locally from saved cases and findings.</p>
          <div class="actions">
            <a class="button primary" href="{download_prompt_url}">Download Markdown</a>
            <a class="button" href="{raw_page_url}">View Full Report</a>
          </div>
        </section>
        <section class="grid two">
          <div class="panel">
            <h2>What The Agent Gets</h2>
            <ul class="plain-list">
              <li>Case-first priorities, not a raw scanner dump.</li>
              <li>Evidence from the scanners that produced each case.</li>
              <li>Verification steps before any fix is trusted.</li>
              <li>Fix steps and guardrails for secrets, risky upgrades, and destructive changes.</li>
            </ul>
          </div>
          <div class="panel">
            <h2>Scan Snapshot</h2>
            {_summary_table(scan, len(cases))}
          </div>
        </section>
        <section class="panel">
          <h2>Cases In This Prompt</h2>
          <div class="case-stack">{case_cards}</div>
        </section>
        <section class="panel">
          <div class="section-head">
            <div>
              <h2>Prompt Text</h2>
              <p class="muted">Use this when handing the scan to an AI agent.</p>
            </div>
            <button class="button" type="button" onclick="copyPrompt()">Copy Prompt</button>
          </div>
          <pre id="prompt-text" class="prompt">{html.escape(prompt)}</pre>
        </section>
        <script>
          async function copyPrompt() {{
            const text = document.getElementById('prompt-text')?.innerText || '';
            await navigator.clipboard.writeText(text);
          }}
        </script>
        """,
    )


def raw_report_page(scan: dict[str, object]) -> str:
    raw_json = raw_report_export(scan).decode("utf-8", errors="replace")
    download_raw_url = f"/api/report?scanId={_url_text(scan.get('scan_id'))}&kind=raw"
    prompt_page_url = f"/report/?scanId={_url_text(scan.get('scan_id'))}&kind=prompt"
    return _page_shell(
        title="Full Security Report",
        scan=scan,
        active="raw",
        body=f"""
        <section class="hero compact">
          <p class="eyebrow">Complete local scan output</p>
          <h1>Full Report</h1>
          <p class="lede">This is the raw normalized report with cases, findings, scanner status, and evidence gaps. It is intentionally plain.</p>
          <div class="actions">
            <a class="button primary" href="{download_raw_url}">Download JSON</a>
            <a class="button" href="{prompt_page_url}">View AI Prompt</a>
          </div>
        </section>
        <section class="panel">
          <h2>Raw JSON</h2>
          <pre class="raw-json">{html.escape(raw_json)}</pre>
        </section>
        """,
    )


def _page_shell(*, title: str, scan: dict[str, object], active: str, body: str) -> str:
    repo = html.escape(str(scan.get("repo") or "repository"))
    scan_id = html.escape(str(scan.get("scan_id") or "unknown"))
    prompt_href = f"/report/?scanId={_url_text(scan.get('scan_id'))}&kind=prompt"
    raw_href = f"/report/?scanId={_url_text(scan.get('scan_id'))}&kind=raw"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)} - Security Observatory</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f2ed;
      --panel: rgba(255, 255, 255, 0.72);
      --ink: #111111;
      --muted: rgba(17, 17, 17, 0.58);
      --line: rgba(17, 17, 17, 0.12);
      --gold: #d4a62d;
      --code: #171717;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, rgba(212,166,45,0.12), transparent 34rem), var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    a {{ color: inherit; }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 1rem clamp(1rem, 4vw, 3rem);
      border-bottom: 1px solid var(--line);
      background: rgba(245, 242, 237, 0.92);
      backdrop-filter: blur(14px);
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      min-width: 0;
    }}
    .mark {{
      width: 2rem;
      height: 2rem;
      border: 1px solid var(--ink);
      display: grid;
      place-items: center;
      background: white;
      font-size: 0.8rem;
    }}
    .brand-text {{ min-width: 0; }}
    .brand-title {{
      font-size: 0.7rem;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--muted);
      white-space: nowrap;
    }}
    .brand-subtitle {{
      font-size: 0.85rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 54vw;
    }}
    .nav {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; justify-content: flex-end; }}
    .nav a, .button {{
      display: inline-flex;
      min-height: 2.25rem;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.58);
      padding: 0.55rem 0.8rem;
      text-decoration: none;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.68rem;
      letter-spacing: 0.13em;
      text-transform: uppercase;
      cursor: pointer;
    }}
    .nav a.active {{ border-color: var(--ink); box-shadow: inset 3px 0 0 var(--gold); }}
    .button.primary {{ background: var(--ink); border-color: var(--ink); color: white; }}
    main {{ width: min(1180px, calc(100% - 2rem)); margin: 0 auto; padding: 2rem 0 4rem; }}
    .hero {{
      border: 1px solid var(--line);
      background: var(--panel);
      padding: clamp(1.5rem, 4vw, 3rem);
      margin-bottom: 1rem;
    }}
    .hero.compact {{ padding-block: 2rem; }}
    .eyebrow {{
      margin: 0 0 0.8rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.68rem;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    h1 {{ margin: 0; font-size: clamp(2.2rem, 7vw, 5rem); line-height: 0.95; font-weight: 300; letter-spacing: -0.03em; }}
    h2 {{ margin: 0 0 0.9rem; font-size: 1.1rem; font-weight: 520; }}
    .lede {{ max-width: 48rem; color: var(--muted); line-height: 1.7; margin: 1rem 0 0; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 1.5rem; }}
    .grid {{ display: grid; gap: 1rem; margin-bottom: 1rem; }}
    .grid.two {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .panel {{
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 1.25rem;
      margin-bottom: 1rem;
    }}
    .section-head {{ display: flex; align-items: start; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }}
    .muted {{ color: var(--muted); line-height: 1.6; margin: 0; }}
    .plain-list {{ margin: 0; padding-left: 1.1rem; color: var(--muted); line-height: 1.75; }}
    .summary-table {{ display: grid; grid-template-columns: 11rem minmax(0, 1fr); gap: 0.6rem 1rem; font-size: 0.9rem; }}
    .summary-table dt {{ color: var(--muted); }}
    .summary-table dd {{ margin: 0; min-width: 0; overflow-wrap: anywhere; }}
    .case-stack {{ display: grid; gap: 0.75rem; }}
    .case-card {{ border: 1px solid var(--line); background: rgba(255,255,255,0.62); padding: 1rem; }}
    .case-meta {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.7rem; }}
    .pill {{
      border: 1px solid var(--line);
      background: #fbfbfb;
      padding: 0.25rem 0.45rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.62rem;
      letter-spacing: 0.13em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .pill.hot {{ border-color: rgba(212,166,45,0.55); color: #8a6400; }}
    .case-card h3 {{ margin: 0 0 0.55rem; font-size: 1rem; }}
    .case-card p {{ margin: 0.4rem 0; color: var(--muted); line-height: 1.6; }}
    .case-card ul {{ margin: 0.45rem 0 0; padding-left: 1.1rem; color: var(--muted); line-height: 1.6; }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border: 1px solid rgba(255,255,255,0.10);
      background: var(--code);
      color: #f4f4f4;
      padding: 1rem;
      overflow: auto;
      line-height: 1.55;
      font-size: 0.82rem;
    }}
    .prompt {{ max-height: none; }}
    .raw-json {{ min-height: 60vh; }}
    @media (max-width: 760px) {{
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .nav {{ justify-content: flex-start; }}
      .grid.two {{ grid-template-columns: 1fr; }}
      .section-head {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/" aria-label="Back to dashboard">
      <span class="mark">S</span>
      <span class="brand-text">
        <span class="brand-title">Security Observatory</span>
        <span class="brand-subtitle">{repo} / {scan_id}</span>
      </span>
    </a>
    <nav class="nav">
      <a href="/">Back To Dashboard</a>
      <a class="{'active' if active == 'prompt' else ''}" href="{prompt_href}">AI Prompt</a>
      <a class="{'active' if active == 'raw' else ''}" href="{raw_href}">Full Report</a>
    </nav>
  </header>
  <main>{body}</main>
</body>
</html>"""


def _scan_cases(scan: dict[str, object]) -> list[dict[str, object]]:
    case_source = scan.get("active_cases") if "active_cases" in scan else scan.get("cases")
    cases = [case for case in list(case_source or []) if isinstance(case, dict)]
    if cases:
        return sorted(cases, key=_case_sort_key)
    scanner_dicts = [item for item in list(scan.get("scanners", [])) if isinstance(item, dict)]
    finding_source = scan.get("active_findings") if "active_findings" in scan else scan.get("findings")
    findings = list(finding_source or [])
    return [
        case.to_dict()
        for case in build_security_cases(
            findings,
            scanner_dicts,
            {"repo": scan.get("repo"), "repo_path": scan.get("repo_path"), "scan_id": scan.get("scan_id")},
        )
    ]


def _case_sort_key(case: dict[str, object]) -> tuple[int, int, str]:
    return (
        {"fix_now": 0, "verify": 1, "watch": 2, "info": 3}.get(str(case.get("action_level")), 9),
        SEVERITY_ORDER.get(str(case.get("severity")), 99),
        str(case.get("title") or ""),
    )


def _case_card(case: dict[str, object]) -> str:
    title = html.escape(str(case.get("title") or "Security case"))
    risk = html.escape(str(case.get("plain_english_risk") or "This case may affect the safety or reliability of the project."))
    action = html.escape(str(case.get("action_level") or "verify").replace("_", " "))
    severity = html.escape(str(case.get("severity") or "medium"))
    confidence = html.escape(str(case.get("confidence") or "medium"))
    category = html.escape(category_label(str(case.get("category") or "unknown")))
    affected = [html.escape(str(item)) for item in case.get("affected_files", []) if item]
    fix_steps = [html.escape(str(item)) for item in case.get("fix_steps", []) if item]
    evidence = [item for item in case.get("evidence", []) if isinstance(item, dict)]
    evidence_items = "".join(
        f"<li>{html.escape(str(item.get('scanner') or 'scanner'))}: {html.escape(str(item.get('title') or 'finding'))} at {html.escape(str(item.get('location') or 'repository'))}</li>"
        for item in evidence[:5]
    )
    location_text = ", ".join(affected) if affected else "Repository"
    fix_items = "".join(f"<li>{step}</li>" for step in fix_steps[:4])
    return f"""
    <article class="case-card">
      <div class="case-meta">
        <span class="pill hot">{action}</span>
        <span class="pill">{severity}</span>
        <span class="pill">{confidence} confidence</span>
        <span class="pill">{category}</span>
      </div>
      <h3>{title}</h3>
      <p>{risk}</p>
      <p><strong>Affected place:</strong> {location_text}</p>
      {"<ul>" + evidence_items + "</ul>" if evidence_items else ""}
      {"<ul>" + fix_items + "</ul>" if fix_items else ""}
    </article>
    """


def _summary_table(scan: dict[str, object], case_count: int) -> str:
    finding_source = scan.get("active_findings") if "active_findings" in scan else scan.get("findings", [])
    suppressed_counts = scan.get("suppressed_counts") if isinstance(scan.get("suppressed_counts"), dict) else {}
    rows = [
        ("Repository", scan.get("repo")),
        ("Health score", scan.get("health_score")),
        ("Status", scan.get("status")),
        ("Profile", scan.get("profile")),
        ("Cases", case_count),
        ("Findings", len(list(finding_source or []))),
        ("Suppressed", suppressed_counts.get("findings", 0)),
        ("Finished", scan.get("finished_at") or "unknown"),
    ]
    return "<dl class=\"summary-table\">" + "".join(
        f"<dt>{html.escape(str(label))}</dt><dd>{html.escape(str(value))}</dd>" for label, value in rows
    ) + "</dl>"


def _url_text(value: object) -> str:
    from urllib.parse import quote

    return quote(str(value or ""), safe="")


def _docs_title(source: str, fallback: str) -> str:
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _docs_page_shell(*, title: str, body: str, source_path: str) -> str:
    safe_title = html.escape(title)
    safe_source = html.escape(source_path)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title} — DëvSec docs</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f2ed;
      --panel: rgba(255, 255, 255, 0.78);
      --ink: #111111;
      --muted: rgba(17, 17, 17, 0.62);
      --line: rgba(17, 17, 17, 0.12);
      --gold: #d4a62d;
      --code-bg: #171717;
      --code-fg: #f4f4f4;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, rgba(212,166,45,0.10), transparent 32rem), var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.7;
    }}
    a {{ color: inherit; text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    a:hover {{ text-decoration-color: var(--gold); }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 1rem clamp(1rem, 4vw, 3rem);
      border-bottom: 1px solid var(--line);
      background: rgba(245, 242, 237, 0.92);
      backdrop-filter: blur(14px);
    }}
    .brand {{ display: flex; align-items: center; gap: 0.75rem; min-width: 0; text-decoration: none; }}
    .mark {{
      width: 2rem; height: 2rem;
      border: 1px solid var(--ink);
      display: grid; place-items: center;
      background: white; font-size: 0.8rem;
    }}
    .brand-text {{ min-width: 0; }}
    .brand-title {{
      font-size: 0.7rem;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--muted);
      white-space: nowrap;
    }}
    .brand-subtitle {{
      font-size: 0.85rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 54vw;
    }}
    .nav a {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.58);
      padding: 0.55rem 0.8rem;
      text-decoration: none;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.68rem;
      letter-spacing: 0.13em;
      text-transform: uppercase;
    }}
    main {{ width: min(820px, calc(100% - 2rem)); margin: 0 auto; padding: 2.5rem 0 5rem; }}
    .eyebrow {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.68rem;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--muted);
      margin: 0 0 1.4rem;
    }}
    .doc {{
      background: var(--panel);
      border: 1px solid var(--line);
      padding: clamp(1.6rem, 4vw, 3rem);
    }}
    .doc h1 {{ font-size: clamp(2rem, 5vw, 3rem); line-height: 1.05; margin: 0 0 1.2rem; font-weight: 360; letter-spacing: -0.02em; }}
    .doc h2 {{ font-size: 1.45rem; margin: 2.4rem 0 0.8rem; font-weight: 520; letter-spacing: -0.01em; }}
    .doc h3 {{ font-size: 1.15rem; margin: 1.8rem 0 0.6rem; font-weight: 520; }}
    .doc h4, .doc h5, .doc h6 {{ font-size: 1rem; margin: 1.4rem 0 0.5rem; font-weight: 520; }}
    .doc p {{ margin: 0.9rem 0; }}
    .doc ul, .doc ol {{ margin: 0.9rem 0; padding-left: 1.4rem; }}
    .doc li {{ margin: 0.25rem 0; }}
    .doc li > ul, .doc li > ol {{ margin: 0.3rem 0; }}
    .doc blockquote {{
      margin: 1.2rem 0;
      padding: 0.5rem 1rem;
      border-left: 3px solid var(--gold);
      background: rgba(212,166,45,0.07);
      color: var(--muted);
    }}
    .doc hr {{ border: 0; border-top: 1px solid var(--line); margin: 2rem 0; }}
    .doc code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.86em;
      background: rgba(17,17,17,0.06);
      padding: 0.12rem 0.35rem;
      border-radius: 3px;
    }}
    .doc pre {{
      background: var(--code-bg);
      color: var(--code-fg);
      padding: 1rem 1.1rem;
      overflow: auto;
      font-size: 0.82rem;
      line-height: 1.55;
      border: 1px solid rgba(255,255,255,0.08);
      margin: 1.2rem 0;
    }}
    .doc pre code {{ background: transparent; padding: 0; border-radius: 0; color: inherit; font-size: inherit; }}
    .doc table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1.4rem 0;
      font-size: 0.92rem;
    }}
    .doc th, .doc td {{
      border: 1px solid var(--line);
      padding: 0.55rem 0.75rem;
      text-align: left;
      vertical-align: top;
    }}
    .doc th {{
      background: rgba(17,17,17,0.04);
      font-weight: 520;
    }}
    .source {{
      margin-top: 1.4rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.7rem;
      color: var(--muted);
      letter-spacing: 0.08em;
    }}
    @media (max-width: 760px) {{
      .topbar {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/" aria-label="Back to dashboard">
      <span class="mark">D</span>
      <span class="brand-text">
        <span class="brand-title">DëvSec docs</span>
        <span class="brand-subtitle">{safe_title}</span>
      </span>
    </a>
    <nav class="nav">
      <a href="/">Back to dashboard</a>
    </nav>
  </header>
  <main>
    <p class="eyebrow">In-app documentation</p>
    <article class="doc">{body}</article>
    <p class="source">Source: {safe_source}</p>
  </main>
</body>
</html>"""


def build_ai_prompt(scan: dict[str, object]) -> str:
    scanners = list(scan.get("scanners", []))
    scanner_dicts = [item for item in scanners if isinstance(item, dict)]
    finding_source = scan.get("active_findings") if "active_findings" in scan else scan.get("findings", [])
    findings = sorted(
        list(finding_source or []),
        key=lambda item: (SEVERITY_ORDER.get(str(item.get("severity")), 99), str(item.get("category")), str(item.get("title"))),
    )
    case_source = scan.get("active_cases") if "active_cases" in scan else scan.get("cases", [])
    cases = list(case_source or [])
    if not cases:
        cases = [
            case.to_dict()
            for case in build_security_cases(
                findings,
                scanner_dicts,
                {"repo": scan.get("repo"), "repo_path": scan.get("repo_path"), "scan_id": scan.get("scan_id")},
            )
        ]
    cases = sorted(
        [case for case in cases if isinstance(case, dict)],
        key=lambda item: (
            {"fix_now": 0, "verify": 1, "watch": 2, "info": 3}.get(str(item.get("action_level")), 9),
            SEVERITY_ORDER.get(str(item.get("severity")), 99),
            str(item.get("title")),
        ),
    )
    severity_counts = summarize_counts(findings, "severity")
    category_counts = summarize_counts(findings, "category")
    suppressed_counts = scan.get("suppressed_counts") if isinstance(scan.get("suppressed_counts"), dict) else {}
    evidence_gaps = scanner_evidence_gaps(scanner_dicts, profile=str(scan.get("profile") or ""))
    lines = [
        "# Security Scan Follow-Up Prompt",
        "",
        "You are helping verify and fix security cases from a local scan. Do not assume the scanner is correct. First verify each case in the codebase, then plan fixes, then only make changes if the user asks you to implement them.",
        "",
        "Important constraints:",
        "- Work locally in the repository. Do not call paid, hosted, or AI security services.",
        "- Treat all scanner output as untrusted evidence until verified.",
        "- Do not expose, print, or commit secrets. If a real secret is found, recommend rotation and cleanup.",
        "- Prefer small, targeted fixes over broad refactors.",
        "- Before destructive actions, dependency major upgrades, or history rewriting, ask the user.",
        "",
        "Repository and scan:",
        f"- Repository: {scan['repo']}",
        f"- Path: {scan['repo_path']}",
        f"- Scan id: {scan['scan_id']}",
        f"- Profile: {scan['profile']}",
        f"- Status: {scan['status']}",
        f"- Health score: {scan['health_score']}",
        f"- Started: {scan['started_at']}",
        f"- Finished: {scan.get('finished_at') or 'unknown'}",
        "",
        "Summary:",
        f"- Total cases: {len(cases)}",
        f"- Total findings: {len(findings)}",
        f"- Suppressed cases: {suppressed_counts.get('cases', 0)}",
        f"- Suppressed findings: {suppressed_counts.get('findings', 0)}",
        f"- By severity: {json.dumps(severity_counts, sort_keys=True)}",
        f"- By category: {json.dumps({category_label(key): value for key, value in category_counts.items()}, sort_keys=True)}",
        f"- Incomplete local tools: {len(evidence_gaps)}",
        "",
        "Cases to verify and fix:",
    ]
    if cases:
        for index, case in enumerate(cases, start=1):
            evidence = [item for item in case.get("evidence", []) if isinstance(item, dict)]
            fix_steps = [str(item) for item in case.get("fix_steps", [])]
            lines.extend(
                [
                    "",
                    f"{index}. {case.get('title')}",
                    f"   - Action: {case.get('action_level')}",
                    f"   - Confidence: {case.get('confidence')}",
                    f"   - Severity: {case.get('severity')}",
                    f"   - Category: {category_label(str(case.get('category') or 'unknown'))}",
                    f"   - Risk in plain English: {case.get('plain_english_risk')}",
                    f"   - Source scanners: {', '.join(case.get('scanners') or []) or 'unknown'}",
                    "   - Evidence:",
                ]
            )
            for item in evidence:
                lines.append(f"     - {item.get('scanner')}: {item.get('title')} at {item.get('location') or 'repository'}")
            if not evidence:
                lines.append("     - No scanner evidence was attached. Re-check the saved raw findings before acting.")
            recency = case.get("install_recency") if isinstance(case.get("install_recency"), dict) else {}
            surfaces = [str(item) for item in (case.get("rotation_surfaces") or []) if str(item).strip()]
            if recency:
                confidence = str(recency.get("confidence") or "unknown")
                last_signal = recency.get("last_install_signal_at") or "unknown"
                lines.append(f"   - Install recency: {confidence} (last local signal: {last_signal})")
                if confidence == "strong":
                    lines.append("   - Probably executed - rotate the following surfaces:")
                    if surfaces:
                        lines.extend([f"     - {surface}" for surface in surfaces])
                    else:
                        lines.append("     - No repo-specific credential surfaces were enumerated.")
                    lines.append("   - Rotation guardrails: rotate at the provider first, update local config last, never commit rotated values.")
                elif confidence in {"weak", "unknown"}:
                    lines.append("   - Rotation guidance: no rotation recommendation from local evidence; verify execution before touching credentials.")
            lines.extend(
                [
                    "   - Verification steps:",
                    "     - Inspect the referenced files and confirm this is real in this project.",
                    "     - Decide whether the risky path can actually be reached or abused.",
                    "   - Fix steps:",
                ]
            )
            if fix_steps:
                lines.extend([f"     - {step}" for step in fix_steps])
            else:
                lines.append("     - Choose the smallest safe fix after verification.")
            lines.append(f"   - Source fingerprints: {', '.join(case.get('source_fingerprints') or []) or 'none'}")
    else:
        lines.append("- No cases were saved for this scan. Verify that the selected checks ran successfully before treating the repo as clean.")
    if evidence_gaps:
        lines.extend(["", "Incomplete local tool evidence:"])
        for item in evidence_gaps:
            reason = item.get("reason") or "tool was not available"
            pack_pages = item.get("pack_pages") if isinstance(item.get("pack_pages"), list) else []
            pack_text = ", ".join(str(pack.get("label") or pack.get("id")) for pack in pack_pages if isinstance(pack, dict))
            tool_label = item.get("tool_label") or item.get("scanner")
            profile_hint = item.get("recommended_profile_id")
            recommendation = []
            if pack_text:
                recommendation.append(f"open {pack_text}")
            if tool_label:
                recommendation.append(f"check the {tool_label} tool page")
            if profile_hint:
                recommendation.append(f"rerun the {profile_hint} profile after setup")
            suffix = f" Recommended: {'; '.join(recommendation)}." if recommendation else ""
            lines.append(f"- {item.get('scanner')}: {reason}.{suffix}")
    lines.extend(
        [
            "",
            "Your task:",
            "1. Start with a short verification plan. Work case-first, not raw-finding-first.",
            "2. For each case, explain exactly how you will verify whether it is real or a false positive. Reference the file/path and line when available.",
            "3. After verification, propose a fix plan ordered by action level: fix_now first, then verify, watch, and info.",
            "4. Include the tests, commands, or manual checks that should be run after each fix.",
            "5. Call out any fix that may need product judgment, a dependency major upgrade, credential rotation, or deployment coordination.",
            "6. End with a concise next-action checklist.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_check_job(
    job_id: str,
    db_path: Path,
    repo_path: Path,
    args: Namespace,
    *,
    scanner_names: list[str] | None = None,
    agent_lab_proposal_id: str | None = None,
    agent_lab_preview: dict[str, Any] | None = None,
) -> None:
    from .cli import scan_repo

    scanners = list(dict.fromkeys(scanner_names or scanner_names_for_profile(args)))
    total = max(len(scanners), 1)
    update_job(
        job_id,
        status="running",
        progress=2,
        message="Preparing local scan",
        currentStep=None,
        startedAt=utc_now(),
    )

    def progress(event: dict[str, object]) -> None:
        index = int(event.get("index", 1))
        scanner = str(event.get("scanner", "scanner"))
        label = SCANNER_LABELS.get(scanner, scanner)
        if event.get("event") == "scanner_started":
            percent = max(5, round(((index - 1) / total) * 90))
            update_job(job_id, progress=percent, message=label, currentStep=label, currentScanner=scanner)
        else:
            percent = min(95, round((index / total) * 90))
            if event.get("error"):
                label = f"{label} skipped or incomplete"
            update_job(job_id, progress=percent, message=label, currentStep=label, currentScanner=scanner)

    try:
        scan = scan_repo(repo_path, args, db_path.parent.parent, progress_callback=progress, scanner_names=scanners)
        if agent_lab_proposal_id:
            _record_agent_lab_execution_result(
                db_path,
                agent_lab_proposal_id,
                agent_lab_preview or {},
                {
                    "job_id": job_id,
                    "mode": "approved_run",
                    "status": "complete",
                    "scan_id": scan.get("scan_id"),
                    "report_path": scan.get("report_path"),
                    "started_at": scan.get("started_at"),
                    "finished_at": scan.get("finished_at"),
                    "profile": scan.get("profile"),
                    "scanner_statuses": scan.get("scanners") or [],
                    "evidence_gaps": scan.get("evidence_gaps") or [],
                },
            )
        update_job(
            job_id,
            status="complete",
            progress=100,
            message="Check complete",
            currentStep=None,
            currentScanner=None,
            scan=scan,
            finishedAt=utc_now(),
        )
    except Exception as exc:
        if agent_lab_proposal_id:
            _record_agent_lab_execution_result(
                db_path,
                agent_lab_proposal_id,
                agent_lab_preview or {},
                {
                    "job_id": job_id,
                    "mode": "approved_run",
                    "status": "failed",
                    "error": str(exc),
                    "finished_at": utc_now(),
                },
            )
        update_job(
            job_id,
            status="failed",
            progress=100,
            message="Check failed",
            error=str(exc),
            currentStep=None,
            currentScanner=None,
            finishedAt=utc_now(),
        )


def _record_agent_lab_execution_result(
    db_path: Path,
    proposal_id: str,
    preview: dict[str, Any],
    execution: dict[str, Any],
) -> None:
    db = ObservatoryDB(db_path)
    try:
        proposal = db.get_agent_lab_proposal(proposal_id)
        if not proposal:
            return
        plan = dict(proposal.get("final_execution_plan") or {})
        plan.setdefault("version", "agent-lab.execution-plan.v1")
        plan["approval_state"] = proposal.get("approval_state")
        if preview:
            plan["last_preview"] = preview
        plan["last_execution"] = execution
        _update_agent_lab_plan_item_statuses(plan, execution)
        db.update_agent_lab_execution_plan(proposal_id=proposal_id, final_execution_plan=plan)
    finally:
        db.close()


def _update_agent_lab_plan_item_statuses(plan: dict[str, Any], execution: dict[str, Any]) -> None:
    items = plan.get("items")
    if not isinstance(items, list):
        return
    status = str(execution.get("status") or "")
    evidence_gaps = [item for item in execution.get("evidence_gaps") or [] if isinstance(item, dict)]
    scan_id = execution.get("scan_id")
    report_path = execution.get("report_path")
    item_status = {
        "queued": "queued_for_execution",
        "complete": "executed_with_evidence_gaps" if evidence_gaps else "executed",
        "failed": "execution_failed",
    }.get(status, status or "unknown")
    for item in items:
        if not isinstance(item, dict):
            continue
        item["status"] = item_status
        if scan_id:
            item["scan_id"] = scan_id
        if report_path:
            item["report_path"] = report_path


class DashboardHandler(SimpleHTTPRequestHandler):
    db_path: Path
    assets_dir: Path

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.assets_dir), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def send_json(self, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json_error(self, status: int, message: str, **extra: object) -> None:
        body = json.dumps({"error": message, **extra}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_accepted_json(self, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_no_content(self) -> None:
        self.send_response(204)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def send_html(self, html_body: str) -> None:
        body = html_body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_download(self, body: bytes, *, content_type: str, filename: str) -> None:
        safe_filename = re.sub(r"[^A-Za-z0-9_.-]+", "-", filename).strip("-") or "security-report"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_repo_doc(self, path: str) -> None:
        # docs/ lives at the repo root; the package sits at src/security_observatory/.
        repo_root = Path(__file__).resolve().parents[2]
        docs_root = (repo_root / "docs").resolve()
        candidate = (docs_root / path.removeprefix("/docs/")).resolve()
        if not candidate.is_file() or (docs_root not in candidate.parents and candidate != docs_root):
            self.send_error(404, "Doc not found.")
            return
        try:
            source = candidate.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404, "Doc not found.")
            return
        rendered = render_markdown(source)
        title = _docs_title(source, candidate.stem)
        page = _docs_page_shell(title=title, body=rendered, source_path=str(candidate.relative_to(repo_root)))
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/docs/") and parsed.path.endswith(".md"):
            self.serve_repo_doc(parsed.path)
            return
        if parsed.path == "/favicon.ico":
            icon_path = self.assets_dir / "favicon.png"
            if not icon_path.exists():
                self.send_response(204)
                self.end_headers()
                return
            body = icon_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/summary":
            db = ObservatoryDB(self.db_path)
            try:
                payload = db.dashboard_payload()
            finally:
                db.close()
            payload["environment"] = dashboard_environment_signal()
            payload["recovery_playbooks"] = build_recovery_playbooks(payload.get("active_cases") or [])
            self.send_json(payload)
            return
        if parsed.path == "/api/tool-catalog":
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            self.send_json({"items": tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)})
            return
        if parsed.path == "/api/security-packs":
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            self.send_json({"items": security_pack_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)})
            return
        if parsed.path == "/api/scan-profiles":
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            self.send_json({"items": scan_profile_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)})
            return
        if parsed.path == "/api/agent-lab/context":
            query = parse_qs(parsed.query)
            repo_path = query.get("repoPath", query.get("repo_path", [""]))[0] or None
            repo_name = query.get("repoName", query.get("repo_name", [""]))[0] or None
            db = ObservatoryDB(self.db_path)
            try:
                payload = build_agent_context_payload(db, repo_path=repo_path, repo_name=repo_name)
            finally:
                db.close()
            self.send_json(payload)
            return
        if parsed.path == "/api/agent-lab/proposals":
            query = parse_qs(parsed.query)
            repo_name = query.get("repoName", query.get("repo_name", [""]))[0] or None
            approval_state = query.get("approvalState", query.get("approval_state", [""]))[0] or None
            db = ObservatoryDB(self.db_path)
            try:
                proposals = db.list_agent_lab_proposals(repo_name=repo_name, approval_state=approval_state, limit=100)
            finally:
                db.close()
            self.send_json({"items": proposals})
            return
        if parsed.path == "/api/agent-lab/proposals/execution-preview":
            self.preview_agent_lab_proposal_execution(parsed)
            return
        if parsed.path == "/api/install-preview":
            query = parse_qs(parsed.query)
            tool_id = query.get("toolId", query.get("tool_id", [""]))[0]
            pack_id = query.get("packId", query.get("pack_id", [""]))[0]
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            if tool_id:
                catalog = tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
                item = next((tool for tool in catalog if tool.get("id") == tool_id), None)
                if not item:
                    self.send_error(404, "Tool not found.")
                    return
                self.send_json({"preview": item.get("install_preview"), "tool": item})
                return
            if pack_id:
                packs = security_pack_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
                item = next((pack for pack in packs if pack.get("id") == pack_id), None)
                if not item:
                    self.send_error(404, "Security Pack not found.")
                    return
                self.send_json({"preview": item.get("install_preview"), "pack": item})
                return
            self.send_error(400, "toolId or packId is required.")
            return
        if parsed.path == "/api/honey/keys":
            query = parse_qs(parsed.query)
            project_id = query.get("projectId", [""])[0] or None
            db = ObservatoryDB(self.db_path)
            try:
                self.send_json({"keys": db.list_honey_keys(project_id=project_id), "placement_paths": list(DEFAULT_PLACEMENT_PATHS)})
            finally:
                db.close()
            return
        if parsed.path.startswith("/api/honey/open/"):
            token_id = parsed.path.removeprefix("/api/honey/open/").strip("/")
            query = parse_qs(parsed.query)
            signature = query.get("sig", [""])[0]
            db = ObservatoryDB(self.db_path)
            try:
                signing_secret = db.honey_signing_secret()
                key = db.get_honey_key(token_id)
                if key and open_url_is_valid(signing_secret, token_id, signature):
                    headers = sanitize_headers(dict(self.headers.items()))
                    db.record_honey_key_trigger(
                        honey_key=key,
                        ip_address=self.client_address[0] if self.client_address else None,
                        user_agent=self.headers.get("User-Agent"),
                        method="GET",
                        path=self.path,
                        headers=headers,
                        body_summary=None,
                        confidence=0.92,
                        source_type="url_open",
                    )
            finally:
                db.close()
            self.send_no_content()
            return
        if parsed.path == "/api/honey/trigger":
            self.trigger_honey_key(parsed, method="GET")
            return
        if parsed.path == "/api/projects":
            root = Path(os.environ.get("SECURITY_OBSERVATORY_PROJECTS_ROOT", "~/Dev/Projects")).expanduser()
            repos = [{"name": repo.name, "path": str(repo)} for repo in discover_repos(root)]
            self.send_json({"root": str(root), "repos": repos})
            return
        if parsed.path == "/api/check-status":
            job_id = parse_qs(parsed.query).get("jobId", [""])[0]
            job = job_snapshot(job_id)
            if not job:
                self.send_error(404, "Check job not found.")
                return
            self.send_json({"job": job})
            return
        if parsed.path.rstrip("/") == "/report":
            query = parse_qs(parsed.query)
            scan_id = query.get("scanId", [""])[0]
            kind = query.get("kind", ["prompt"])[0]
            if kind not in {"raw", "prompt"}:
                self.send_error(400, "Report kind must be raw or prompt.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                scan = db.scan_export(scan_id)
            finally:
                db.close()
            if not scan:
                self.send_error(404, "Scan report not found.")
                return
            self.send_html(report_page(scan, kind))
            return
        if parsed.path == "/api/report":
            query = parse_qs(parsed.query)
            scan_id = query.get("scanId", [""])[0]
            kind = query.get("kind", ["raw"])[0]
            if kind not in {"raw", "prompt"}:
                self.send_error(400, "Report kind must be raw or prompt.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                scan = db.scan_export(scan_id)
            finally:
                db.close()
            if not scan:
                self.send_error(404, "Scan report not found.")
                return
            if kind == "raw":
                body = raw_report_export(scan)
                self.send_download(body, content_type="application/json; charset=utf-8", filename=f"{scan_id}-raw-report.json")
                return
            prompt = build_ai_prompt(scan).encode("utf-8")
            self.send_download(prompt, content_type="text/markdown; charset=utf-8", filename=f"{scan_id}-ai-next-steps-prompt.md")
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/case-decision":
            self.save_case_decision()
            return
        if parsed.path == "/api/agent-lab/proposals":
            self.import_agent_lab_proposal()
            return
        if parsed.path == "/api/agent-lab/proposals/decision":
            self.save_agent_lab_proposal_decision()
            return
        if parsed.path == "/api/agent-lab/proposals/run":
            self.run_agent_lab_proposal()
            return
        if parsed.path == "/api/honey/keys":
            self.create_honey_key()
            return
        if parsed.path == "/api/honey/archive":
            self.archive_honey_key()
            return
        if parsed.path == "/api/honey/incident-step":
            self.update_honey_incident_step()
            return
        if parsed.path == "/api/honey/incident-close":
            self.close_honey_incident()
            return
        if parsed.path == "/api/honey/insert":
            self.insert_honey_key_file()
            return
        if parsed.path == "/api/honey/trigger":
            self.trigger_honey_key(parsed, method="POST")
            return
        if parsed.path == "/api/managed-tools/install":
            self.install_managed_tool()
            return
        if parsed.path == "/api/managed-tools/uninstall":
            self.uninstall_managed_tool()
            return
        if parsed.path == "/api/tools/install-via-pkg":
            self.install_via_homebrew()
            return
        if parsed.path != "/api/run-check":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            repo_path = Path(str(payload.get("repoPath", ""))).expanduser().resolve()
            audits = [str(item) for item in payload.get("audits", [])]
            if not repo_path.is_dir():
                self.send_error(400, "Repo path does not exist.")
                return
            args = args_for_audits(audits)
            scanners = scanner_names_for_profile(args)
            job_id = uuid.uuid4().hex[:12]
            job = {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Queued",
                "repoName": repo_path.name,
                "repoPath": str(repo_path),
                "audits": audits or ["quick"],
                "steps": [SCANNER_LABELS.get(scanner, scanner) for scanner in scanners],
                "currentStep": None,
                "currentScanner": None,
                "startedAt": utc_now(),
                "finishedAt": None,
                "error": None,
            }
            with CHECK_JOBS_LOCK:
                CHECK_JOBS[job_id] = job
            thread = threading.Thread(target=run_check_job, args=(job_id, self.db_path, repo_path, args), daemon=True)
            thread.start()
            self.send_json({"job": job_snapshot(job_id)})
        except Exception as exc:
            self.send_error(500, str(exc))

    def install_managed_tool(self) -> None:
        try:
            payload = self.read_json_body()
            tool_id = str(payload.get("toolId") or payload.get("tool_id") or "").strip()
            if not payload.get("confirmManagedInstall"):
                self.send_error(400, "Confirm managed install before downloading a DëvSec-owned tool.")
                return
            install_record = install_managed_tool_files(tool_id)
            db = ObservatoryDB(self.db_path)
            try:
                record = db.record_managed_tool(
                    tool_id=str(install_record["tool_id"]),
                    version=str(install_record["version"]),
                    install_root=str(install_record["install_root"]),
                    binary_path=str(install_record["binary_path"]),
                    source=str(install_record["source"]),
                    checksum=str(install_record["checksum"]),
                    installer_version=str(install_record["installer_version"]),
                    ownership_id=str(install_record["ownership_id"]),
                    installed_at=str(install_record["installed_at"]),
                    active=True,
                    version_check_status=str(install_record["version_check_status"]),
                    version_check_output=str(install_record.get("version_check_output") or ""),
                    version_checked_at=str(install_record["version_checked_at"]),
                    metadata=dict(install_record.get("metadata") or {}),
                )
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            tool = _catalog_tool(tool_id, managed_tool_records)
            self.send_json(
                {
                    "managed_tool": record,
                    "tool": tool,
                    "preview": (tool or {}).get("install_preview"),
                }
            )
        except ManagedToolInstallError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def uninstall_managed_tool(self) -> None:
        try:
            payload = self.read_json_body()
            tool_id = str(payload.get("toolId") or payload.get("tool_id") or "gitleaks").strip()
            ownership_id = str(payload.get("ownershipId") or payload.get("ownership_id") or "").strip()
            if not payload.get("confirmManagedUninstall"):
                self.send_error(400, "Confirm managed uninstall before removing a DëvSec-owned tool.")
                return

            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
                record = _managed_record_for_uninstall(managed_tool_records, tool_id=tool_id, ownership_id=ownership_id)
                if record is None:
                    self.send_error(404, "DëvSec-owned managed tool not found.")
                    return
                removal = uninstall_managed_tool_files(record)
                deactivated = db.deactivate_managed_tool(str(record["ownership_id"]))
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            tool = _catalog_tool(tool_id, managed_tool_records)
            self.send_json(
                {
                    "removed": removal,
                    "managed_tool": deactivated,
                    "tool": tool,
                    "preview": (tool or {}).get("install_preview"),
                }
            )
        except ManagedToolInstallError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def install_via_homebrew(self) -> None:
        # Catalog declares each tool's install method (homebrew, uv tool, manual, ...).
        # For method=homebrew we can run `brew install <binary>` on the user's behalf
        # because the binary name is part of the catalog contract — not user input.
        try:
            payload = self.read_json_body()
            tool_id = str(payload.get("toolId") or payload.get("tool_id") or "").strip()
            if not payload.get("confirmHomebrewInstall"):
                self.send_error(400, "Confirm Homebrew install before running brew.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            tool = _catalog_tool(tool_id, managed_tool_records)
            if tool is None:
                self.send_error(404, f"Tool {tool_id!r} not in catalog.")
                return
            install = tool.get("install") or {}
            if install.get("method") != "homebrew":
                self.send_error(400, f"Tool {tool_id!r} is not a Homebrew install (method={install.get('method')!r}).")
                return
            binary = str(install.get("binary") or "").strip()
            if not re.match(r"^[a-z0-9][a-z0-9._-]*$", binary):
                self.send_error(400, f"Refusing to run brew with binary name {binary!r}.")
                return
            brew = shutil.which("brew")
            if not brew:
                self.send_error(500, "Homebrew is not installed. Install Homebrew first: https://brew.sh")
                return
            env = {
                **os.environ,
                "HOMEBREW_NO_AUTO_UPDATE": "1",
                "HOMEBREW_NO_ANALYTICS": "1",
                "HOMEBREW_NO_ENV_HINTS": "1",
            }
            result = subprocess.run(
                [brew, "install", binary],
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )
            success = result.returncode == 0
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            refreshed = _catalog_tool(tool_id, managed_tool_records)
            self.send_json({
                "tool": refreshed,
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": f"brew install {binary}",
            })
        except subprocess.TimeoutExpired:
            self.send_error(504, "brew install timed out after 600s.")
        except Exception as exc:
            self.send_error(500, str(exc))

    def save_case_decision(self) -> None:
        try:
            payload = self.read_json_body()
            case_id = str(payload.get("caseId") or payload.get("case_id") or "").strip()
            repo_name = str(payload.get("repoName") or payload.get("repo_name") or "").strip()
            status = str(payload.get("status") or "open").strip()
            note = str(payload.get("note") or "").strip()
            vex_status = str(payload.get("vexStatus") or payload.get("vex_status") or "").strip() or None
            vex_justification = str(payload.get("vexJustification") or payload.get("vex_justification") or payload.get("vexReason") or payload.get("vex_reason") or "").strip() or None
            if not case_id:
                self.send_error(400, "Case id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                decision = db.set_case_decision(
                    case_id=case_id,
                    repo_name=repo_name or "repository",
                    status=status,
                    note=note,
                    vex_status=vex_status,
                    vex_justification=vex_justification,
                    vulnerability_id=str(payload.get("vulnerabilityId") or payload.get("vulnerability_id") or "").strip() or None,
                    package_name=str(payload.get("packageName") or payload.get("package_name") or "").strip() or None,
                    package_version=str(payload.get("packageVersion") or payload.get("package_version") or "").strip() or None,
                    package_ecosystem=str(payload.get("packageEcosystem") or payload.get("package_ecosystem") or "").strip() or None,
                    package_url=str(payload.get("packageUrl") or payload.get("package_url") or "").strip() or None,
                    component_package_key=str(payload.get("componentPackageKey") or payload.get("component_package_key") or "").strip() or None,
                    fixed_version=str(payload.get("fixedVersion") or payload.get("fixed_version") or "").strip() or None,
                )
            finally:
                db.close()
            self.send_json({"decision": decision})
        except ValueError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def import_agent_lab_proposal(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > AGENT_PROPOSAL_MAX_BYTES:
                self.send_json_error(400, "Agent Lab proposal is too large.", max_bytes=AGENT_PROPOSAL_MAX_BYTES)
                return
            body = self.rfile.read(length) if length else b"{}"
            if len(body) > AGENT_PROPOSAL_MAX_BYTES:
                self.send_json_error(400, "Agent Lab proposal is too large.", max_bytes=AGENT_PROPOSAL_MAX_BYTES)
                return
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except json.JSONDecodeError as exc:
                self.send_json_error(400, "Request body must be JSON.", errors=[exc.msg])
                return
            proposal = proposal_from_import_payload(payload)
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
                validated = validate_agent_proposal(proposal, managed_tool_records=managed_tool_records)
                saved = db.save_agent_lab_proposal(validated)
            finally:
                db.close()
            self.send_json({"proposal": saved})
        except AgentLabProposalValidationError as exc:
            self.send_json_error(400, "Agent Lab proposal failed validation.", errors=exc.errors)
        except Exception as exc:
            self.send_error(500, str(exc))

    def preview_agent_lab_proposal_execution(self, parsed: Any) -> None:
        query = parse_qs(parsed.query)
        proposal_id = str(query.get("proposalId", query.get("proposal_id", query.get("id", [""])))[0] or "").strip()
        mode = str(query.get("mode", ["dry_run_preview"])[0] or "dry_run_preview").strip()
        if not proposal_id:
            self.send_json_error(400, "Agent Lab proposal id is required.")
            return
        try:
            db = ObservatoryDB(self.db_path)
            try:
                proposal = db.get_agent_lab_proposal(proposal_id)
                if not proposal:
                    self.send_json_error(404, "Agent Lab proposal not found.")
                    return
                preview = build_agent_execution_preview(
                    proposal,
                    managed_tool_records=db.list_managed_tools(),
                    requested_mode=mode,
                )
                plan = dict(proposal.get("final_execution_plan") or {})
                plan["last_preview"] = preview
                proposal = db.update_agent_lab_execution_plan(proposal_id=proposal_id, final_execution_plan=plan)
            finally:
                db.close()
            self.send_json({"preview": preview, "proposal": proposal})
        except AgentLabExecutionError as exc:
            self.send_json_error(400, "Agent Lab proposal cannot be routed.", errors=exc.errors)
        except ValueError as exc:
            self.send_json_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def save_agent_lab_proposal_decision(self) -> None:
        try:
            payload = self.read_json_body()
            proposal_id = str(payload.get("proposalId") or payload.get("proposal_id") or payload.get("id") or "").strip()
            approval_state = str(payload.get("approvalState") or payload.get("approval_state") or payload.get("decision") or "").strip()
            if not proposal_id:
                self.send_json_error(400, "Agent Lab proposal id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                proposal = db.set_agent_lab_proposal_approval(
                    proposal_id=proposal_id,
                    approval_state=approval_state,
                    note=str(payload.get("note") or "").strip() or None,
                    decided_by=str(payload.get("decidedBy") or payload.get("decided_by") or "").strip() or None,
                )
            finally:
                db.close()
            self.send_json({"proposal": proposal})
        except ValueError as exc:
            self.send_json_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def run_agent_lab_proposal(self) -> None:
        try:
            payload = self.read_json_body()
            proposal_id = str(payload.get("proposalId") or payload.get("proposal_id") or payload.get("id") or "").strip()
            mode = str(payload.get("mode") or "dry_run_preview").strip()
            execute = bool(payload.get("execute")) or mode == "approved_run"
            if not proposal_id:
                self.send_json_error(400, "Agent Lab proposal id is required.")
                return

            db = ObservatoryDB(self.db_path)
            try:
                proposal = db.get_agent_lab_proposal(proposal_id)
                if not proposal:
                    self.send_json_error(404, "Agent Lab proposal not found.")
                    return
                preview = build_agent_execution_preview(
                    proposal,
                    managed_tool_records=db.list_managed_tools(),
                    requested_mode="approved_run" if execute else "dry_run_preview",
                    require_approval=execute,
                )
                if not execute:
                    plan = dict(proposal.get("final_execution_plan") or {})
                    plan["last_preview"] = preview
                    proposal = db.update_agent_lab_execution_plan(proposal_id=proposal_id, final_execution_plan=plan)
                    self.send_json({"preview": preview, "proposal": proposal})
                    return
            finally:
                db.close()

            repo_path = Path(str(proposal.get("repo_path") or "")).expanduser().resolve()
            if not repo_path.is_dir():
                self.send_json_error(400, "Agent Lab proposal repo path does not exist.")
                return
            scanner_names = [str(item) for item in preview.get("scanner_names") or [] if str(item).strip()]
            if not scanner_names:
                self.send_json_error(400, "Agent Lab proposal has no DëvSec scanner route.")
                return
            profile_ids = [str(item) for item in preview.get("scan_profile_ids") or [] if str(item).strip()]
            args = args_for_audits(profile_ids)
            job_id = uuid.uuid4().hex[:12]
            job = {
                "id": job_id,
                "status": "queued",
                "source": "agent-lab",
                "proposalId": proposal_id,
                "progress": 0,
                "message": "Queued Agent Lab scan",
                "repoName": repo_path.name,
                "repoPath": str(repo_path),
                "audits": profile_ids or ["quick"],
                "steps": [SCANNER_LABELS.get(scanner, scanner) for scanner in scanner_names],
                "currentStep": None,
                "currentScanner": None,
                "startedAt": utc_now(),
                "finishedAt": None,
                "error": None,
                "executionPreview": preview,
            }
            with CHECK_JOBS_LOCK:
                CHECK_JOBS[job_id] = job
            _record_agent_lab_execution_result(
                self.db_path,
                proposal_id,
                preview,
                {
                    "job_id": job_id,
                    "mode": "approved_run",
                    "status": "queued",
                    "started_at": job["startedAt"],
                    "scanner_names": scanner_names,
                },
            )
            thread = threading.Thread(
                target=run_check_job,
                args=(job_id, self.db_path, repo_path, args),
                kwargs={
                    "scanner_names": scanner_names,
                    "agent_lab_proposal_id": proposal_id,
                    "agent_lab_preview": preview,
                },
                daemon=True,
            )
            thread.start()
            self.send_accepted_json({"job": job_snapshot(job_id), "preview": preview})
        except AgentLabExecutionError as exc:
            self.send_json_error(400, "Agent Lab proposal cannot be routed.", errors=exc.errors)
        except ValueError as exc:
            self.send_json_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def create_honey_key(self) -> None:
        try:
            payload = self.read_json_body()
            repo_path = str(payload.get("repoPath") or "").strip()
            repo_name = str(payload.get("repoName") or Path(repo_path).name or "repository").strip()
            project_id = str(payload.get("projectId") or project_id_for_repo_path(repo_path or repo_name))
            name = str(payload.get("name") or "Legacy internal API key").strip()[:120]
            placement_path = str(payload.get("placementPath") or DEFAULT_PLACEMENT_PATHS[0]).strip()[:240]
            note = str(payload.get("note") or "").strip()[:500] or None
            created_by = str(payload.get("createdBy") or "").strip()[:120] or None
            db = ObservatoryDB(self.db_path)
            try:
                signing_secret = db.honey_signing_secret()
                material = generate_honey_key(signing_secret)
                key = db.create_honey_key(
                    key_id=material.token_id,
                    project_id=project_id,
                    repo_id=repo_path or None,
                    name=name,
                    token_hash=material.token_hash,
                    placement_path=placement_path,
                    note=note,
                    created_by=created_by,
                )
                snippets = build_decoy_snippets(
                    base_url=self.request_base_url(),
                    name=name,
                    token=material.token,
                    token_id=material.token_id,
                    signing_secret=signing_secret,
                )
                self.send_json(
                    {
                        "key": key,
                        "raw_token": material.token,
                        "snippets": snippets,
                        "warning": "Honey Keys are fake, powerless decoy secrets. They alert you when touched. They do not prevent breaches by themselves.",
                    }
                )
            finally:
                db.close()
        except sqlite3.IntegrityError:
            self.send_error(409, "Honey Key already exists.")
        except Exception as exc:
            self.send_error(500, str(exc))

    def archive_honey_key(self) -> None:
        try:
            payload = self.read_json_body()
            key_id = str(payload.get("id") or "").strip()
            if not key_id:
                self.send_error(400, "Honey Key id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                key = db.archive_honey_key(key_id)
            finally:
                db.close()
            if not key:
                self.send_error(404, "Honey Key not found.")
                return
            self.send_json({"key": key})
        except Exception as exc:
            self.send_error(500, str(exc))

    def update_honey_incident_step(self) -> None:
        try:
            payload = self.read_json_body()
            event_id = str(payload.get("eventId") or payload.get("event_id") or "").strip()
            step = str(payload.get("step") or "").strip()
            complete = bool(payload.get("complete"))
            if not event_id:
                self.send_error(400, "Honey Key event id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                incident = db.set_honey_incident_step(event_id, step, complete)
            finally:
                db.close()
            self.send_json({"incident": incident})
        except ValueError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def close_honey_incident(self) -> None:
        try:
            payload = self.read_json_body()
            event_id = str(payload.get("eventId") or payload.get("event_id") or "").strip()
            note = str(payload.get("acceptedRiskNote") or payload.get("accepted_risk_note") or "").strip()
            if not event_id:
                self.send_error(400, "Honey Key event id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                incident = db.close_honey_incident(event_id, note)
            finally:
                db.close()
            self.send_json({"incident": incident})
        except ValueError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def insert_honey_key_file(self) -> None:
        try:
            payload = self.read_json_body()
            key_id = str(payload.get("id") or "").strip()
            repo_path = Path(str(payload.get("repoPath") or "")).expanduser().resolve()
            placement_path = str(payload.get("placementPath") or "").strip()
            snippet = str(payload.get("snippet") or "")
            confirmed = bool(payload.get("confirmPlacement"))
            advanced_placement = bool(payload.get("advancedPlacement"))

            if not key_id:
                self.send_error(400, "Honey Key id is required.")
                return
            if not confirmed:
                self.send_error(400, "Confirm safe placement before writing the decoy file.")
                return
            if not repo_path.is_dir():
                self.send_error(400, "Repo path does not exist.")
                return
            if not placement_path or Path(placement_path).is_absolute():
                self.send_error(400, "Placement path must be relative to the repo.")
                return
            if len(snippet.encode("utf-8")) > 64_000:
                self.send_error(400, "Decoy snippet is too large.")
                return

            target_path = (repo_path / placement_path).resolve()
            try:
                target_path.relative_to(repo_path)
            except ValueError:
                self.send_error(400, "Placement path must stay inside the repo.")
                return
            if not _is_safe_honeykeys_path(placement_path) and not advanced_placement:
                self.send_error(400, "Default insertions must use .devsec/honeykeys/. Enable advanced placement for realistic decoy filenames.")
                return
            if target_path.exists():
                self.send_error(409, "Placement file already exists. Choose a new decoy path so DëvSec does not overwrite real project files.")
                return

            db = ObservatoryDB(self.db_path)
            try:
                signing_secret = db.honey_signing_secret()
                token = extract_honey_key_from_request(path="", query={}, headers={}, body=snippet.encode("utf-8"))
                if not token or not honey_key_is_well_formed(token, signing_secret):
                    self.send_error(400, "Decoy snippet does not contain a valid Honey Key.")
                    return
                key = db.find_honey_key_by_hash(hash_honey_key(token))
                if not key or str(key["id"]) != key_id:
                    self.send_error(400, "Decoy snippet does not match this Honey Key.")
                    return
                if key.get("repo_id") and Path(str(key["repo_id"])).expanduser().resolve() != repo_path:
                    self.send_error(400, "Honey Key belongs to a different repo.")
                    return
            finally:
                db.close()

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(snippet, encoding="utf-8")
            try:
                os.chmod(target_path, 0o600)
            except OSError:
                pass
            self.send_json({"path": str(target_path), "relative_path": placement_path})
        except Exception as exc:
            self.send_error(500, str(exc))

    def trigger_honey_key(self, parsed, *, method: str) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(min(length, 64_000)) if length else b""
        header_dict = dict(self.headers.items())
        token = extract_honey_key_from_request(
            path=self.path,
            query=parse_qs(parsed.query),
            headers=header_dict,
            body=body,
        )
        db = ObservatoryDB(self.db_path)
        try:
            signing_secret = db.honey_signing_secret()
            if token and honey_key_is_well_formed(token, signing_secret):
                key = db.find_honey_key_by_hash(hash_honey_key(token))
                if key:
                    db.record_honey_key_trigger(
                        honey_key=key,
                        ip_address=self.client_address[0] if self.client_address else None,
                        user_agent=self.headers.get("User-Agent"),
                        method=method,
                        path=self.path,
                        headers=sanitize_headers(header_dict),
                        body_summary=summarize_body(body, self.headers.get("Content-Type")),
                        confidence=0.98 if key.get("status") != "archived" else 0.35,
                        source_type="api_call",
                    )
        finally:
            db.close()
        self.send_accepted_json({"accepted": True})

    def read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(min(length, 64_000)) if length else b"{}"
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def request_base_url(self) -> str:
        host = self.headers.get("Host") or f"127.0.0.1:{self.server.server_port}"
        return f"http://{host}"


def _is_safe_honeykeys_path(path: str) -> bool:
    clean = Path(path)
    parts = clean.parts
    return len(parts) >= 3 and parts[0] == ".devsec" and parts[1] == "honeykeys"


def _catalog_tool(tool_id: str, managed_tool_records: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            tool
            for tool in tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
            if tool.get("id") == tool_id
        ),
        None,
    )


def _managed_record_for_uninstall(
    records: list[dict[str, Any]],
    *,
    tool_id: str,
    ownership_id: str,
) -> dict[str, Any] | None:
    candidates = [
        record
        for record in records
        if str(record.get("tool_id") or "") == tool_id
        and (not ownership_id or str(record.get("ownership_id") or "") == ownership_id)
    ]
    verified = [record for record in candidates if managed_tool_evidence(record).verified]
    if len(verified) == 1:
        return verified[0]
    if ownership_id and candidates:
        return candidates[0]
    return None


def serve_dashboard(db_path: Path, assets_dir: Path, port: int, open_browser: bool) -> None:
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"db_path": db_path, "assets_dir": assets_dir})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Security Observatory dashboard: {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
