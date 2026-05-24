#!/usr/bin/env tsx
/**
 * Demo 2 — Python CLI end-to-end rotation against a fixture that mirrors
 * dëv-security's repo shape (pyproject.toml + .env). Uses the REAL
 * pythonCliAdapter and the REAL `security-scan` binary at
 * .venv/bin/security-scan as the smoke command.
 *
 * The demo runs in TWO PARTS because the pipeline clamps the soak window
 * to a minimum of 10 minutes (`SOAK_MIN_MS`). That floor is right for
 * production — it's the SRE-cadence floor the campaign locked. But a
 * single-session autonomous demo can't sit on a 10-minute wall-clock
 * sleep AND finish in the session's time budget, so we split:
 *
 *   PART A — Full pipeline, --no-soak.
 *     Runs HEALTH_CHECK → PREFLIGHT → ACQUIRE → STAGE_CANARY →
 *     VERIFY_CANARY → STAGE_PROD → VERIFY_PROD → ROTATED with `skipSoak:
 *     true`. Produces a real verification receipt where `soak_skipped`
 *     is surfaced loudly (that's the contract). Captures: receipt md,
 *     state.json, rotation-log.jsonl, the rotated .env + backup.
 *
 *   PART B — Direct adapter soak, compressed.
 *     Calls `pythonCliAdapter.baseline()` then `pythonCliAdapter.soakWindow()`
 *     directly with `durationMs = 2_000` and `invocationCount = 2`. The
 *     adapter clamps to its own 60 s floor, so the actual wall-clock is
 *     ~60 s but the SAME baseline/soak code path executes — same stderr
 *     monitoring, same pattern matching, same anomaly detection. Proves
 *     the soak phase works end-to-end in compressed time.
 *
 * Output (artifacts/):
 *   - rotation-state.json
 *   - <secret>-<ts>.md         (verification receipt — PART A)
 *   - rotation-log.jsonl       (step trail — PART A)
 *   - .env (rotated)
 *   - .env.backup-<ts>         (pre-rotation backup)
 *   - soak-direct-result.json  (PART B baseline + soak result)
 *   - stdout-transcript.txt    (full run log)
 */

import { promises as fs } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_BUILD = resolve(
  process.env.HOME!,
  ".claude/skills/secrets-rotation/tests/_build",
);

const SECRET = "DEVSEC_GITHUB_TOKEN";
const INITIAL = "synthetic-pre-rotation-token-0001";
const NEW_VALUE = "synthetic-post-rotation-token-0002-XYZ";

const SECURITY_SCAN_BIN =
  "/Users/christiankatzmann/Dev/Projects/dëv-security/.venv/bin/security-scan";

async function buildFixture(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "demo-python-cli-"));
  await fs.writeFile(
    join(root, "pyproject.toml"),
    `[project]
name = "security-observatory"
version = "0.1.0"
description = "Local-first security observability — DEMO FIXTURE"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
security-scan = "security_observatory.cli:main"
`,
    "utf8",
  );
  await fs.writeFile(
    join(root, ".env"),
    `# DEVSEC_GITHUB_TOKEN — synthetic demo secret (Class A self-generated).
# v0.2 demo artifact for the devsec-rotation-foundation campaign.
${SECRET}="${INITIAL}"
DEVSEC_LOG_LEVEL=info
`,
    "utf8",
  );
  await fs.mkdir(join(root, "data"), { recursive: true });
  await fs.writeFile(
    join(root, "data/rotation-state.json"),
    JSON.stringify(
      {
        version: 1,
        repo_name: "dëv-security (demo fixture)",
        scaffolded_at: new Date().toISOString(),
        scaffolded_version: "v0.2-foundation",
        secrets: [{ name: SECRET, class: "A" }],
        rotations: [],
      },
      null,
      2,
    ),
    "utf8",
  );
  return root;
}

function makeClassAPlugin() {
  return {
    secretName: SECRET,
    secretClass: "A" as const,
    async preflight() {
      return { ok: true as const };
    },
    async acquire() {
      return {
        newValue: NEW_VALUE,
        newValueFingerprint: "fp-demo-" + NEW_VALUE.slice(0, 12),
        newKeyId: null,
        oldKeyId: null,
      };
    },
    async verify() {
      return {
        ok: true as const,
        probedEndpoint: "(class-a no-provider stub)",
      };
    },
    async revoke() {
      return { ok: true as const };
    },
  };
}

