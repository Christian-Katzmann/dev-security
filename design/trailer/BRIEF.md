# Trailer brief — DëvSec

This file specifies the motion artifact for the dëv-security repository. It is the only source-of-truth for trailer scope, narrative arc, subtitles, demo data, and brand coherence. A producer session uses `/hyperframes` to render against this brief.

## What this trailer is

- **Shape:** 30–60 second polished trailer (v3 §11 default for product-shape repos with a real visible surface).
- **Audience:** a stranger landing on the GitHub repo who needs to decide in under a minute whether DëvSec is worth their attention.
- **Job:** prove the product exists, runs on real data, and respects the local-first stance the README claims.
- **Voice:** calm, honest, sentence case, no marketing energy. The same voice the README and `PROVOCATION.md` use.

## What this trailer is **not**

- Not a feature montage with rapid cuts and music swells
- Not a synthesized-voice narration ("DëvSec — the local-first security platform for modern teams!")
- Not a startup hero film with abstract motion graphics over a wordmark burst
- Not a product-marketing reel for an unreleased feature (everything shown must be the real, running product)
- Not a tutorial (no on-screen typing tutorials, no captioned-arrow callouts to UI elements)

If the result feels like a SaaS landing-page hero video, it's wrong. The trailer should feel like watching a careful engineer use the product, with quiet annotation.

## Specs

| Field | Value |
|---|---|
| Format | MP4, web-friendly H.264 codec |
| Resolution | 1920 × 1080 minimum; 2560 × 1440 if the dashboard captures well at that size |
| Aspect ratio | 16:9 |
| Length target | 45 seconds (acceptable range: 30–60 seconds) |
| Audio | No voiceover. Either: no audio track, or one quiet ambient bed (e.g. low-volume room-tone, no melody). |
| Subtitles | Embedded burned-in subtitles (not a sidecar `.srt` — the trailer plays muted in most contexts; subtitles must always be visible) |
| File size | < 10 MB if possible; < 25 MB hard cap |
| Output path | `design/trailer/trailer.mp4` |
| Embed plan | GitHub-native MP4 upload (matches the "no third-party tracking" stance — same call Microsoft made for AI-Engineering-Coach per v3 §11) |

## Narrative arc

Four beats, ~10–15s each. Subtitles below are the canonical script; tighten wording during production only if visually impossible to fit.

### Beat 1 — Problem (0:00 – 0:08)

**Visual:** Solid charcoal background (`#2A2A2A`). White subtitle text centered. No animation other than a slow ~0.5s fade-in.

**Subtitle:**
> Most security tools send your source code to a SaaS.
> DëvSec doesn't.

Hold the second line for 2 seconds before transition.

### Beat 2 — The invocation (0:08 – 0:22)

**Visual:** Terminal scene on cream background (`#EDE4D6`). A monospace terminal window appears mid-screen. The line `security-scan .` types itself (no faked-typing animation — paste-in is fine). Scanner output streams (real output, fast scroll — readability is not the point; presence of real output is). Then the terminal fades and the DëvSec dashboard fades in over it, anchored to the same horizontal third — the Overview hero we've been screenshotting (sage banner, posture chart, OPEN FINDINGS card).

**Subtitle (lower-third, simultaneous with dashboard reveal):**
> Scanners run on your machine.

Hold for 3 seconds while the dashboard finishes loading and the eye settles on the posture.

### Beat 3 — The case-and-handoff (0:22 – 0:38)

**Visual:** Camera (programmatic pan/zoom) moves from Overview → into a single case row in the Open Findings list. The case expands. The viewer sees the case's plain-English risk, severity, confidence, and the "AI prompt" button. Click. The agent-ready handoff prompt slides in as a card overlay, showing the markdown the user is about to copy.

**Subtitle (lower-third, two sequential):**
> 500 findings, grouped into 41 cases.
> Each case carries a fix path — ready for the agent you already trust.

