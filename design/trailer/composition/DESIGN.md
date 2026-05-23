# Visual identity — DëvSec trailer composition

Derived from `design/trailer/BRIEF.md` and `design/social/BRIEF.md`. Locked.

## Style prompt

Calm, honest, sentence case. The same voice the README and `PROVOCATION.md` use.
The trailer should feel like watching a careful engineer use the product, with
quiet annotation — not a SaaS landing-page hero video. Minimal motion. No
gradients on backgrounds. No glows or drop shadows on text.

## Colors

| Role | Hex | Use |
|---|---|---|
| Charcoal | `#2A2A2A` | Beat 1 background, end-frame URL, subtitle text on cream |
| Cream | `#EDE4D6` | Beats 2 / 3 / 4 backgrounds, subtitle text on charcoal |
| Mustard | `#C89A4C` | Wordmark curly braces (end frame only). Nothing else. |
| Sage | `#7A8D7A` | Carried in from the real dashboard screenshots only — never painted in |
| Sage deep | `#5F7160` | Terminal prompt accent (Beat 2 only — derived from sage banner) |

## Typography

- **Wordmark `{ DËVSEC }`** — Eczar serif (Google Fonts). Curly braces in mustard, letters in charcoal.
- **Subtitles** — Inter, weight 500, sentence case. ~52px at 1080p. White on charcoal, charcoal on cream.
- **Terminal text** — JetBrains Mono. Charcoal text on cream terminal background.

## Motion

- Cross-fades between beats: 0.4s.
- Within a beat: ease-out for entrances (`power2.out`, `power3.out`, `expo.out`), ease-in is only used on the final fade to black.
- Subtitle entrances: 0.5s fade + 12px upward translate.
- Pan/zoom on screenshots: 6–10s, linear or `power1.inOut`, scale change ≤ 1.15×.
- No bounce, no overshoot, no particles, no animated logo stinger.

## What NOT to do

- No synthesized voiceover, no music with melody.
- No marketing language ("powered by", "next-gen", "stop sending your code to the cloud!").
- No fake screen action — every dashboard frame is a real screenshot or a real screenshot pan.
- No "AI-native" badges, no version-number burns, no download CTA, no social-share icons.
- No animated logo burst. The wordmark fades in slowly; nothing bounces.
- No full-screen linear gradients on dark backgrounds — H.264 banding.
