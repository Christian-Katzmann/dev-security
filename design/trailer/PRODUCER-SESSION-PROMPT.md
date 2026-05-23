# Prompt for the HyperFrames producer session

Copy everything between the dividers below into a fresh Claude Code (or Codex) session opened in this repository. The receiving session will read the brief, invoke `/hyperframes`, and render the trailer.

The receiving session should run with **Opus 4.7 + Extra High thinking** (Claude Code) or **GPT-5.5 + Extra High reasoning effort** (Codex). Motion artifact production benefits from careful, slow thinking — speed-mode will skip the brief's hard rejections.

---

## Prompt to paste

```text
Produce a 30–60 second polished trailer for the dëv-security repository using the /hyperframes skill.

Project root: /Users/christiankatzmann/Dev/Projects/dëv-security
Brief (read this FIRST, in full): /Users/christiankatzmann/Dev/Projects/dëv-security/design/trailer/BRIEF.md
Output target: /Users/christiankatzmann/Dev/Projects/dëv-security/design/trailer/trailer.mp4

The brief contains:
- Narrative arc across four beats with timing
- Canonical subtitle script (do not paraphrase unless timing makes it impossible)
- Demo data thread that must match every other visual artifact in the repo
- Brand palette and typography
- Hard rejections (no voiceover, no marketing language, no fake screen action, etc.)
- Three acceptable production paths (live capture / HTML+GSAP composition / hybrid screen-record) — pick whichever fits your environment

The repo already has a finished visual layer that the trailer must cohere with:
- design/social/BRIEF.md — social preview brief (same palette, same wordmark you'll use in the end frame)
- design/screenshots/01-overview.png through 04-settings.png — four captioned dashboard screenshots (light theme, 16:10, same demo data thread)
- design/screenshots/CAPTIONS.md — explains the screenshot system rules; the trailer follows the same conventions
- README.md — opens with the positioning sentence; the trailer's opening subtitle pairs with it
- PROVOCATION.md — the sharp claim behind the local-first stance; the trailer is the moving-picture version of the same argument
- docs/decisions/REJECTED/002-cloud-llm-for-finding-explanation.md — explains the "agent you already trust" line in Beat 3; do not paraphrase that phrase

Operating constraints:
- Read the brief before invoking /hyperframes. The brief is the contract.
- Use only free / local rendering — no HeyGen Cloud Studio, no Remotion Cloud Render, no ElevenLabs TTS, no paid HyperFrames features. The bundled Kokoro-82M is local, but the brief requires NO voiceover anyway.
- Subtitle-only (no narration). Burned-in subtitles, not sidecar SRT.
- Do not edit anything outside design/trailer/. Do not modify README.md, AGENTS.md, PROVOCATION.md, the social BRIEF, the screenshot files, or any code. Your scope ends at producing the MP4.
- If the live-capture path requires DëvSec to be running locally, you may start the dashboard with `security-scan dashboard --port 8765` — but kill that process before the session ends.
- If you find a real blocker (HyperFrames not installed, no screen-capture capability in this environment, hardware limitation), surface it; don't degrade the brief to make it work.

Working with Christian: he is an innovator and systems thinker, not a coder. He cannot evaluate production-level decisions about codecs, frame rates, or compositing trees. Make those calls yourself and explain in plain language. Do not present a menu of options; produce the trailer and explain the choices you made.

When done, report back with exactly these four things, in this order:
1. Path to the rendered MP4 (should be design/trailer/trailer.mp4)
2. Total runtime in seconds
3. Production path used (live capture / HTML+GSAP / hybrid) and a one-sentence justification
4. Verdict: "ready to embed in README" OR "needs another pass: <one-line reason>"

If any beat or subtitle had to deviate from the brief, list every deviation with a one-line reason. Honest reporting beats polished-looking output.
```

---

## What happens after the producer session returns

When the producer session reports "ready to embed in README", the main `/repo-craft` session (or any follow-on session) handles the README embed, with this default position:

- Replace the hero image at the top of README.md with the trailer's MP4
- Use the existing `design/screenshots/01-overview.png` as the poster frame (so the trailer's first impression matches the existing screenshot system)
- Keep the existing italicized caption below the embed (the caption applies to both the trailer and its poster frame)

If the producer reports "needs another pass", read their reason, decide whether to re-invoke `/hyperframes` against the same brief or revise the brief itself, and run again. Don't ship a v3-rejected trailer.

## On rendering cost

The brief specifies free/local rendering only. If HyperFrames offers a paid path mid-session (cloud render, premium TTS, etc.), the producer session must refuse it unless explicitly authorized by Christian in a follow-up message. The trailer is durable infrastructure — paying $5 to render it once may be fine, but the default is local-first because that's the project's stance and the producer should embody it.
