#!/usr/bin/env tsx
/**
 * Demo 1 — Vercel-shape end-to-end rotation against a mock adapter.
 *
 * Why a mock instead of a real Vercel project:
 *
 *   The skill's safety rails explicitly forbid running `vercel --prod`
 *   without per-invocation operator approval. This step runs fully
 *   autonomously inside `claude --print` — no operator is in the loop to
 *   approve a real production deploy. The campaign's open question covers
 *   exactly this case: "if no Christian Next.js project is conveniently
 *   scaffold-ready, fall back to a minimal test fixture. Document the
 *   choice."
 *
 *   A second concern: a real soak window is 10–60 minutes (default 15).
 *   A single-session autonomous demo cannot sit on that wall-clock sleep
 *   AND finish in the session's budget — see Demo 2 for the same
 *   constraint.
 *
 * What this demo proves:
 *
 *   - The pipeline's full Vercel-shape state machine runs end-to-end:
 *     HEALTH_CHECK → PREFLIGHT → ACQUIRE → STAGE_CANARY → DEPLOY_CANARY
 *     → VERIFY_CANARY → STAGE_PROD → DEPLOY_PROD → VERIFY_PROD → SOAK →
 *     IN_GRACE.
 *   - A Class B-API rotation reaches IN_GRACE with a real verification
 *     receipt written to `data/rotation-receipts/`.
 *   - The receipt renders the Vercel-flavored scope statement
 *     ("Vercel preview + production env writes…tailing `vercel logs`").
 *
 * What this demo does NOT prove:
 *
 *   - That the real `vercel` CLI calls in `templates/adapters/vercel.ts.tmpl`
 *     work as documented. That's covered by manual operator-supervised
 *     rotations on Christian's real Next.js + Vercel projects (out of
 *     scope for this autonomous session).
 *
 * Output (artifacts/):
 *   - rotation-state.json
 *   - <secret>-<ts>.md         (verification receipt)
 *   - rotation-log.jsonl       (step trail)
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

const SECRET = "ANTHROPIC_ADMIN_KEY";
const INITIAL = "sk-ant-fake-initial-value-0001";
const NEW_VALUE = "sk-ant-fake-rotated-value-0002";

interface VercelMockAdapterShape {
  stackName: "vercel";
  envStore: Map<string, { canary?: string; prod?: string }>;
  calls: string[];
}

function makeVercelMockAdapter(): VercelMockAdapterShape & Record<string, any> {
  const envStore = new Map<string, { canary?: string; prod?: string }>();
  envStore.set(SECRET, { canary: INITIAL, prod: INITIAL });
  const calls: string[] = [];

  const adapter: any = {
    stackName: "vercel" as const,
    envStore,
    calls,

    async detect() {
      calls.push("detect");
      return true;
    },

    async preflight() {
      calls.push("preflight");
      return { ok: true };
    },

    async readCurrentValue({ name }: any) {
      calls.push(`readCurrentValue:${name}`);
      const v = envStore.get(name)?.prod;
      if (!v) throw new Error(`mock vercel: ${name} not present in env`);
      return v;
    },

    async ensureNoDrift({ name }: any) {
      calls.push(`ensureNoDrift:${name}`);
    },

    async writeEnv({ name, value, target }: any) {
      calls.push(`writeEnv:${name}:${target}`);
      const entry = envStore.get(name) ?? {};
      entry[target] = value;
      envStore.set(name, entry);
    },

    async deploy({ target }: any) {
      calls.push(`deploy:${target}`);
      // Vercel-shape DeploymentRef so the receipt renders Vercel-flavored.
      return {
        kind: "vercel" as const,
        target,
        url:
          target === "canary"
            ? "https://moneyapp-git-rotation-cw7-katzmann.vercel.app"
            : "https://moneyapp.vercel.app",
        deploymentId: `mock-vercel-deploy-${target}-${Date.now()}`,
      };
    },

    async applicationProbe({ secretName, deployment }: any) {
      calls.push(`applicationProbe:${secretName}:${deployment?.target}`);
      const url =
        deployment?.target === "canary"
          ? "https://moneyapp-git-rotation-cw7-katzmann.vercel.app/api/health/auth-secret"
          : "https://moneyapp.vercel.app/api/health/auth-secret";
      return { ok: true as const, probedEndpoint: url };
    },

    async baseline() {
      calls.push("baseline");
      return {
        errorCount: 0,
        observedDurationMs: 5 * 60_000,
        samples: [],
        context: {
          stackName: "vercel",
          secretName: SECRET,
          logSource: "vercel logs",
        },
      };
    },

    async soakWindow(opts: any) {
      calls.push(`soakWindow:${opts.durationMs}`);
      return {
        errorCount: 0,
        anomalyDetected: false,
        verdict: `Soak clean: 0 new auth-error pattern matches in ${
          opts.durationMs / 60_000
        } min window vs baseline 0.`,
        observedDurationMs: opts.durationMs,
        samples: [],
        context: {
          stackName: "vercel",
          secretName: SECRET,
          logSource: "vercel logs",
        },
      };
    },

    async rollback({ name, previousValue }: any) {
      calls.push(`rollback:${name}`);
      const entry = envStore.get(name) ?? {};
      entry.prod = previousValue;
      entry.canary = previousValue;
      envStore.set(name, entry);
    },
  };

  return adapter;
}

function makeClassBApiPlugin() {
  return {
    secretName: SECRET,
    secretClass: "B-API" as const,
    async preflight() {
      return { ok: true as const };
    },
    async acquire() {
      return {
        newValue: NEW_VALUE,
        newValueFingerprint: "fp-mock-" + NEW_VALUE.slice(0, 16),
        newKeyId: "key_mock_rotated_id",
        oldKeyId: "key_mock_initial_id",
      };
    },
    async verify() {
      return {
        ok: true as const,
        probedEndpoint: "https://api.anthropic.com/v1/admin/me",
      };
    },
    async revoke() {
      return { ok: true as const };
    },
  };
}

async function buildFixture(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "demo-vercel-"));
  // No special files needed — the mock adapter ignores repoRoot for
  // detection. Just initialize the state file the pipeline reads.
  await fs.mkdir(join(root, "data"), { recursive: true });
  await fs.writeFile(
    join(root, "data/rotation-state.json"),
    JSON.stringify(
      {
        version: 1,
        repo_name: "money.com (demo fixture)",
        scaffolded_at: new Date().toISOString(),
        scaffolded_version: "v0.2-foundation",
        secrets: [{ name: SECRET, class: "B-API" }],
        rotations: [],
      },
      null,
      2,
    ),
    "utf8",
  );
  return root;
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
}

async function main(): Promise<void> {
  // @ts-expect-error — dynamic import of rendered TS via tsx
  const { runRotation } = await import(resolve(SKILL_BUILD, "lib/pipeline.ts"));

  const logs: string[] = [];
  const log = (line: string): void => {
    logs.push(line);
    process.stdout.write(line.endsWith("\n") ? line : line + "\n");
  };

  log("═".repeat(72));
  log("Demo 1 — Vercel-shape rotation via mock adapter");
  log("═".repeat(72));
  log("(Real Vercel deploys are gated by skill safety rails — see");
  log(" header docs at the top of this file for the rationale.)");
  log("");

  const repoRoot = await buildFixture();
  const adapter = makeVercelMockAdapter();
  log(`[demo] fixture at ${repoRoot}`);
  log(`[demo] secret: ${SECRET} (Class B-API, 24h grace window)`);
  log(`[demo] adapter: mock Vercel (stackName=${adapter.stackName})`);

  const result = await runRotation({
    repoRoot,
    secretName: SECRET,
    trigger: "cli",
    adapter,
    loadPlugin: async () => makeClassBApiPlugin(),
    log,
    verifyBackoffMs: [1, 1, 1],
    healthCheckDurationMs: 100,
    // Soak duration is observed by the mock — no real wall-clock sleep.
    soakDurationMs: 15 * 60_000,
  });

  log(`\n[demo] terminal_status: ${result.terminal_status}`);
  log(`[demo] halted_reason: ${result.halted_reason ?? "<none>"}`);
  log(`\n[demo] adapter call sequence (${adapter.calls.length} calls):`);
  for (const c of adapter.calls) log(`  - ${c}`);

  const dest = resolve(__dirname, "artifacts");
  await copyArtifacts(repoRoot, dest);
  log(`\n[demo] artifacts copied to ${dest}`);

  await fs.writeFile(
    resolve(dest, "stdout-transcript.txt"),
    logs.join("\n"),
    "utf8",
  );

  await rm(repoRoot, { recursive: true, force: true });

  // Class B-API rotation reaches IN_GRACE, not ROTATED (the grace window
  // is honored — REVOKE runs later via cron or next invocation).
  if (result.terminal_status !== "IN_GRACE") process.exitCode = 1;
}

main().catch((err) => {
  console.error("[demo] FATAL:", err);
  process.exitCode = 2;
});