The second line lands as the handoff card appears. The phrase "agent you already trust" is the load-bearing claim; do not paraphrase it. (It's the local-first replacement for cloud LLM enrichment — see `docs/decisions/REJECTED/002-cloud-llm-for-finding-explanation.md`.)

### Beat 4 — Stance + close (0:38 – 0:45)

**Visual:** Quick three-shot montage of dashboard surfaces — Overview, Tool Catalog (`design/screenshots/03-tool-catalog.png`), Settings (`design/screenshots/04-settings.png`) — each held for ~1 second with a soft cross-fade. Then a slow fade to the wordmark on a cream background.

**Subtitle (one sequence across the montage):**
> Local SQLite. 127.0.0.1. No cloud LLM.

**End frame (held 3 seconds before fade to black):**

```
{ DËVSEC }
github.com/Christian-Katzmann/dev-security
```

The wordmark uses the brand's Eczar serif at large size with the curly braces in mustard (`#C89A4C`). The URL line is in the same neutral grotesk used for body subtitles, smaller, charcoal.

## Demo data thread

Same scan thread as the screenshot system — under no circumstances diverge from this:

- **Target:** DëvSec scanning itself (the repository at `/Users/christiankatzmann/Dev/Projects/dëv-security`).
- **Posture:** 0.0 / 10
- **Open findings count:** 500
- **Featured case:** the stdlib dependency vulnerability case (CVE-2025-68121 and CVE-2026-27143 are both in the Overview's open findings list — pick either as the "drill-into" case in Beat 3).
- **Recovery playbook (if used):** "Upgrade vulnerable dependencies" — 41 cases — ~175 min wall-clock — sourced from `grype`. This is exactly the playbook shown in `design/screenshots/02-recovery-playbooks.png`.

The screenshots in `design/screenshots/` are the authoritative reference for what the dashboard looks like at each surface. If the producer cannot run the live dashboard, the trailer can be composed entirely from these screenshots with HyperFrames' camera-pan and overlay-text capabilities.

## Brand palette

Identical to `design/social/BRIEF.md`:

| Color | Hex | Use in trailer |
|---|---|---|
| Charcoal | `#2A2A2A` | Beat 1 background, end-frame URL, subtitle text on cream |
| Cream | `#EDE4D6` | Beat 2/3/4 backgrounds, subtitle text on charcoal |
| Mustard | `#C89A4C` | Wordmark curly braces (end frame only) |
| Sage | `#7A8D7A` | Dashboard hero banner — carried through from the real product, not painted in |

No gradients. No drop shadows on text. No glows.

## Typography

- **Wordmark `{ DËVSEC }` (end frame):** Eczar serif, same weight and spacing as the brand sheet (`assets/security-observatory-brand-sheet.png`).
- **Subtitles:** A neutral grotesk that pairs with Eczar — Inter or IBM Plex Sans. Sentence case. ~36–48 pt at 1080p output. White on charcoal, charcoal on cream.
- **Terminal text (Beat 2):** A monospace face — JetBrains Mono, Fira Code, or system monospace. Whatever HyperFrames' default produces is fine.

## Pacing

Roughly 10–15 seconds per beat. Cross-fades between beats are 0.3–0.5 seconds. Within a beat, motion is minimal — small pans, gentle scale changes, no bouncy easing. Use ease-out for entrances and ease-in for exits; nothing should snap.

The trailer is calm by construction. If a frame feels busy, it's wrong for this project.

## Hard rejections

The producer session must refuse all of the following, even if a HyperFrames template suggests them:

- **No synthesized voiceover.** No Kokoro-82M narration, no ElevenLabs, no `say` voice burns. Subtitle-only.
- **No background music with melody.** Either silent track or a low-volume room-tone / ambient hum.
- **No marketing language.** No "powered by", "enterprise-grade", "next-gen", "revolutionary", "stop sending your code to the cloud!".
- **No fake screen action.** Every UI element shown must be the real DëvSec dashboard. No mockups, no Figma frames pretending to be screenshots, no "concept dashboard" reconstructions.
- **No "Powered by AI" or "AI-native" badges.** The agent-ready handoff is mentioned in subtitle; that's the entire AI surface in the trailer.
- **No download CTAs.** No "Get DëvSec now", no "Install in 30 seconds!". The end frame gives the GitHub URL; the visitor decides.
- **No animated logo burst.** The wordmark appears with a slow fade, not a bounce, not a stinger, not a particle effect.
- **No version-number burns.** v0.1.0 does not appear anywhere in the trailer.
- **No social-share callouts.** No "share this with your team!", no platform icons.
- **No countdown timers or progress bars on the wordmark.** This is not a launch teaser.

## Production paths (any are acceptable)

The producer session picks based on what's available in their environment. Listed strongest-first:

1. **Live capture against the local dashboard.** Start the dashboard with `security-scan dashboard --port 8765`, point HyperFrames' website-to-hyperframes pipeline at `http://127.0.0.1:8765`. The dashboard already has the demo-data thread loaded (DëvSec scanning itself = 500 findings, posture 0.0). This is the strongest path because it captures the real running product. Requires DëvSec to be installed in the producer session's environment.

2. **HyperFrames HTML+GSAP composition with screenshot stand-ins.** Run `hyperframes init --example product-promo`. Use the four screenshots in `design/screenshots/` as the visual content; add camera moves, text overlays, and the terminal shot in Beat 2 via HTML+GSAP. Rendered locally via `npx hyperframes render`. Free, local, deterministic. This is the fallback when (1) isn't available.

3. **Hybrid — screen-record the dashboard manually, then compose in HyperFrames.** Christian or the producer captures short screen recordings of the dashboard manually (Beats 2, 3, 4 each); HyperFrames composes them with subtitle overlays and transitions. Requires hand-capture work but produces the most authentic motion footage.

All three paths must produce the same output: a single MP4 at `design/trailer/trailer.mp4` matching the specs and narrative above.

## Acceptance criterion

The trailer passes when all of these are true:

1. Total runtime is between 30 and 60 seconds.
2. The four beats land in the order specified; subtitles match the script (paraphrasing only for unavoidable timing).
3. The demo data thread (DëvSec scanning itself, 500 findings, posture 0.0) is recognizable in any frame showing a dashboard surface.
4. The wordmark in the end frame visually matches the wordmark on the brand sheet and (when rendered) the social preview PNG — same Eczar treatment, same curly-brace color.
5. Audio: either silent or a single low-volume ambient bed. No voice.
6. The trailer survives the "calm test": play it muted with no context, and it should still feel like a careful product demo, not a hype reel.
7. File size and format match the spec table at the top.
8. The MP4 lives at `design/trailer/trailer.mp4`.

## After the render

The producer session is **not** asked to edit the README to embed the trailer. That step stays in the main `/repo-craft` session — the README embed needs to be coordinated with the existing hero screenshot and the `## Screens` section so the visual rhythm holds.

The producer's job ends at: a rendered MP4 at the path above, plus a one-line summary of "ready to embed" or "needs another pass (reason)".
