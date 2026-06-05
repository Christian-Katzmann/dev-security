"""Server-rendered report and docs pages for the local dashboard.

Two surfaces render as standalone HTML, parallel to the React dashboard: the
``/report/`` export page (AI-handoff prompt + full raw report) and the
``/docs/`` shell. They live here, out of the request handler, so
``dashboard_server`` stays a routing layer rather than also being a second
templating engine. Every function here is pure: it takes a scan/doc payload
and returns a string (or bytes, for the raw export).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .cases import build_security_cases, scanner_evidence_gaps
from .decisions import assemble_suppression


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


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, re.sub(r"[-_]+", " ", category).title())


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
          <p class="lede">This page turns the local scan into a focused brief for an AI coding agent. It is generated locally from saved cases and raw findings.</p>
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
          <p class="lede">This is the raw normalized report with cases, raw findings, scanner status, and evidence gaps. It is intentionally plain.</p>
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
        {"active_incident": 0, "fix_now": 1, "verify": 2, "watch": 3, "info": 4}.get(str(case.get("action_level")), 9),
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
        ("Raw findings", len(list(finding_source or []))),
        ("Suppressed raw findings", suppressed_counts.get("findings", 0)),
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
            {"active_incident": 0, "fix_now": 1, "verify": 2, "watch": 3, "info": 4}.get(str(item.get("action_level")), 9),
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
        f"- Total raw findings: {len(findings)}",
        f"- Suppressed cases: {suppressed_counts.get('cases', 0)}",
        f"- Suppressed raw findings: {suppressed_counts.get('findings', 0)}",
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
