# Pinned-set criteria

The pinned set on `github.com/Christian-Katzmann` is curated as a designed exhibition, not a portfolio dump. v3 §16 of the repo-craft guide is the standard; this file is the operational checklist a candidate repo must clear before it earns a pin alongside `dev-security`.

## The thesis the set must communicate

> Local-first, source-grounded, calm-by-default tools for serious domains — built so AI agents can work in them safely.

Every pinned repo expresses one face of this. Read in order, the set should feel like a short essay with a clear voice — first pin is the strongest argument, last pin is the most speculative.

## Current state (2026-05-24)

| Slot | Repo | Role |
|---|---|---|
| 1 | `dev-security` | Technical depth piece — local-first security observability |
| 2 | `idea-bench` | Flagship product — self-hosted, trust-bounded AI evaluation |
| 3 | `gitslip` | Workflow infrastructure piece — source-grounded deployment for AI-coded projects |
| 4–6 | empty | Honest empty — better than a half-fit pin |

Slots 4–6 stay empty until a candidate clears the bar below. Empty slots are honest; weak-surface pins drag the strong ones down.

## What a candidate repo must clear before it earns a pin

A candidate must pass **all five**. One miss is a hold.

1. **Public on GitHub.** Private repos don't appear in the Pinned section, full stop. If the repo is still private, the answer is no — start with the public-flip path (`/repo-craft` end-to-end), not the pin.
2. **Opening sentence fits the thesis as a particular case of it.** Not by repeating "local-first" verbatim — by *being* local-first / source-grounded / calm-by-default applied to its own domain. If the first sentence of the README has nothing to do with the through-line, either rewrite the sentence, rewrite the thesis, or skip the pin. `idea-bench`'s "self-hosted tool for running blind head-to-head evaluations of LLM output" qualifies — self-hosted is the team-shaped corollary of local-first, and "blind evaluation that survives a decision meeting" is calm-by-default applied to AI governance.
3. **First-fold matches the studio shape.** Positioning sentence → status line → hero (video or screenshot with caption) → "What this is not" or equivalent boundary section. Doesn't have to be identical to dev-security's structure — has to be recognizably from the same maker. The test: a visitor who has read dev-security, `idea-bench`, and `gitslip` should be able to predict what the next pinned repo looks like before clicking it.
4. **Visual layer earns its slot.** At minimum: a designed social preview (uploaded via Settings → Social preview), a hero shot or trailer with an italicized one-sentence caption that says what is *proven*, and screenshots/diagrams in a consistent style across the README. A pinned repo with no visual layer drags the perceived quality of the set down.
5. **Status statement is honest about partiality.** The set is held together partly by candor — "0.1.x, the dashboard is honest about what's still partial" (dev-security) and "usable public alpha, single-operator self-hosted loop is real, team workspaces deliberately out of scope" (`idea-bench`) belong to the same voice. A candidate that overstates readiness breaks the voice even if its README looks polished.

## Known candidates and current verdict

- **`monëy.com`** — Private (personal banking, will likely stay private). Even if flipped public, the public surface is currently a directory of subdirectory READMEs with no root README, so it fails (3) and (4) cleanly. Not a near-term pin candidate; if it ever earns one, that's its own multi-week effort.
- **`reuse-kit`** — Not on GitHub at all (no remote). Fails (1) by default. The kit is a personal force-multiplier, not a portfolio piece — pinning it would require deciding whether to publish it at all, which is a separate question.
- **`plsmode`** — Public but small ("Buttons for commands. You're welcome."). Fails (2) — it's a utility, not a serious-domain tool — and fails (4) on visual layer. Not a pin candidate.
- **Future candidates** — A domain-expertise piece in the public-sector or finance space (per v3 §16's "domain expertise" face of the thesis) is the natural shape for slot 4 if one of Christian's local projects earns its own `/repo-craft` pass.

## When to re-evaluate

Re-evaluate the set whenever:

- A new repo finishes its `/repo-craft` pass and goes public.
- An existing pinned repo's status statement changes substantially (e.g. dev-security exits 0.1.x into a 0.5.x state where "honest about partiality" no longer reads true).
- The thesis itself shifts. If that happens, every pinned repo's opening sentence gets re-checked against the new through-line — pins that no longer fit get unpinned, not retrofitted.

Don't pin to fill slots. The empty slots are part of the composition.