async function copyArtifacts(repoRoot: string, dest: string): Promise<void> {
  await fs.mkdir(dest, { recursive: true });
  await fs.copyFile(
    join(repoRoot, "data/rotation-state.json"),
    join(dest, "rotation-state.json"),
  );
  try {
    await fs.copyFile(
      join(repoRoot, "data/rotation-log.jsonl"),
      join(dest, "rotation-log.jsonl"),
    );
  } catch {}
  const receipts = await fs
    .readdir(join(repoRoot, "data/rotation-receipts"))
    .catch(() => [] as string[]);
  for (const f of receipts) {
    await fs.copyFile(
      join(repoRoot, "data/rotation-receipts", f),
      join(dest, f),
    );
  }
  const entries = await fs.readdir(repoRoot);
  for (const f of entries) {
    if (f === ".env" || f.startsWith(".env.backup-")) {
      await fs.copyFile(join(repoRoot, f), join(dest, f));
    }
  }
}

async function main(): Promise<void> {
  // @ts-expect-error — dynamic import of rendered TS via tsx
  const { pythonCliAdapter } = await import(
    resolve(SKILL_BUILD, "adapters/python-cli.ts")
  );
  // @ts-expect-error — dynamic import of rendered TS via tsx
  const { runRotation } = await import(resolve(SKILL_BUILD, "lib/pipeline.ts"));

  const logs: string[] = [];
  const log = (line: string): void => {
    logs.push(line);
    process.stdout.write(line.endsWith("\n") ? line : line + "\n");
  };

  const smokeCommand = {
    command: SECURITY_SCAN_BIN,
    args: ["--version"],
  };

  // ─── PART A — Full pipeline with --no-soak ─────────────────────────
  log("═".repeat(72));
  log("PART A — Full pipeline rotation against fixture (skipSoak: true)");
  log("═".repeat(72));

  const repoRoot = await buildFixture();
  log(`[demo] fixture at ${repoRoot}`);
  log(`[demo] secret: ${SECRET}, initial value: ${INITIAL}`);

  const detected = await pythonCliAdapter.detect(repoRoot);
  log(`[demo] adapter.detect(repoRoot) = ${detected}`);
  if (!detected) throw new Error("python-cli adapter did not detect fixture");

  const result = await runRotation({
    repoRoot,
    secretName: SECRET,
    trigger: "cli",
    adapter: pythonCliAdapter,
    loadPlugin: async () => makeClassAPlugin(),
    log,
    verifyBackoffMs: [1, 1, 1],
    healthCheckDurationMs: 1500,
    skipSoak: true,
    adapterHints: {
      smokeCommand,
      invocationCount: 2,
      authErrorPatterns: ["auth.*fail", "unauthorized", "invalid.*token"],
    },
  });

  log(`\n[demo] PART A terminal_status: ${result.terminal_status}`);
  log(`[demo] PART A halted_reason: ${result.halted_reason ?? "<none>"}`);

  const dest = resolve(__dirname, "artifacts");
  await copyArtifacts(repoRoot, dest);
  log(`[demo] PART A artifacts → ${dest}`);

  await rm(repoRoot, { recursive: true, force: true });

  // ─── PART B — Direct adapter soak, compressed ─────────────────────
  log("\n" + "═".repeat(72));
  log("PART B — Direct adapter baseline + soakWindow (compressed timing)");
  log("═".repeat(72));

  const soakRoot = await buildFixture();
  log(`[demo] soak fixture at ${soakRoot}`);

  log("[demo] calling pythonCliAdapter.baseline() with 2-second window...");
  const baseline = await pythonCliAdapter.baseline({
    mode: "baseline",
    repoRoot: soakRoot,
    secretName: SECRET,
    durationMs: 2_000,
    patterns: [/auth.*fail/i, /unauthorized/i, /invalid.*token/i],
    hints: { smokeCommand, invocationCount: 2 },
  });
  log(
    `[demo] baseline result: ${JSON.stringify(
      { errorCount: baseline.errorCount, samples: baseline.samples.length },
    )}`,
  );

  log("\n[demo] calling pythonCliAdapter.soakWindow() with 2-second window...");
  const soak = await pythonCliAdapter.soakWindow({
    mode: "soak",
    repoRoot: soakRoot,
    secretName: SECRET,
    durationMs: 2_000,
    patterns: [/auth.*fail/i, /unauthorized/i, /invalid.*token/i],
    baseline,
    hints: { smokeCommand, invocationCount: 2 },
  });
  log(
    `[demo] soak result: ${JSON.stringify({
      errorCount: soak.errorCount,
      anomalyDetected: soak.anomalyDetected,
      verdict: soak.verdict,
    })}`,
  );

  await fs.writeFile(
    resolve(dest, "soak-direct-result.json"),
    JSON.stringify({ baseline, soak }, null, 2),
    "utf8",
  );

  await rm(soakRoot, { recursive: true, force: true });

  // ─── Final transcript ───────────────────────────────────────────────
  await fs.writeFile(
    resolve(dest, "stdout-transcript.txt"),
    logs.join("\n"),
    "utf8",
  );

  log("\n[demo] complete. all artifacts in artifacts/");

  if (result.terminal_status !== "ROTATED") process.exitCode = 1;
}

main().catch((err) => {
  console.error("[demo] FATAL:", err);
  process.exitCode = 2;
});
