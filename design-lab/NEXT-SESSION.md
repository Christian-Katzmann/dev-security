# Next session — prompt

> Paste this to a fresh session to continue the design-lab work.

---

Use the **/surface-economy** skill to make **industry-grade, Apple-level** design improvements to the **DëvSec design-lab Overview** page. Christian is not happy with it yet — push the craft.

**Orient first (read these):**
- Session memory `devsec-ui-redesign-lab` — full project context.
- `design-lab/README.md` — the lab's rules + structure.
- Root `MISTGLASS-GREY.md` — the design language. **Stay in Mistglass Grey** (cool sage→teal surface, white-on-grey, frosted glass, mono labels). Do not invert to dark cards.

**Run it:** `bash scripts/run-design-lab.sh` → http://127.0.0.1:8788 (or open the "DëvSec Design" Dock app). It lands on the Overview. Sealed zero-build lab (React UMD + Babel + Tailwind CDN, fake data, no backend).

**Files:** `design-lab/screens/m-overview.jsx` (the screen) · `design-lab/foundation/mist-kit.jsx` (`MWidget`, `MBento`, primitives) · `design-lab/foundation/mist-viz.jsx` (`MRing`, `MSeverityBars`, `MLineTrend`, `MHeatmap`) · `design-lab/foundation/mist-shell.jsx` (nav + workspace switcher).

**Shape today:** a full-width posture **hero band**, then a **bento board** of widgets (stat squares, severity, coverage, charts, lists). Keep the hero band. Keep both modes working (all-repos ↔ single repo via the workspace switcher).

**Known gaps to attack (Christian's words, distilled):**
1. **Size-variety rhythm** — it's still mostly hero + a row of squares + many 2-wides. Needs a real large tile / tall tile for music.
2. **Tile presence / depth** — widgets read low-contrast against the grey. Make each feel like a distinct, liftable object.
3. **Content fit** — every widget must fill its size *or* be sized to its content. No dead space, nothing cramped.

**Rules:** verify it renders in the preview with **zero console errors** before claiming done; **stop any server you start** (ports 8788/8789) before ending the turn; never touch the live app (`dashboard-ui/`, `src/`).
