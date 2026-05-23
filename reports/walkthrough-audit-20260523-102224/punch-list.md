# DëvSec — Product walkthrough audit

Audit ID: `walkthrough-audit-20260523-102224`
Date: 2026-05-23
Mode: `no-ai` (project documents no cloud LLM calls; nothing to budget)
Surfaces planned: 38 · visited: 21 · coverage_ratio: 0.55 · complete: false

> Scope note: this audit deliberately did NOT click destructive actions (Retire honey key, Run all, Install plugin on a real third-party tool, Start check) because they would mutate the user's local state, install software via Homebrew, or kick off real scans. Several detail pages were also not opened individually. See `coverage-receipt.json` for the full plan-vs-visited breakdown.

## Summary

DëvSec's surfaces are calm, well-typed, and largely honest. The recent `catalog-polish` campaign cleaned up the biggest dishonesties (Snooze button gone, pack-page CTAs collapsed into a calm note, Read documentation linked to homepages for external tools). What remains is a quieter layer of lies — small affordances that look real but aren't wired up, language that promises more than the build does, and one whole category of "agent" presence that exists only in CSS.

The findings cluster into three patterns:

1. **Ambient theater.** Sidebar shows "Agent live · tailing scanners"; an Agent header pill turns blue and pulses. There is no agent. The toggle is `useState`.
2. **Universal "Install plugin" label on tools that can't be installed.** Built-in tools, locally-detected tools, and never-installable tools all carry the same Install button. The state is shown elsewhere on the card, but the button label keeps promising.
3. **Silent gates.** Pressing primary actions (Rerun checks, Run all, Start check, Open profile) when the workspace target is the catch-all "Dashboard" produces no result and no explanation. The button either does nothing, or opens a sheet whose Start button is disabled with no helper.

The Catalog itself is in good shape post-polish; most damage is one level out.

---

## USER-BLOCKING

*(Findings where a first-time user cannot complete the obvious task. None — every blocker has a workaround like "select a repo first" — but two are close.)*

### F-001 · "Run all" silently disabled with no explanation when default target is selected
- **Surface:** Header toolbar (all routes), workspace target = `dashboard`
- **Category:** user-blocking
- **Severity:** medium
- **User expectation:** "Run all" sits next to the workspace title with a refresh icon. A first-time user assumes clicking it runs every scanner on whatever is selected. It's the most visible CTA on every screen.
- **Reality:** Button is dimmed/disabled. No tooltip on hover. No helper note. The reason is `canRun={target.type === 'repo'}` (App.tsx:748) — the default target on first load is the synthetic `dashboard` aggregate, which isn't a repo. New user has no way to know they must first pick a real repo from the dropdown.
- **Repro steps:** Open dashboard at `http://127.0.0.1:8766` → button "Run all" is visible, dimmed → hover → no tooltip → click → no response.
- **Evidence:** [overview-initial.png](evidence/overview-initial.png), [F001-fake-agent-toggle.png](evidence/F001-fake-agent-toggle.png) (same toolbar)
- **Console:** none
- **Fix hypothesis:** Either (a) auto-select last-scanned repo on first load instead of `dashboard`, or (b) keep button enabled, click opens a "Choose a repo first" picker, or (c) add a `title=`/aria-label explaining the gate.

### F-006 · "Rerun checks" on Recovery playbooks is a no-op when target = dashboard
- **Surface:** Recovery playbooks, header button on each playbook card
- **Category:** user-blocking
- **Severity:** medium
- **User expectation:** Clicking "Rerun checks" on a playbook should open the scan-check sheet (or run the matching scanner). On a screen that exists only because there ARE findings to fix, "Rerun checks" is the obvious next action.
- **Reality:** Click → no UI change, no sheet, no error. The underlying `setIsCheckOpen(true)` is immediately reverted by `useEffect(() => { if (target.type === 'dashboard') setIsCheckOpen(false); }, [target])` (App.tsx:609). The user has no way to discover this gate from the UI.
- **Repro steps:** Default target "dashboard" → sidebar → Recovery playbooks → click "Rerun checks" on any card → nothing happens, no network activity.
- **Evidence:** [recovery-playbooks.png](evidence/recovery-playbooks.png)
- **Console:** none
- **Fix hypothesis:** Same as F-001 — surface the "needs a repo target" gate. The cleanest move is to render the playbooks page with a top-of-page "Switch to the repo where the finding lives" picker when target=dashboard, instead of pretending the button works.

