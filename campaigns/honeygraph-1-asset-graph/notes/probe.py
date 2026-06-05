"""Probe the real dependency graph: from each vulnerable component, which
consumers (blast targets) are reachable? Helps pick an honest crown jewel."""
from __future__ import annotations
import json, shutil, sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, "src")
from security_observatory.model import Finding
from security_observatory.sbom import load_sbom_components, load_sbom_dependency_edges
from security_observatory.enrichment import correlate_dependency_findings

REPORT, CDX = sys.argv[1], sys.argv[2]
scan_dir = Path("/tmp/honeygraph-32/scan_dir"); scan_dir.mkdir(parents=True, exist_ok=True)
shutil.copy(CDX, scan_dir / "sbom.cyclonedx.json")
report = json.loads(Path(REPORT).read_text())
fields = set(Finding.__dataclass_fields__)
findings = [Finding(**{k:v for k,v in f.items() if k in fields}) for f in report["findings"]]
components = load_sbom_components(scan_dir)
dep_edges = load_sbom_dependency_edges(scan_dir)
findings = correlate_dependency_findings(findings, components)

# fingerprint -> label
fp_label = {}
for c in components:
    cd = c.to_dict()
    fp_label[cd.get("component_fingerprint")] = f"{cd.get('name')}@{cd.get('version')}"

# Build blast adjacency: depends_on reversed (src depends_on dst => from dst reach src)
adj = defaultdict(list)
for e in dep_edges:
    # AssetEdge: src_identity_key depends_on dst_identity_key
    adj[e.dst_identity_key].append(e.src_identity_key)

def bfs(start):
    seen={start}; stack=[start]
    while stack:
        n=stack.pop()
        for m in adj.get(n,()):
            if m not in seen:
                seen.add(m); stack.append(m)
    seen.discard(start)
    return seen

vuln_fps = sorted({f.component_fingerprint for f in findings if f.component_fingerprint})
print(f"vulnerable component fingerprints: {len(vuln_fps)}")
print(f"total dep edges: {len(dep_edges)}")

# For each vuln, how many consumers can it reach (blast radius)?
consumer_tally = Counter()
total_blast = []
for fp in vuln_fps:
    reach = bfs(fp)
    total_blast.append((fp_label.get(fp,fp), len(reach)))
    for r in reach:
        consumer_tally[fp_label.get(r,r)] += 1
total_blast.sort(key=lambda x:-x[1])
print("\nVuln packages by blast radius (consumers reachable):")
for name,n in total_blast[:20]:
    print(f"  {n:4d}  {name}")

print("\nMost-common blast TARGETS (consumers reached by many vulns) — crown-jewel candidates:")
for name,n in consumer_tally.most_common(25):
    print(f"  reached-by {n:4d} vulns  {name}")
