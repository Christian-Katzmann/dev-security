# Tool Catalog Storefront UX Plan

This plan translates the catalog contract in `docs/tool-catalog.md` into the dashboard storefront. The storefront is read-only for the MVP: it explains supported coverage, local readiness, safety policy, and future packs without changing scanner execution, installing tools, or making External Surface feel usable.

## Human Context Contract

- User likely arrives feeling: curious, cautious, and not fully sure which scanners are safe or useful.
- Prior context they may carry: scanner names are technical, not-installed tools can feel like broken protection, and security products often blur local scans with cloud behavior.
- What they fear getting wrong: running a tool that leaves the Mac, needs credentials, writes files, scans an external target, or gives false confidence.
- What getting it wrong costs: unwanted network activity, leaked source or secrets, repository damage, or trusting coverage that is not really present.
- Their likely bandwidth: low to medium. The catalog must work at a glance before it rewards deeper reading.
- What they need to trust: clear install state, clear local/network boundaries, honest Coming Soon treatment, and visible approval points.
- Where they need agency: before network use, credential use, target entry, file writes, install, uninstall, destructive behavior, or Agent Lab execution.
- What the product must not do: sell advanced tools as toys, hide policy behind friendly labels, or imply future coverage already ran.

## Navigation

Rename the current `Scanners` tab to `Tool Catalog` in the first implementation pass.

This is the cleaner product model because the backend already exposes `tool_catalog` types and the README now frames Tool Catalog as a current feature. The trade-off is that the screen must be explicit that install/uninstall controls are not ready. Keep the existing scan-running behavior behind the current "Run checks" and profile picker flow; do not introduce one-click install, uninstall, or pack-run actions.

Recommended structure inside the tab:

1. Catalog header with search, a short coverage summary, and runtime counts.
2. Browse controls for category, pack, status, and safety labels.
3. Featured packs as compact filter cards, not full pack pages.
4. Tool grid with compact cards.
5. Detail panel or detail page for the selected tool.
6. Scanner doctor and last-run status folded into detail and Verification, not removed.

Use "Tool Catalog" in navigation and "Scanner doctor" only for the diagnostic status section.

## Browse IA

The browse view should help users answer four questions in this order:

1. What can DëvSec check?
2. Can this Mac run that check now?
3. What safety boundary applies?
4. Which pack or scan profile uses it?

Primary controls:

- Search across tool label, summary, category, profile, pack, and scanner key.
- Category segmented filter with an `All` option.
- Pack filter for Starter, Secrets, Dependencies, AI Agent, and future packs.
- Status filter for Ready, Needs setup, Not installed, Advanced, and Coming soon.
- Safety filter for Local, Optional network, Network required, Needs credentials, Approval required, and Agent Lab blocked.

Default view:

- Show all normal MVP tools and built-in checks.
- Include visible Coming Soon pack cards.
- Keep `legitify`, `malcontent`, and `checkov` out of the default grid unless the user selects Advanced, Platform Posture, Advanced Dependency, IaC, or searches for them.
- External Surface appears only as a Coming Soon pack/card with no target input and no run path.

## First-Class Categories

Use the stable category ids from `docs/tool-catalog.md`. Display labels can be friendlier, but the ids should drive filters and pack composition.

| Category id | Display label | Default treatment |
| --- | --- | --- |
| `code-security` | Code security | First-class |
| `secrets` | Secrets | First-class |
| `dependencies` | Dependencies | First-class |
| `supply-chain` | Supply chain | First-class |
| `ai-agent` | AI agent | First-class |
| `defense-intel` | Defense intel | First-class, lower priority |
| `infrastructure` | Infrastructure | Visible through IaC/advanced context |
| `platform-posture` | Platform posture | Advanced or Coming Soon context |
| `external-surface` | External surface | Coming Soon only |

## Card Hierarchy

Tool cards should be compact, scannable, and policy-led. Use the catalog mockups for density, icon placement, and filter rhythm, but not their install claims or marketplace language.

Card content order:

1. Category icon and status pill.
2. Tool label.
3. One-line plain-English summary.
4. Two or three priority safety labels.
5. Pack badges.
6. Profile or last-run hint.
7. Passive action: "View details".

Avoid primary buttons on cards for install or run. If a tool is runnable today, running still happens through the existing scan/profile chooser so behavior stays unchanged.

Status pill priority:

1. `Display only` for `coming-soon`.
2. `Needs setup` for `not-configured`.
3. `Unavailable` for environment or prerequisite blocks.
4. `Not installed` for supported external binaries not detected.
5. `Detected locally` for user-owned binaries on PATH.
6. `Built in` for DëvSec-owned scanner logic.
7. `DëvSec managed` only when a managed-tool registry exists.

## Pack Membership Badges

Show pack membership as small badges on tool cards and in detail:

- `Starter`
- `Secrets`
- `Dependencies`
- `AI Agent`
- `IaC`
- `Platform Posture`
- `Advanced Dependency`
- `External Surface`

Badge role treatment:

- Included: normal badge.
- Optional: normal badge with "optional" text in detail only.
- Coming soon: muted badge plus `Display only` safety label.

Packs help users understand jobs. They must never imply pack-level permissions override tool-level policy.

## Coming Soon Pack Cards

Feature Coming Soon packs in a small "Future coverage" section below the active pack filters or after the primary tool grid. These are educational tiles, not CTAs.

Required Coming Soon behavior:

- No target fields.
- No scan buttons.
- No install or uninstall buttons.
- No Agent Lab action.
- No "run pack" language.
- Copy explains what future coverage will mean and why it is not active yet.

External Surface copy example:

> External Surface will cover domain and internet-facing checks after DëvSec has target approval controls. It is display-only in this version.

