# Workflow Surface Audit

Security Observatory audits GitHub Actions workflow files locally. It walks:

```text
.github/workflows/*.yml
.github/workflows/*.yaml
```

No actions are executed, no tokens are read, and no network calls are made.

## Rules

- `workflow-unpinned-action`: `uses:` references that are not pinned to a full
  commit SHA.
- `workflow-fetch-exec`: `run:` blocks that fetch remote code and execute it,
  such as `curl ... | sh`, `wget ... | bash`, or `bash <(curl ...)`.
- `workflow-secret-exfil`: `run:` blocks that echo, encode, or send
  `${{ secrets.* }}` values.
- `workflow-pr-target-fork-checkout`: `pull_request_target` workflows that
  check out fork-controlled pull request code.
- `workflow-untrusted-input-run`: `run:` blocks that interpolate event body or
  title text directly into shell.
- `workflow-permissions-write-all` and `workflow-permissions-write`: workflow
  tokens widened to write scopes without a nearby justification comment.

Critical findings are active execution or exfiltration patterns. High findings
are broad trust surfaces such as unpinned actions or write-scoped workflow
tokens. The `pull_request_target` fork-checkout pattern is medium because it
requires the surrounding workflow to determine exploitability.

## Allow-List

Known-good entries can be silenced per project in:

```text
.devsec/workflow-allowlist.yaml
```

Format:

```yaml
entries:
  - rule: workflow-fetch-exec
    path: .github/workflows/template-validation.yml
    line: 52
    reason: Official Typst installer used only for documentation validation.
```

Entries require `rule`, `path`, and `reason`; `line` is optional but recommended
for noisy workflow patterns. A matching entry without a reason does not silence
the finding.
