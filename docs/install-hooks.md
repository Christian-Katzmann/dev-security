# Install Hook Classifier

Security Observatory classifies install-time hooks without running package
managers or reaching the network. The scanner reads local files only:

- `package.json` scripts named `preinstall`, `install`, and `postinstall`
- Python `pyproject.toml` build backends and hook-like command fields
- `setup.py` install-command lines such as `cmdclass`, subprocess calls, and
  shell helpers

Every discovered npm install hook is saved in the raw `install-hooks.json`
report. Only high and critical records become cases, so ordinary or unclear
hooks stay visible without flooding the remediation queue.

## Tiers

- `critical`: remote script piped to shell, base64 decode piped to shell,
  fetch-then-`eval`, temporary write-and-execute patterns, or install-time
  writes to `~/.npmrc` / `~/.pypirc`.
- `high`: unaudited shell-outs, dynamic compiled artifact downloads,
  `NODE_OPTIONS` changes, or `child_process` use from install scripts.
- `medium`: nested installers, unknown `node-gyp rebuild` paths, native builds
  without checksum evidence, or unknown install-hook patterns.
- `info`: pnpm install enforcers and clearly local subproject install chains.

Unknown patterns intentionally fall back to `medium` with low confidence. That
means Observatory is saying "look at this once," not "this package is bad."

## Allow-List

Known-good entries can be silenced per project in:

```text
.devsec/install-hook-allowlist.yaml
```

Format:

```yaml
entries:
  - rule: install-local-subproject
    path: package.json
    reason: Installs the checked-in local client package.
```

Entries require `rule`, `path`, and a human-readable `reason`. A matching entry
without a reason does not silence the finding; the missing reason is kept in
the case evidence.
