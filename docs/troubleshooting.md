# Troubleshooting

## A Scanner Is Missing

Run:

```bash
security-scan doctor
```

Then rerun:

```bash
./install-security-observatory.sh
```

## A Scan Is Slow

Use:

```bash
security-scan --quick
```

Full scans intentionally do more work, especially dependency and filesystem scanners.

Medusa can be slow on some TypeScript/agent-heavy repos. The observatory runs it in quick mode with a bounded timeout so the rest of the scan still completes.

## Too Much Noise

Start with the normalized report and suppress at the scanner layer where possible. Prefer narrow allowlists over broad folder exclusions.

## Secret Findings

Do not paste secret values into issues or chat. Rotate the credential first, then clean history or add a specific allowlist entry if it is a false positive.

## Dashboard Has No Data

Run at least one scan:

```bash
security-scan .
```
