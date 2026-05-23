# Screenshot captions

Captions used in the README and any external surface that links to these screenshots. Single source of truth — if the dashboard changes shape enough that a caption no longer reads as a true claim, the screenshot must be regenerated and the caption updated here.

Rules every caption follows (v3 §6, §8):

- **One sentence.** Two only if the second clause is the unfakeable proof.
- **Says what's *proven*, not what's depicted.** "The dashboard view" is weak. "The dashboard groups raw scanner output into action-level cases" is real.
- **Realistic demo data preserved.** Every caption references the same scan thread (500 findings, 0.0 / 10 posture, stdlib CVE-2025-68121) so the screenshots feel like one continuous session, not four unrelated demos.
- **No marketing voice.** Sentence case. No "powerful", "industry-leading", "production-grade".

## System

- **Theme:** all-light.
- **Aspect ratio:** 16:10 (originals captured at 600×375 and 720×450).
- **Demo data thread:** same scan, same repo (DëvSec scanning itself), same posture and finding counts across all four.
- **No fake affordances:** every visible button, pill, and label corresponds to a real handler in the running app. The pre-campaign "Agent live · tailing scanners" pill is absent from every shot in this folder; that pill was removed in Step 1.2 of the public-repo-ready campaign and any screenshot containing it is stale.

## Captions

### `01-overview.png` — Overview

> *The dashboard groups raw scanner output into action-level cases — each carries plain-English risk, severity, and an agent-ready handoff prompt. The 0.0 / 10 posture is real: this is DëvSec scanning itself.*

### `02-recovery-playbooks.png` — Recovery playbooks

> *Cases roll up into category-level playbooks — 41 stdlib CVE findings become one "Upgrade vulnerable dependencies" playbook with steps, a wall-clock estimate, and an AI-prompt handoff, not 41 separate tickets.*

### `03-tool-catalog.png` — Tool Catalog

> *Every scanner is named with install state (built-in, detected-locally, managed-install, coming soon) and a per-tool policy that gates network access, credentials, and file writes — the catalog is the contract; nothing runs that hasn't been approved in it.*

### `04-settings.png` — Settings and data coverage

> *Repository snapshots, history records, and active findings are stored in local SQLite under `~/.security-observatory`; the Settings page shows you what the dashboard has on hand and reinforces that reports never leave the machine unless you export them.*

## Replacement protocol

When the dashboard changes enough to invalidate a screenshot:

1. Capture the replacement at the same aspect ratio (16:10) and theme (light) as the rest of the system.
2. Verify the same demo-data thread (same repo, same findings count, same posture).
3. Replace the file in `design/screenshots/` keeping the same filename.
4. Update the caption above if the claim it makes no longer holds.
5. Verify the README still reads cleanly with the new image.

Do not introduce mixed themes, mixed aspect ratios, or mismatched demo data — the screenshot system is the visual contract for the project's visual surface, and consistency is what makes the dashboard look like a product instead of a series of unrelated demos.