## Tool Detail Model

Use either route-like internal state or a persistent side panel. For the current single-page dashboard, a right-side detail panel is the best first pass because it preserves the existing `ScannersView` pattern and avoids adding routing complexity.

Detail sections:

1. Header: label, category, lifecycle/status, owner, and selected pack badges.
2. Purpose: what the tool is for in one or two plain sentences.
3. What it checks: capabilities and evidence types.
4. Current availability: install state, runtime status, last run, findings count, affected repos, and error if present.
5. Safety and permissions: derived safety labels plus a short policy summary.
6. Scan profiles: profiles that include the tool and whether each is default, opt-in, advanced, or future.
7. Setup: install instructions or human setup requirements when relevant.
8. Actions: existing run/profile controls only; disabled preview controls for future install/uninstall if shown at all.
9. Docs: internal docs path and external homepage when available.

Do not hide runtime truth. A catalog entry can say a tool is supported; the detail panel must still show whether it actually ran, was not installed, errored, or has not run for the selected repo.

## Safety Label Display

Safety labels must be derived from policy, lifecycle, and install fields. They are not marketing copy and should not be duplicated as hand-authored card labels.

Display priority:

1. Boundary: `Local`, `Optional network`, `Network required`, or `Sends source off machine`.
2. Credential: `No credentials` or `Needs credentials`.
3. Action safety: `Read-only`, `Writes files`, `Approval required`, or `Destructive`.
4. Agent permission: `Agent Lab allowed` or `Agent Lab blocked`.
5. Lifecycle/install: `Display only`, `Detected locally`, `Built in`, or `DëvSec managed`.

Use neutral or info treatment for setup and policy states: `Network required`, `Needs credentials`, `Approval required`, `Writes files`, `Destructive`, `Unavailable`, `Not installed`, `Not configured`, `Advanced`, and `Coming soon`. Severity colors stay reserved for security severity.

## Install-State Display

Use the install states from `docs/tool-catalog.md` exactly:

| Install state | User-facing meaning | UI treatment |
| --- | --- | --- |
| `built-in` | Built into DëvSec. No install needed. | Ready, calm positive |
| `managed` | DëvSec owns the managed install. | Future-ready label only when registry exists |
| `detected` | Found locally, but user-owned. | Ready, with user-owned note |
| `missing` | Supported but not available on this Mac. | Display as `Not installed`; needs install guidance |
| `unavailable` | Cannot run in this context. | Explain blocker |
| `not-configured` | Installed but needs credentials, artifacts, cache, or repo context. | Explain setup |
| `coming-soon` | Display-only future coverage. | Disabled educational tile |

Uninstall posture must be visible before future uninstall controls exist:

- Built-in: no uninstall.
- Detected/user-owned: DëvSec cannot uninstall.
- Manual-only: DëvSec can guide setup but does not own cleanup.
- DëvSec-managed: only after the managed registry exists.

## Plain-English Copy Rules

- Prefer "checks", "coverage", "local", "needs setup", and "display only".
- Avoid "deploy", "one-click install", "plugin store", "system secure", and broad "verified" claims unless backed by fields.
- Explain risk boundaries before actions, not in hidden tooltips.
- Say what happens locally and what may leave the machine.
- Treat not-installed tools as setup gaps, not security failures.
- Treat Coming Soon as future coverage, not broken protection.
- For advanced tools, explain the prerequisite first: credentials, network, artifact cache, previous scan, repo remote, or target approval.

Dangerous or advanced tools should feel serious and bounded, not attractive. The done-well bar: a low-bandwidth user can tell "I should not run this unless I understand the prerequisite" without feeling shamed or tempted by dramatic copy.

## Existing Scanners View Evolution

Keep the current `ScannersView` implementation shape, but change its meaning:

- Rename tab title and nav item to `Tool Catalog`.
- Use `toolCatalogItems(summary)` when present, with `scannerDoctorGroups(summary)` as compatibility/runtime status.
- Keep the existing scanner catalog fallback until API payloads fully migrate.
- Replace scanner bars with real catalog metadata: status, safety labels, pack badges, and profile hints.
- Move "Run now" and "Choose profile" into the detail panel so card browsing does not imply one-click execution.
- Keep scanner doctor rows in Verification and optionally link from each tool detail.
- Preserve every existing scan-running path and API call.

Implementation must not make UI-only availability states. If runtime detection does not know a tool is ready, the UI should say supported or detected according to the available field, not runnable.

## Implementation Preservation Notes

- Do not solve trust with warmer copy while leaving risky actions visually available.
- Do not show External Surface target input, scan execution, install action, or Agent Lab action in this campaign.
- Do not show full pack pages or pack-run flows here; the Managed Security Packs campaign owns that.
- Do not claim install, update, or uninstall ownership for user-installed tools.
- Do not treat a Coming Soon pack as degraded protection.
- Do not use the dark mockup as the default page mood. The light Mistglass design system stays canonical.
- Do not let category filters hide the scanner doctor truth for a selected repo.

## User-State Acceptance Scenarios

Given the user is cautious and unsure what leaves their machine, when they browse a tool card, they can see local/network and credential labels before opening detail or running anything.

Given the user sees a not-installed scanner, when they open detail, they can tell it is a setup gap and not proof the repository is unsafe.

Given the user sees External Surface, when they inspect it, they cannot enter a domain, start a scan, install a tool, or trigger Agent Lab.

Given the user is reviewing advanced platform posture, when they inspect `legitify`, they see network and credential requirements before any profile run is offered.

Given the user wants a simple starter scan, when they filter to Starter, they mostly see local, read-only, default-enabled tools and are not asked to reason about advanced artifacts or credentials.
