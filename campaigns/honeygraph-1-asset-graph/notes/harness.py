"""3.2 validation harness — faithful replay of scan_repo's post-scanner pipeline.

Real findings (stored scan history) + real SBOM dependency graph (syft) + a
human-labeled crown-jewel component. Runs the EXACT ranking code scan_repo runs.
"""
from __future__ import annotations
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, "src")
from security_observatory.model import Finding
from security_observatory.sbom import load_sbom_components, load_sbom_dependency_edges
from security_observatory.enrichment import correlate_dependency_findings
from security_observatory.cases import build_security_cases, apply_consequence_priority
from security_observatory.asset_graph import derive_asset_nodes
from security_observatory.crown_jewels import mark_crown_jewels, CrownJewelLabel
from security_observatory.consequence import attach_consequences

REPORT = sys.argv[1]
CDX = sys.argv[2]
CROWN_PKGS = [p.strip() for p in sys.argv[3].split(",")] if len(sys.argv) > 3 else []

scan_dir = Path("/tmp/honeygraph-32/scan_dir"); scan_dir.mkdir(parents=True, exist_ok=True)
shutil.copy(CDX, scan_dir / "sbom.cyclonedx.json")
report = json.loads(Path(REPORT).read_text()); repo_name = report["repo"]
fields = set(Finding.__dataclass_fields__)
findings = [Finding(**{k: v for k, v in f.items() if k in fields}) for f in report["findings"]]
components = load_sbom_components(scan_dir)
dep_edges = load_sbom_dependency_edges(scan_dir)
findings = correlate_dependency_findings(findings, components)
print(f"== {repo_name} == findings={len(findings)} components={len(components)} dep_edges={len(dep_edges)} "
      f"correlated={sum(1 for f in findings if f.component_fingerprint)}")

statuses = report.get("scanners", [])
cases = build_security_cases(findings, statuses, {"repo": repo_name}, [])
# snapshot pre-boost rank + action level per case_id
before = {c.case_id: (i, c.action_level) for i, c in enumerate(cases)}
severity_order = list(cases)

component_dicts = [c.to_dict() for c in components]
nodes = derive_asset_nodes(components=component_dicts, findings=findings, iac_resources=[])
labels = []
for pkg in CROWN_PKGS:
    fp = None
    for c in components:
        cd = c.to_dict()
        if str(cd.get("name") or "").lower() == pkg.lower():
            fp = cd.get("component_fingerprint"); break
    if fp:
        labels.append(CrownJewelLabel(identity_key=fp, node_type="component"))
        print(f"crown jewel: {pkg} -> {fp}")
    else:
        print(f"!! not found: {pkg}")
if labels:
    nodes = mark_crown_jewels(nodes, labels)

attach_consequences(cases, nodes, dep_edges)
boosted = apply_consequence_priority(cases)

with_cons = [c for c in cases if isinstance(c.consequence, dict)]
reaches = [c for c in with_cons if c.consequence.get("reaches_crown_jewel")]
strong = [c for c in reaches if c.consequence.get("confidence") == "strong"]
weak = [c for c in reaches if c.consequence.get("confidence") == "weak"]
print(f"consequence-dict cases={len(with_cons)} reach-jewel={len(reaches)} (strong={len(strong)} weak={len(weak)})")

def fmt(case, idx):
    cons = case.consequence if isinstance(case.consequence, dict) else None
    tag = ""
    if cons and cons.get("reaches_crown_jewel"):
        tag = f"  <<REACHES d={cons.get('distance')} {cons.get('confidence')} blast={cons.get('blast_radius')}>>"
    return f"{idx:2d}. [{case.action_level:7}/{case.severity:8}] {case.title[:62]}{tag}"

print("\n--- TOP 12 BY SEVERITY (today) ---")
for i, c in enumerate(severity_order[:12], 1): print(fmt(c, i))
print("\n--- TOP 12 BY CONSEQUENCE (post-boost) ---")
for i, c in enumerate(boosted[:12], 1): print(fmt(c, i))

# Action-level changes (the real promotions)
print("\n--- ACTION-LEVEL PROMOTIONS (rank/bucket change) ---")
after = {c.case_id: (i, c.action_level) for i, c in enumerate(boosted)}
promoted = [c for c in boosted if before[c.case_id][1] != after[c.case_id][1]]
if not promoted: print("  (none — no case changed action level)")
for c in promoted:
    bi, bl = before[c.case_id]; ai, al = after[c.case_id]
    print(f"  {c.title[:50]}: {bl}->{al}  rank {bi}->{ai}")
    for r in c.priority_reasons:
        if "reach" in r.lower(): print(f"      reason: {r}")

# Where do dependency cases sit before vs after?
print("\n--- DEPENDENCY CASES: rank before -> after ---")
dep_cases = [c for c in boosted if c.category == "dependencies"]
for c in sorted(dep_cases, key=lambda x: after[x.case_id][0]):
    bi = before[c.case_id][0]; ai = after[c.case_id][0]
    cons = c.consequence if isinstance(c.consequence, dict) else None
    r = "reaches" if (cons and cons.get("reaches_crown_jewel")) else "-"
    print(f"  rank {bi:3d}->{ai:3d} [{c.action_level:7}/{c.severity}] {c.title[:48]} [{r}]")
