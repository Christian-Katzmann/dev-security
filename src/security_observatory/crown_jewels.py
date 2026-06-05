"""Human-labeled crown jewels: which nodes are actually worth protecting.

No signal DëvSec collects can tell which data store matters — that is a judgment
only a human can make. So crown jewels are *declared*, never inferred: a committed
repo-local file (``.devsec/crown-jewels.json``) lists the node identities a human
considers crown-jewel-grade, and a scan-time pass flips ``is_crown_jewel = 1`` on
the matching asset nodes.

Honesty / unattended-safety rules:

  - **Never inferred.** Absent file => no crown jewels. That is graceful, not a
    crash, and never guessed-at.
  - **No prompt, ever.** The file is read silently; a missing or malformed file
    yields an empty label set so an unattended scan never blocks.
  - **Matched by identity.** Labels match a node's ``identity_key`` (and, when
    given, its ``node_type`` to disambiguate), the same identities the asset graph
    already uses (component fingerprint, secret file path, IaC resource address).

File shape (both forms accepted)::

    {"crown_jewels": [
        {"identity_key": "aws_db_instance.customer_db", "node_type": "datastore"},
        "config/prod-secrets.env"
    ]}

or simply a top-level list of the same entries. Each entry is either a bare
identity-key string or an object with ``identity_key`` (required) and an optional
``node_type``. Unknown keys (e.g. a human ``note``) are ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .asset_graph import AssetNode, NODE_TYPES

#: Repo-relative location of the human-edited crown-jewel label file.
CROWN_JEWELS_RELATIVE_PATH = ".devsec/crown-jewels.json"


@dataclass(frozen=True, slots=True)
class CrownJewelLabel:
    """One human-declared crown jewel, matched against an asset node's identity.

    ``node_type`` is optional: when ``None`` the label matches any node carrying
    ``identity_key`` (identities rarely collide across types — components are
    fingerprints, secrets are paths, resources are addresses), and when set it
    must also match the node's type.
    """

    identity_key: str
    node_type: str | None = None

    def matches(self, node: AssetNode) -> bool:
        if node.identity_key != self.identity_key:
            return False
        return self.node_type is None or self.node_type == node.node_type


def load_crown_jewel_labels(repo_path: str | Path) -> list[CrownJewelLabel]:
    """Read ``.devsec/crown-jewels.json`` from a repo. Never raises.

    A missing, empty, or unparseable file — or any entry that isn't a usable
    identity — yields an empty (or partial) list, so an unattended scan with no
    crown jewels labeled simply has none rather than failing.
    """
    path = Path(repo_path) / CROWN_JEWELS_RELATIVE_PATH
    try:
        if not path.exists() or path.stat().st_size == 0:
            return []
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    return parse_crown_jewel_labels(data)


def parse_crown_jewel_labels(data: Any) -> list[CrownJewelLabel]:
    """Parse already-loaded JSON into labels. Pure; tolerant of junk entries."""
    if isinstance(data, dict):
        entries = data.get("crown_jewels", [])
    elif isinstance(data, list):
        entries = data
    else:
        return []
    if not isinstance(entries, list):
        return []

    labels: list[CrownJewelLabel] = []
    seen: set[tuple[str, str | None]] = set()
    for entry in entries:
        label = _parse_entry(entry)
        if label is None:
            continue
        dedupe_key = (label.identity_key, label.node_type)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        labels.append(label)
    return labels


def _parse_entry(entry: Any) -> CrownJewelLabel | None:
    if isinstance(entry, str):
        identity_key = entry.strip()
        return CrownJewelLabel(identity_key=identity_key) if identity_key else None
    if isinstance(entry, dict):
        identity_key = str(entry.get("identity_key") or "").strip()
        if not identity_key:
            return None
        node_type = str(entry.get("node_type") or "").strip() or None
        if node_type is not None and node_type not in NODE_TYPES:
            # An unknown type would never match; drop the type rather than the
            # whole label so a typo doesn't silently delete a crown jewel.
            node_type = None
        return CrownJewelLabel(identity_key=identity_key, node_type=node_type)
    return None


def mark_crown_jewels(
    nodes: Iterable[AssetNode],
    labels: Iterable[CrownJewelLabel],
) -> list[AssetNode]:
    """Return the node list with ``is_crown_jewel`` set where a label matches.

    Pure: returns new :class:`AssetNode` instances (they are frozen) and never
    mutates the inputs. A node already marked stays marked; a node matched by any
    label becomes marked. No label matching anything is fine (no crown jewels).
    """
    label_list = list(labels)
    result: list[AssetNode] = []
    for node in nodes:
        is_crown = node.is_crown_jewel or any(label.matches(node) for label in label_list)
        if is_crown == node.is_crown_jewel:
            result.append(node)
        else:
            result.append(
                AssetNode(
                    node_type=node.node_type,
                    identity_key=node.identity_key,
                    label=node.label,
                    confidence=node.confidence,
                    is_crown_jewel=True,
                )
            )
    return result
