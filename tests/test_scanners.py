from pathlib import Path

from security_observatory.model import DEFAULT_EXCLUDES
from security_observatory.scanners import _command, scanner_catalog


def test_trufflehog_uses_local_friendly_exclusions(tmp_path: Path):
    command = _command("trufflehog", Path("/repo"), tmp_path, Path("/rules"))

    assert "--concurrency=2" in command
    assert "--force-skip-binaries" in command
    assert "--force-skip-archives" in command
    exclude_path = Path(command[command.index("--exclude-paths") + 1])
    content = exclude_path.read_text(encoding="utf-8")
    for name in DEFAULT_EXCLUDES:
        assert name in content


def test_scanner_catalog_includes_fixable_doctor_steps():
    catalog = {item["scanner"]: item for item in scanner_catalog()}

    assert catalog["ai-static"]["built_in"] is True
    assert "brew install semgrep" in catalog["semgrep"]["install"]
    assert "uv tool install checkov" in catalog["checkov"]["install"]
    assert catalog["gitleaks"]["area"] == "Secrets"