---

## POLISHED-BUT-LYING

*(UI looks done, but the action doesn't really work or doesn't match the copy.)*

### F-002 · "Pause agent" / "Resume agent" toggle has no agent
- **Surface:** Header toolbar (every route) + sidebar status pill ("Agent live · tailing scanners")
- **Category:** polished-but-lying
- **Severity:** high (top of every page, signals system state)
- **User expectation:** "Agent live · tailing scanners" + a Pause button next to a live indicator dot reads, to any reasonable user, as a live process monitoring scanners in the background. Pause should stop something — at minimum stop tailing the latest scan log.
- **Reality:** No agent exists. `agentRunning` is a single `useState(true)` (App.tsx:561). Clicking Pause flips a boolean that controls only the dot color and the words next to it ("live · tailing scanners" ↔ "paused · tap resume"). No backend call. No scanner is paused. Nothing is being tailed.
- **Repro steps:** Open dashboard → sidebar reads "Agent live · tailing scanners" → click toolbar pause icon → sidebar reads "Agent paused · tap resume" → check network panel → 0 requests fired.
- **Evidence:** [F001-fake-agent-toggle.png](evidence/F001-fake-agent-toggle.png)
- **Console:** none
- **Fix hypothesis:** Either (a) wire it to a real long-poll of `/api/check-status` or scan tail, or (b) drop the agent metaphor entirely — replace the pill with something honest like "Last refresh 10:22 AM" and a Refresh button. The current copy makes promises the product doesn't keep.

