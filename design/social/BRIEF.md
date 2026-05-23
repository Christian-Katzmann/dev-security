# Social preview brief — DëvSec

This file specifies the GitHub social preview for the dëv-security repository.
Render once, upload via Settings → Social preview, then leave it alone — a single durable preview beats versioned ones.

## Specs

- **File:** `design/social/social-preview.png` (this folder)
- **Dimensions:** 1280 × 640 (GitHub-recommended; do not deviate — smaller crops poorly, larger is wasted bytes)
- **Format:** PNG, 24-bit, < 1 MB
- **Color profile:** sRGB

## Composition

A 60 / 40 horizontal split. Identity on the left, substance on the right, anchored to a single strong horizontal third.

### Left pane (760 × 640) — identity

- **Wordmark `{ DËVSEC }`** at ~140 pt, centered vertically within the upper two-thirds of the pane.
  - Source: the same wordmark used on the dashboard brand mark — extract from `assets/security-observatory-brand-sheet.png` or `assets/security-observatory-logo.png`.
  - Type: Eczar (or the brand's chosen serif). The curly braces are part of the wordmark, not decoration — keep their weight and spacing as shown on the brand sheet.
- **Positioning sentence** directly below the wordmark at ~32 pt, two lines maximum:

  > Local-first security observability.
  > Scan, audit, recover — without sending your code anywhere.

  Sentence case. No marketing punctuation.

### Right pane (520 × 640) — substance

A tight crop from `design/screenshots/01-overview.png` (the canonical dashboard hero in the new screenshot system):

- **Crop region:** the sage-green hero banner at the top of the dashboard, including the `POSTURE 0.0 / 10` chart, the title line `CRITICAL: stdlib dependency vulnerability CVE-2025-68121`, and the `OPEN FINDINGS` header card directly below it.
- **Treatment:** no browser chrome, no fake device frame, no shadow, no perspective tilt. The crop is the substance itself.
- **Fit:** the crop occupies ~80% of the right pane vertically, with the cream background filling the margin so both panes share one continuous backdrop.

The right pane proves the project exists and shows real demo data; the left pane gives it a name to remember. Neither overpowers the other.

## Palette

All values sampled from the brand sheet:

| Color | Hex | Use |
|---|---|---|
| Charcoal | `#2A2A2A` | Wordmark letters, positioning sentence |
| Cream | `#EDE4D6` | Background (both panes) |
| Mustard | `#C89A4C` | Curly braces in wordmark, nothing else |
| Sage | `#7A8D7A` | Carried in from the dashboard crop only — do not paint it onto the left pane |

No gradients. No drop shadows. No glows. No additional colors. No startup-purple, no signal-red.

## Typography

- **Wordmark:** Eczar (or whatever the brand sheet uses). Must match the wordmark on the dashboard exactly — the social preview should read as the same project, not a different brand.
- **Positioning sentence:** A neutral grotesk that pairs with Eczar — Inter or IBM Plex Sans both work. Sentence case. No all-caps.

If unsure which sans pairs best, sample the dashboard's body type and use that.

## Negative space

~30–35% air across the composition. The wordmark does not crowd the positioning sentence; the dashboard crop does not crowd the right edge. Treat the file as a gallery poster, not a billboard.

## Hard rejections

- No badges (no shields.io, no star count, no version)
- No "PLEASE STAR" or "GIVE US A STAR" callouts
- No emoji
- No taglines like "Stop sending your code to the cloud!"
- No icons beyond the wordmark's own curly braces
- No marketing claims ("Now with AI!", "Free forever")
- No GitHub or product logos overlapping the composition
- No bullet lists of features

## Test criterion

Render the file, then view it at Slack-thumbnail size (~150 × 75 px). At that size:

- The wordmark must still read as `DËVSEC` (the braces will smudge — that is fine; the letters cannot).
- The phrase "Local-first" must still be legible.
- The right pane should still read as a software dashboard, not abstract shape.

If any of those fail, the composition is too crowded. Reduce, do not enlarge.

## Upload

Once rendered:

1. Save as `design/social/social-preview.png`.
2. GitHub → repository → Settings → Social preview → Upload image.
3. Verify the unfurl by pasting the repo URL into a Slack DM to yourself — the unfurl should show the preview, not the default GitHub language card.

## Not in scope

- Per-release variants (one durable preview beats versioned ones)
- Animated previews (GitHub does not render motion in unfurls)
- Localized variants (one English preview)
- Twitter-card overrides (GitHub's preview is also what Twitter and Slack unfurl)
