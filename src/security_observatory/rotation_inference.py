"""Best-effort inference of a rotatable secret name from a `secrets`-category case.

The dashboard's case card surfaces a "Rotate this" affordance for secrets-category
cases when rotation is scaffolded for the repo. To pre-fill the rotation modal,
we need to guess which catalog entry the case is about — gitleaks/trufflehog
rarely emit the env-var name directly, but their `title` and `remediation` lines
often carry enough provider context to infer it.

This module is deliberately conservative: it returns a name only when the case
text matches a known catalog entry verbatim or hits a tight provider-name
pattern. When the signal is too weak we return ``None`` and let the surface fall
back to the secret picker.

The function is pure — pass it the case dict and the candidate names list. The
catalog file is read separately via :func:`load_catalog_secret_names` so tests
can inject fixtures without touching ``~/.claude/skills/secrets-rotation``.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger("security_observatory.rotation_inference")


DEFAULT_CATALOG_PATH = Path.home() / ".claude" / "skills" / "secrets-rotation" / "catalog.json"


# Conservative provider-name → catalog-name patterns. Each pattern requires
# both a provider word AND a key/secret-shaped word so generic "API key" text
# doesn't false-match. Order matters only for ties — see :func:`infer_secret_name`.
_PROVIDER_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\banthropic[\W_]*api[\W_]*key\b", re.IGNORECASE), "ANTHROPIC_API_KEY"),
    (re.compile(r"\bopenai[\W_]*api[\W_]*key\b", re.IGNORECASE), "OPENAI_API_KEY"),
    (re.compile(r"\bnext[\W_]*auth[\W_]*secret\b", re.IGNORECASE), "NEXTAUTH_SECRET"),
    (re.compile(r"\bcron[\W_]*secret\b", re.IGNORECASE), "CRON_SECRET"),
    (re.compile(r"\bturso[\W_]*auth[\W_]*token\b", re.IGNORECASE), "TURSO_AUTH_TOKEN"),
    (re.compile(r"\bblob[\W_]*read[\W_]*write[\W_]*token\b", re.IGNORECASE), "BLOB_READ_WRITE_TOKEN"),
    (re.compile(r"\bresend[\W_]*api[\W_]*key\b", re.IGNORECASE), "RESEND_API_KEY"),
    (re.compile(r"\bgithub[\W_]*client[\W_]*secret\b", re.IGNORECASE), "GITHUB_CLIENT_SECRET"),
    (re.compile(r"\bmcp[\W_]*api[\W_]*key\b", re.IGNORECASE), "MCP_API_KEY"),
    (re.compile(r"\bcache[\W_]*revalidate[\W_]*secret\b", re.IGNORECASE), "CACHE_REVALIDATE_SECRET"),
    (re.compile(r"\bauth[\W_]*secret\b", re.IGNORECASE), "AUTH_SECRET"),
)


def load_catalog_secret_names(catalog_path: Path | str | None = None) -> list[str]:
    """Return the list of env-var names declared in the rotation catalog.

    Reads ``~/.claude/skills/secrets-rotation/catalog.json`` by default. Returns
    an empty list when the file is missing or unparseable — callers should treat
    that the same as "no catalog available" and skip inference.
    """
    path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
    if not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError) as exc:
        logger.warning("rotation_inference: failed to read catalog %s: %s", path, exc)
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return []
    names: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def _case_corpus(case: dict[str, Any]) -> str:
    parts: list[str] = []
    title = case.get("title")
    if isinstance(title, str):
        parts.append(title)
    for file in case.get("affected_files") or []:
        if isinstance(file, str):
            parts.append(file)
    for evidence in case.get("evidence") or []:
        if not isinstance(evidence, dict):
            continue
        for field in ("title", "remediation", "location"):
            value = evidence.get(field)
            if isinstance(value, str):
                parts.append(value)
    for step in case.get("fix_steps") or []:
        if isinstance(step, str):
            parts.append(step)
    return " \n ".join(parts)


def infer_secret_name(
    case: dict[str, Any],
    candidate_names: Iterable[str] | None = None,
) -> str | None:
    """Best-effort guess of which catalog secret the case is about.

    Returns the env-var name (e.g., ``"ANTHROPIC_API_KEY"``) when the case text
    contains the name verbatim or matches a tight provider-name pattern.
    Returns ``None`` when the signal is too weak — callers should fall back to
    the secret picker rather than guess.

    Only ``secrets``-category cases are considered. Other categories return
    ``None`` immediately.

    ``candidate_names`` restricts inference to the secrets a particular repo
    can actually rotate (typically the rotation state's secret list). Pass
    ``None`` to allow any name; pass an empty iterable to disable inference.
    """
    if str(case.get("category") or "") != "secrets":
        return None
    candidates: list[str] | None = list(candidate_names) if candidate_names is not None else None
    if candidates is not None and not candidates:
        return None

    corpus = _case_corpus(case)
    if not corpus.strip():
        return None
    corpus_lower = corpus.lower()

    # Exact-name match takes priority — when a remediation step literally names
    # the env var (``ANTHROPIC_API_KEY``), trust it over a provider-hint guess.
    # Sort candidates longest-first so ``GITHUB_CLIENT_SECRET`` wins over a
    # hypothetical ``GITHUB`` substring.
    name_pool: list[str]
    if candidates is not None:
        name_pool = list(candidates)
    else:
        # Without a candidate restriction, pull names from the provider-hint
        # table so we have a known universe to match against.
        name_pool = [name for _, name in _PROVIDER_HINTS]
    name_pool.sort(key=len, reverse=True)
    for name in name_pool:
        if re.search(rf"\b{re.escape(name)}\b", corpus, re.IGNORECASE):
            return name

    # Provider-name patterns. Only return a candidate that's allowed.
    allowed = set(candidates) if candidates is not None else None
    for pattern, name in _PROVIDER_HINTS:
        if allowed is not None and name not in allowed:
            continue
        if pattern.search(corpus_lower):
            return name

    return None


__all__ = (
    "DEFAULT_CATALOG_PATH",
    "infer_secret_name",
    "load_catalog_secret_names",
)
