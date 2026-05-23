# REJECTED: Cloud LLM for finding explanation

## What was proposed

Use a hosted LLM (Claude, GPT-4, Gemini) to enrich every finding with a plain-English explanation. Send the finding payload (file path, code snippet, scanner output, severity) to the LLM with a prompt like *"explain this security finding to a developer and suggest a fix"*, return the result, cache it, display it in the dashboard.

This is the pattern many newer security tools have adopted in 2025–2026 — *"AI-powered explanations"*, *"natural-language remediation"*, *"GPT-4-powered triage"*.

## What made it attractive

- **Lower cognitive load on users.** Scanner output is dense and jargon-heavy; an LLM-paraphrased version is faster to skim.
- **One implementation, all scanners.** No per-scanner remediation copy to maintain — the LLM handles every scanner's output shape.
- **Easy demo.** *"Findings explained by AI"* is an immediately legible feature on a marketing page.

## What made it wrong for this project

A cloud LLM re-enables the exact leak DëvSec scans for. The finding payload sent to the LLM contains:

- File path and line number — the user's repo structure
- Code snippet — the user's source code, sometimes including secret-looking values
- Scanner output — which often quotes more source code than the snippet does
- Repo name — present in most enrichment formats

The user opened DëvSec because they did not want a third party to hold their source code. Then, while reviewing findings, a helper feature silently uploads exactly the snippets the scanner flagged as sensitive to a third-party LLM provider. The contradiction isn't subtle — it's the whole point of the project, inverted.

The local-first stance forces a different shape: the *"explain this finding"* affordance is a markdown handoff prompt generated locally. The user copies it into whatever agent they already trust, on whatever boundary they've already decided. The user's existing trust relationship with their agent is the one we route through, not a new one we manufacture.

## When this might become right

Never, for DëvSec specifically. The local-first stance is not negotiable on this axis — it's the load-bearing positioning. If a future DëvSec contributor wants LLM enrichment, the correct shape is local inference (Ollama, llama.cpp, MLX), not a hosted API.

For tools whose positioning is not local-first, cloud LLM enrichment is a legitimate product choice. We are not arguing against it universally; we are arguing it's wrong *here*.

## Decided

2026-05-23 (alongside the public-repo-ready campaign).
