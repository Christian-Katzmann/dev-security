from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
import base64
import hashlib
import hmac
import json
import re
import secrets

from .model import SECRET_KEY_RE, redact_text, slugify


HONEY_KEY_PREFIX = "devsec_hny_"
HONEY_KEY_RE = re.compile(r"\bdevsec_hny_[A-Za-z0-9]+_[A-Za-z0-9]+_[A-Za-z0-9]+\b")
DEFAULT_PLACEMENT_PATHS = (
    ".env.backup",
    "legacy-prod-config.json",
    "internal-admin-notes.md",
    "scripts/legacy/deploy-prod.env",
)
SAFE_HEADER_NAMES = {
    "accept",
    "accept-language",
    "content-type",
    "origin",
    "referer",
    "user-agent",
    "x-forwarded-for",
    "x-real-ip",
}


@dataclass(frozen=True, slots=True)
class HoneyKeyMaterial:
    token_id: str
    token: str
    token_hash: str
    token_signature: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_honey_key(signing_secret: str) -> HoneyKeyMaterial:
    token_id = secrets.token_hex(8)
    secret = _urlsafe_secret(24)
    signature = _token_signature(signing_secret, token_id, secret)
    token = f"{HONEY_KEY_PREFIX}{token_id}_{secret}_{signature}"
    return HoneyKeyMaterial(
        token_id=token_id,
        token=token,
        token_hash=hash_honey_key(token),
        token_signature=signature,
    )


def parse_honey_key(value: str) -> tuple[str, str, str] | None:
    token = value.strip()
    if not token.startswith(HONEY_KEY_PREFIX):
        return None
    remainder = token[len(HONEY_KEY_PREFIX) :]
    parts = remainder.split("_")
    if len(parts) != 3:
        return None
    token_id, secret, signature = parts
    if not token_id or not secret or not signature:
        return None
    return token_id, secret, signature


def honey_key_is_well_formed(value: str, signing_secret: str) -> bool:
    parsed = parse_honey_key(value)
    if not parsed:
        return False
    token_id, secret, signature = parsed
    expected = _token_signature(signing_secret, token_id, secret)
    return hmac.compare_digest(signature, expected)


def hash_honey_key(value: str) -> str:
    return hashlib.sha256(f"honeykey:v1:{value}".encode("utf-8")).hexdigest()


def open_url_signature(signing_secret: str, token_id: str) -> str:
    digest = hmac.new(signing_secret.encode("utf-8"), f"open:{token_id}".encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")[:18]


def open_url_is_valid(signing_secret: str, token_id: str, signature: str) -> bool:
    expected = open_url_signature(signing_secret, token_id)
    return hmac.compare_digest(signature, expected)


def extract_honey_key_from_request(
    *,
    path: str,
    query: dict[str, list[str]],
    headers: dict[str, str],
    body: bytes,
) -> str | None:
    candidates: list[str] = []
    for key in ("token", "key", "api_key"):
        candidates.extend(query.get(key, []))
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth:
        candidates.append(auth.removeprefix("Bearer ").strip())
    for header in ("x-devsec-honey-key", "x-api-key", "X-DevSec-Honey-Key", "X-Api-Key"):
        if headers.get(header):
            candidates.append(headers[header])
    if body:
        text = body.decode("utf-8", errors="replace")
        candidates.extend(_tokens_in_text(text))
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if SECRET_KEY_RE.search(str(key)) and isinstance(value, str):
                    candidates.append(value)
    candidates.extend(_tokens_in_text(path))
    for candidate in candidates:
        token = candidate.strip()
        if token.startswith(HONEY_KEY_PREFIX):
            return token
    return None


def build_decoy_snippets(*, base_url: str, name: str, token: str, token_id: str, signing_secret: str) -> dict[str, str]:
    trigger_url = f"{base_url.rstrip('/')}/api/honey/trigger"
    open_url = f"{base_url.rstrip('/')}/api/honey/open/{quote(token_id)}?sig={quote(open_url_signature(signing_secret, token_id))}"
    return {
        ".env.backup": "\n".join(
            [
                "# Legacy internal API settings retained for rollback testing.",
                f"DEVSEC_INTERNAL_API_KEY={token}",
                f"DEVSEC_INTERNAL_API_URL={trigger_url}",
                f"DEVSEC_INTERNAL_ADMIN_DOCS={open_url}",
                "",
            ]
        ),
        "legacy-prod-config.json": json.dumps(
            {
                "service": "legacy-internal-admin",
                "apiBaseUrl": trigger_url,
                "apiKey": token,
                "adminDocs": open_url,
                "note": "Deprecated configuration retained for incident-response drills.",
            },
            indent=2,
        )
        + "\n",
        "internal-admin-notes.md": "\n".join(
            [
                f"# {name}",
                "",
                "Deprecated internal integration notes.",
                "",
                f"- API key: `{token}`",
                f"- API URL: {trigger_url}",
                f"- Admin docs: {open_url}",
                "",
                "These values are fake DëvSec Honey Keys for defensive monitoring.",
                "",
            ]
        ),
    }


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        if lower not in SAFE_HEADER_NAMES:
            continue
        if "authorization" in lower or "cookie" in lower or SECRET_KEY_RE.search(lower):
            clean[key] = "[REDACTED]"
        else:
            clean[key] = _limit(redact_honey_material(redact_text(value)), 240)
    return clean


def summarize_body(body: bytes, content_type: str | None = None) -> str | None:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    redacted = redact_honey_material(redact_text(text))
    if content_type and "json" in content_type.lower():
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return f"Invalid JSON body, {len(body)} bytes"
        if isinstance(parsed, dict):
            keys = sorted(str(key) for key in parsed.keys())[:20]
            sensitive_keys = sorted(str(key) for key in parsed.keys() if SECRET_KEY_RE.search(str(key)))[:20]
            return _limit(
                json.dumps({"type": "json_object", "keys": keys, "sensitive_keys_redacted": sensitive_keys, "bytes": len(body)}, sort_keys=True),
                900,
            )
        if isinstance(parsed, list):
            return f"JSON array body with {len(parsed)} items, {len(body)} bytes"
        return f"JSON {type(parsed).__name__} body, {len(body)} bytes"
    return _limit(redacted, 900)


def redact_honey_material(value: str) -> str:
    return HONEY_KEY_RE.sub("[REDACTED_HONEY_KEY]", value)


def project_id_for_repo_path(repo_path: str) -> str:
    return slugify(repo_path.rstrip("/").split("/")[-1] or repo_path)


def _token_signature(signing_secret: str, token_id: str, token_secret: str) -> str:
    return hmac.new(
        signing_secret.encode("utf-8"),
        f"token:{token_id}:{token_secret}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]


def _urlsafe_secret(length: int) -> str:
    return secrets.token_hex(length)


def _tokens_in_text(text: str) -> list[str]:
    return HONEY_KEY_RE.findall(text)


def _limit(value: str, max_chars: int) -> str:
    return value if len(value) <= max_chars else value[: max_chars - 3] + "..."