### F-003 · "Read documentation" delivers raw unrendered markdown
- **Surface:** Tool detail page sidebar — applies to every built-in tool whose `docs_path` points at the local `docs/` folder (Built-in AI static checks, IOC Watch, External Surface, Install hook classifier, Workflow surface audit). External tools (Trivy, Gitleaks, etc.) link to vendor sites and render fine.
- **Category:** polished-but-lying
- **Severity:** medium
- **User expectation:** "Read documentation" is the canonical user-facing label for "show me the manual page." A reasonable user clicks it expecting a styled docs page — headings, code blocks, a table of contents.
- **Reality:** The link opens `http://127.0.0.1:8766/docs/<file>.md` which is served as `Content-Type: text/markdown`. The browser displays this as a wall of plain text, raw `#` and `|` characters and all. There is no markdown renderer.
- **Repro steps:** Tool Catalog → Browse all tools → View Built-in AI static checks → sidebar → click "Read documentation" → new tab shows raw markdown text.
- **Evidence:** [F003-docs-raw-markdown.png](evidence/F003-docs-raw-markdown.png)
- **Console:** none
- **Fix hypothesis:** Either (a) ship a small in-app markdown renderer (`marked` or `react-markdown` already in the dashboard's likely-future dep set) at `/docs/<slug>` that fetches the .md and renders it, or (b) point `docs_path` at an external host (GitHub README URLs) like the external tools already do.

### F-004 · Trivy detail page invites you to "Install Trivy" when it's already detected locally
- **Surface:** Tool Catalog → View Trivy
- **Category:** polished-but-lying
- **Severity:** medium
- **User expectation:** If the page says "Install state: Detected locally" and shows "Trivy v0.70.0" then there is nothing to install. The user expects the install button to either disappear, become "Reinstall," or sit dim and inactive.
- **Reality:** "Install plugin" button is fully active and styled as the hero CTA. Underneath, NEXT STEP reads: *"Install Trivy, then rerun the dependency, secrets, IaC, or full scan."* — past tense for a present state. The Last runtime row just says "ran" with no timestamp. Clicking the button would call `installManagedTool('trivy')` and re-run a Homebrew install for a binary already on PATH.
- **Repro steps:** Catalog → Browse all tools → View Trivy → observe "Install state: Detected locally", "Version: Trivy v0.70.0", and an active "Install plugin" button next to NEXT STEP that says "Install Trivy, then rerun…"
- **Evidence:** [F004-trivy-detected-but-install.png](evidence/F004-trivy-detected-but-install.png)
- **Console:** none
- **Fix hypothesis:** Branch on `install_state`: when "Detected locally" — relabel button to "Reinstall via Homebrew" and recompute NEXT STEP to "Run a dependency, secrets, or IaC scan to use Trivy." Strip the "Install Trivy, then…" string from a `next_step` that fires before detection.

### F-005 · Settings → "Export" button has no onClick handler
- **Surface:** Settings → Privacy and storage → "Generated reports" row
- **Category:** polished-but-lying
- **Severity:** medium
- **User expectation:** A button labeled Export, with a download icon, in a row whose subtext says *"Reports remain local unless you export or share them"* — the user expects clicking to download or open an export dialog.
- **Reality:** Clicking does nothing. No network request fires. `<Button variant="secondary" size="sm" icon={<Download size={14} />}>Export</Button>` at App.tsx:1770 — no onClick prop, no handler attached.
- **Repro steps:** Sidebar → Settings → scroll to "Privacy and storage" → click "Export" → no UI change, no download, no console message, no network activity.
- **Evidence:** [settings.png](evidence/settings.png)
- **Console:** none
- **Fix hypothesis:** Either wire it to `/api/export` (and decide what an export means — zip of `reports/`? CSV of cases?), or take the button down until the export endpoint exists. A button on this row implies the feature is shipped.

### F-008 · "Open profile" on pack page opens a sheet whose Start button is disabled
- **Surface:** Tool Catalog → Starter Pack → "Recommended scan profile" → "Open profile"
- **Category:** polished-but-lying
- **Severity:** low-medium
- **User expectation:** "Open profile" with the surrounding copy "*Pair this pack with the quick profile when you are ready to run a scan*" reads as "show me the quick scan, I'll run it." The CTA should lead the user into a runnable state.
- **Reality:** Clicking "Open profile" while target=dashboard opens the "Run security check" sheet with heading "Choose a repo target." Start check is disabled, no tooltip explains why. Body says "Choose the scanners to run" — contradicts the heading. Same gate as F-001/F-006, but here the sheet appears (giving a partial sense of progress) before silently refusing.
- **Repro steps:** Default target "dashboard" → Catalog → Starter Pack → "Open profile" → sheet opens with title "Choose a repo target" and disabled Start check button. No way to choose the repo from inside the sheet.
- **Evidence:** [catalog-pack-starter.png](evidence/catalog-pack-starter.png)
- **Console:** none
- **Fix hypothesis:** When opened with target=dashboard, show a "Pick a repo" picker as the first row of the sheet, not a disabled Start button + a contradictory title.

### F-010 · "Connected platform" check sits as a peer in the run-check sheet without disclosing token requirement
- **Surface:** Run security check sheet (opened from Open profile, Run checks, Rerun checks, etc.)
- **Category:** polished-but-lying
- **Severity:** low-medium
- **User expectation:** Each checkbox in the run sheet represents a runnable scan. Selecting "Connected platform" and pressing Start should produce a connected platform check.
- **Reality:** The README explicitly states platform-posture *"asks legitify to inspect SCM settings"* and requires `SCM_TOKEN=<token>` to be set in the environment. The UI gives no in-product hint: just a 1-line description ("Optional token-backed branch, workflow, and SCM posture checks") and an enabled checkbox sitting alongside non-credential scans. A user enabling it without `SCM_TOKEN` set will get a skipped/partial scan with no in-app help.
- **Repro steps:** Open any run-check sheet → tick "Connected platform" → nothing in the UI links to "where do I add the token?" or "how do I configure this?"
- **Evidence:** (sheet visible in [verification.png](evidence/verification.png) bottom half)
- **Console:** none
- **Fix hypothesis:** Either (a) hide the option until `SCM_TOKEN` is detected on the server, or (b) keep it visible but add a "Needs token" badge that opens an inline note telling the user how to set `SCM_TOKEN` and re-launch the dashboard.

### F-012 · Built-in tools carry a universal "Install plugin" CTA on home-page cards
- **Surface:** Tool Catalog Home → "Popular plugins" cards
- **Category:** polished-but-lying
- **Severity:** low-medium
- **User expectation:** A clickable "Install plugin" button on a tool card promises an install path.
- **Reality:** The same button appears on built-in tools (Built-in AI static checks, Install hook classifier) and on already-detected tools. Clicking just routes to the detail page, where the install button is disabled and the helper text reveals the truth. The home-page card never softens its label — built-in and installable look identical.
- **Repro steps:** Catalog home → see four Popular plugins cards → "Install plugin" on each → click "Install plugin" on Built-in AI static checks → routes to detail page where the button is disabled with helper "Run a quick or AI scan to include this check."
- **Evidence:** [catalog-home.png](evidence/catalog-home.png), [F002-builtin-install-button.png](evidence/F002-builtin-install-button.png)
- **Console:** none
- **Fix hypothesis:** Compute the right verb per state on the home card too: "Already included" / "View tool" for built-in; "Install plugin" only when `previewCanInstall` is true. The detail page already does this — propagate it one level up.

---

## HALF-BUILT

*(Surface clearly partial, not labeled as such.)*

### F-007 · Recovery playbooks are 6 identical "Rotate live secret + scrub history" cards
- **Surface:** Recovery playbooks
- **Category:** half-built
- **Severity:** medium
- **User expectation:** "Recovery playbooks" plural implies different playbooks for different problem classes. With 11 critical, 123 elevated, 288 warning, and 2 low findings spanning leaked secrets, dependency CVEs, AI-agent risks, and hidden Unicode controls, a user expects categorized recovery guidance — at minimum one playbook per scanner family.
- **Reality:** Six identical cards, all titled "Rotate live secret + scrub history," all 4 steps, all sourcing from `gitleaks`. Steps 1–4 are identical and generic ("Capture evidence for…", "Rotate the credential…", "Rerun the matching DëvSec check", "Record the case decision when verified"). The only variance across the six is wall-clock estimate (one says 22 min, the other five say 12 min). Nothing for the 123 elevated AI-agent findings; nothing for the 13 critical Trivy/Grype CVE findings.
- **Repro steps:** Default target "dashboard" → sidebar → Recovery playbooks → scroll the list.
- **Evidence:** [recovery-playbooks.png](evidence/recovery-playbooks.png)
- **Console:** none
- **Fix hypothesis:** Generate one playbook per case-class (secret, dependency CVE, AI-config Unicode hazard, MCP shell-capable command, IaC misconfig), not per finding. Until per-class playbooks exist, label the screen "Cases waiting on Rotate live secret" instead of "Recovery playbooks" to stop overpromising variety.

### F-011 · Activity → "Audits · 24 H × 7 D" heatmap has no visible cells
- **Surface:** Activity (Records group)
- **Category:** half-built
- **Severity:** low
- **User expectation:** A heading "AUDITS · 24 H × 7 D" with day-of-week labels (Sun–Sat) sets the expectation for a heatmap or sparkline showing audit counts per hour-bucket per day. The single 24/7 visualization is the page's main affordance for "when did things happen?"
- **Reality:** The day labels render, but the chart area is empty — no cells, no bars, no gradient. The accessibility snapshot lists just `Sun … Sat` with no plot elements between them. Below it the "Event mix · 7 D" panel does have real numbers (Scanner runs: 13, Findings opened: 424), confirming there IS data to visualize.
- **Repro steps:** Sidebar → Activity → scroll to "AUDITS · 24 H × 7 D" → day labels are visible but no plot.
- **Evidence:** [activity.png](evidence/activity.png)
- **Console:** none
- **Fix hypothesis:** Render the heatmap or drop the heading. The "Event mix" block already does the same job in numbers — if the heatmap isn't shipping, replace its slot with a sparkline of scanner-runs-per-day so the section earns its space.

---

## STALE-PROMISE

*(A documented claim is no longer true.)*

### F-009 · README says health score is 0–100; UI displays it as `/10`
- **Surface:** Overview hero, header pill, KPI cards — everywhere posture is shown
- **Category:** stale-promise
- **Severity:** low
- **Claim:** `README.md` §Health Score: *"The final score is capped between 0 and 100."* — same value referenced in the Penalty table (-40, -25, -15, etc., capped at -80, -60, etc., all assuming a 0–100 base).
- **Reality:** The dashboard divides by 10 at the UI layer (App.tsx:312 `Math.max(0, Math.min(10, averageHealth(summary) / 10))`) and renders `3.3 / 10` and `10.0 / 10`. The CLI/reports presumably still emit the 0–100 score, so the same scan now displays as 33 in one place and 3.3 in another. A user reading the README's penalty table can't reconcile the math against the dashboard.
- **Repro steps:** Compare README §Health Score table (-40 for leaked secret, capped at -80) against any dashboard hero that shows "POSTURE 3.3 / 10".
- **Evidence:** [overview-initial.png](evidence/overview-initial.png) shows "3.3 / 10"; README claim is in `README.md`.
- **Console:** none
- **Fix hypothesis:** Pick one scale and propagate it. Cleanest fix is to update the README §Health Score table to express the displayed values (e.g. -4, -2.5, etc., on a 0–10 base) and call out that internally the score is computed on 0–100 but normalized for display. OR change the UI to show `33 / 100`.

### F-013 · "Last runtime: ran" with no timestamp on tool detail pages
- **Surface:** Tool detail → Setup and ownership → Last runtime
- **Category:** stale-promise (vs. own UI promise of a key/value record)
- **Severity:** very low
- **User expectation:** The row is laid out as a labeled spec row ("Last runtime: <value>"). Every other row in the panel carries a concrete value (Method: Homebrew, Owner: User-owned local install, Binary: trivy). The user reads "Last runtime" and expects a date or "Never."
- **Reality:** The value is the literal word "ran" — past tense verb with no when. Conveys neither "this scanner has run at some point" nor "this scanner ran 12 days ago."
- **Repro steps:** Catalog → View Trivy → scroll to Setup and ownership → Last runtime → "ran".
- **Evidence:** [F004-trivy-detected-but-install.png](evidence/F004-trivy-detected-but-install.png)
- **Console:** none
- **Fix hypothesis:** Either drop the row when there's no timestamp, or render "Last runtime: 12 d ago" / "Last runtime: Never run". The word "ran" alone fails the row's own format.

---

## Out of scope / not pursued

- **VERIFY / FALSE POSITIVE / ACCEPT RISK / MARK FIXED actions** — these open a native `window.prompt()` for an optional note. The prompt itself works; the UX of using a browser-native prompt for case decisions in 2026 is worth a separate UX-forensics pass but isn't lying about itself.
- **A11y nit** — Chrome reports `A form field element should have an id or name attribute (count: 2)`. Two unnamed form fields in the dashboard. Small fix, not user-blocking.
- **Tool detail pages NOT individually opened:** Checkov, Gitleaks, Grype, Install hook classifier, legitify, Medusa, OSV-Scanner, Semgrep, Syft, TruffleHog, Workflow surface audit. By inspection of catalog.py the same install-state pattern likely repeats — F-002/F-004/F-012 probably apply to those too.
- **Place new key (Honey Keys)** — gated behind a real repo selection; not exercised under no-mutations rule.
- **Add repo prompt** — clicked once; browser DevTools instance got into a locked state with the native `window.prompt` open and couldn't recover within the audit window. Worth a deeper look; likely the same primitive `window.prompt` pattern as VERIFY.
- **Run all / Start check** would have invoked actual scans against the user's local repos. Skipped on safety grounds.
