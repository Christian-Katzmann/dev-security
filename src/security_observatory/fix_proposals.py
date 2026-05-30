"""Propose → clean-room-review → land flow for hands-off code fixes.

This is the Phase 2 machinery of the `devsec-rw-mcp` campaign (spec:
docs/rw-extend-spec.md §3). It lets the proposing agent — the one that read the
(attacker-influenceable) finding text — draft a fix as a branch/PR, and a
*separate* clean-room reviewer agent approve or reject the diff. Low-risk fix
classes auto-merge on clean-room approval; everything else stops for a human.

Three structural guarantees make auto-merge safe, and all three are enforced by
data flow rather than by instructing the model nicely:

1. **The clean-room reviewer never sees the finding text.** ``build_review_packet``
   accepts only the diff and a diff-derived classification — there is no
   parameter through which case/finding text could flow. The MCP packet tool
   builds the reviewer's entire input from the stored *diff bytes*, never copying
   the proposal's ``case_id``/``title``. So whatever reaches the reviewer is
   clean by construction.

2. **Every security decision derives from the diff bytes, never a caller label.**
   ``classify_fix_class`` re-runs at packet-build time and again at land time on
   the stored diff. A poisoned finding that mislabels a source-code change as a
   "dependency bump" cannot reach the auto-merge lane — the class is recomputed
   from the diff and the caller's hint is ignored. (Mirrors the severity gate's
   "read severity from the recorded case, never caller text" rule.)

3. **No auto-merge without a recorded clean-room approval of *this* diff.**
   ``decide_landing`` reads the persisted review from the audit trail and
   requires ``clean_room_status == "approved"`` *and* that the approval's diff
   hash matches the diff on file. A diff swapped after approval, or a missing /
   rejected review, can never produce an ``auto_merge`` outcome.

The guarded surface owns the *decision and the audit trail*. The physical git
work (open the branch, push the PR, run the merge) stays with the orchestrating
command — consistent with the MCP boundary that this adapter never writes
repository files. What this module guarantees is that no auto-merge is *ever
authorized* without a clean-room approval recorded against the exact diff.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any
import re

from .model import redact_text, slugify, utc_now_slug


FIX_PROPOSAL_SCHEMA_VERSION = "devsec.fix_proposal.v1"
REVIEW_PACKET_SCHEMA_VERSION = "devsec.clean_room_packet.v1"

# The narrow auto-merge allowlist (spec §3). Widening later is cheap; a wrong
# auto-merge is not. Every other class — and any high/critical suppression, which
# goes through the §2 severity gate, not this loop — stops for a human.
AUTO_MERGE_FIX_CLASSES = ("action_sha_pin", "dependency_bump", "lockfile_patch")

# A fix proposal must open a *new* branch; it may never target a protected
# branch directly. The land gate re-checks this even if propose let it through.
PROTECTED_BRANCHES = {
    "main",
    "master",
    "trunk",
    "develop",
    "development",
    "release",
    "production",
    "prod",
    "stable",
}

MAX_DIFF_BYTES = 200_000

_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/\-]{1,200}$")


class ProtectedBranchError(ValueError):
    """Raised when a proposal would commit to a protected (or the base) branch."""


# ---------------------------------------------------------------------------
# Diff classification — the load-bearing security primitive. Deterministic,
# diff-only, and conservative: it returns ``auto_merge_eligible=True`` *only*
# when it can positively prove the diff matches one of the three narrow classes.
# Every uncertain case falls through to a human class. A missed auto-merge just
# means a human looks; a wrong one is the catastrophic failure we refuse to risk.
# ---------------------------------------------------------------------------

_WORKFLOW_RE = re.compile(r"(?:^|/)\.github/workflows/[^/]+\.ya?ml$", re.IGNORECASE)
_REQUIREMENTS_RE = re.compile(r"(?:^|/)requirements[\w.\-]*\.(?:txt|in)$", re.IGNORECASE)
_IAC_RE = re.compile(
    r"\.(?:tf|tfvars|bicep)$|(?:^|/)(?:dockerfile|docker-compose\.ya?ml)$",
    re.IGNORECASE,
)
_LOCKFILE_NAMES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
    "poetry.lock",
    "pipfile.lock",
    "cargo.lock",
    "go.sum",
    "gemfile.lock",
    "composer.lock",
}
_MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "go.mod",
    "cargo.toml",
    "gemfile",
    "pipfile",
    "composer.json",
}
# Names that look like dependency lines but are project-own metadata, not a
# dependency version bump. Seeing one means "not a clean single-package bump".
_RESERVED_MANIFEST_KEYS = {
    "version",
    "name",
    "description",
    "license",
    "author",
    "main",
    "module",
    "type",
    "homepage",
    "repository",
    "bugs",
    "keywords",
    "engines",
}

_USES_RE = re.compile(r"uses:\s*([A-Za-z0-9._\-/]+)@([^\s#]+)")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_INSTALL_HOOK_RE = re.compile(
    r'"(?:postinstall|preinstall|preuninstall|postuninstall|prepare|'
    r'prepublish|prepublishOnly|install|scripts)"\s*:',
    re.IGNORECASE,
)
_URLISH_RE = re.compile(
    r"(?:https?://|git\+|git://|ssh://|file:|link:|workspace:|npm:|registry)",
    re.IGNORECASE,
)
_JSON_DEP_RE = re.compile(r'"([^"]+)"\s*:\s*"([^"]+)"')
_REQ_DEP_RE = re.compile(r"^([A-Za-z0-9._\-]+)\s*(?:==|>=|~=|<=|!=|>|<|=)\s*v?([0-9][\w.\-+*]*)")
_TOML_DEP_RE = re.compile(r'^([A-Za-z0-9._\-]+)\s*=\s*"[~^>=<!\s]*v?([0-9][\w.\-+*]*)"')
_PEP508_DEP_RE = re.compile(r'^"([A-Za-z0-9._\-]+)\s*(?:[=<>~!]+)\s*v?([0-9][\w.\-+*]*)')
_GOMOD_DEP_RE = re.compile(r"([A-Za-z0-9._/\-]+)\s+v([0-9][\w.\-+]*)")
_VERSION_CORE_RE = re.compile(r"(\d+(?:\.\d+){0,3})")
_IGNORABLE_MANIFEST_LINES = {"{", "}", "},", "],", "[", "]", "(", ")", ",", "dependencies = ["}


@dataclass(slots=True)
class FixClassification:
    fix_class: str
    auto_merge_eligible: bool
    reasons: list[str] = field(default_factory=list)
    disqualifiers: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    file_kinds: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fix_class": self.fix_class,
            "auto_merge_eligible": self.auto_merge_eligible,
            "reasons": list(self.reasons),
            "disqualifiers": list(self.disqualifiers),
            "changed_files": list(self.changed_files),
            "file_kinds": dict(self.file_kinds),
        }


def classify_fix_class(diff: str) -> FixClassification:
    """Classify a unified diff into a fix class, deciding auto-merge eligibility.

    Reads only the diff. Never consults a caller-supplied label, the finding
    text, or any stored classification.
    """
    files = _parse_diff(diff)
    changed = sorted(files)
    if not changed:
        return FixClassification(
            "unknown", False, [], ["No file changes were parsed from the diff."], changed, {}
        )
    kinds = {path: _file_kind(path) for path in changed}
    kindset = set(kinds.values())

    if "source" in kindset:
        return FixClassification(
            "source_change",
            False,
            [],
            ["Diff changes application/source files outside manifests, lockfiles, and workflows."],
            changed,
            kinds,
        )
    if "iac" in kindset:
        return FixClassification(
            "iac_change",
            False,
            [],
            ["Diff changes infrastructure-as-code or container build files; always needs a human."],
            changed,
            kinds,
        )

    # From here, every changed file is a workflow, manifest, or lockfile.
    if kindset == {"workflow"}:
        return _classify_workflow(files, changed, kinds)
    if "workflow" in kindset:
        return FixClassification(
            "mixed_change",
            False,
            [],
            ["Diff mixes workflow files with manifests/lockfiles; outside the single-class allowlist."],
            changed,
            kinds,
        )
    if kindset == {"lockfile"}:
        return FixClassification(
            "lockfile_patch",
            True,
            ["Diff updates only lockfiles; no manifest or source-code change. Lockfiles do not execute code."],
            [],
            changed,
            kinds,
        )
    return _classify_dependency(files, changed, kinds)


def _classify_workflow(
    files: dict[str, dict[str, list[str]]],
    changed: list[str],
    kinds: dict[str, str],
) -> FixClassification:
    removed_uses: dict[str, list[str]] = {}
    added_uses: dict[str, list[str]] = {}
    touched_non_uses = False
    for path in changed:
        for line in files[path]["removed"]:
            if not line.strip():
                continue
            match = _USES_RE.search(line)
            if match:
                removed_uses.setdefault(match.group(1), []).append(match.group(2))
            else:
                touched_non_uses = True
        for line in files[path]["added"]:
            if not line.strip():
                continue
            match = _USES_RE.search(line)
            if match:
                added_uses.setdefault(match.group(1), []).append(match.group(2))
            else:
                touched_non_uses = True

    if touched_non_uses or not added_uses:
        return FixClassification(
            "workflow_change",
            False,
            [],
            ["Workflow change touches more than `uses:` action refs."],
            changed,
            kinds,
        )
    if set(added_uses) != set(removed_uses):
        return FixClassification(
            "workflow_change",
            False,
            [],
            ["Workflow `uses:` change adds or removes an action rather than pinning the same one."],
            changed,
            kinds,
        )
    for action, refs in added_uses.items():
        for ref in refs:
            if not _SHA40_RE.match(ref.lower()):
                return FixClassification(
                    "workflow_change",
                    False,
                    [],
                    [f"New ref for {action} is not a 40-hex commit SHA."],
                    changed,
                    kinds,
                )
    return FixClassification(
        "action_sha_pin",
        True,
        [
            f"Diff pins {len(added_uses)} GitHub Actions `uses:` ref(s) to 40-hex commit "
            "SHAs of the same already-referenced action(s); no other workflow logic changes."
        ],
        [],
        changed,
        kinds,
    )


def _classify_dependency(
    files: dict[str, dict[str, list[str]]],
    changed: list[str],
    kinds: dict[str, str],
) -> FixClassification:
    removed: dict[str, str] = {}
    added: dict[str, str] = {}
    disqualifiers: list[str] = []
    unparsed = False
    for path in changed:
        if kinds[path] != "manifest":
            # Lockfile lines may accompany an allowed manifest bump; they are not
            # analyzed for version pairs (a lockfile cannot introduce source code).
            continue
        for lines, bucket in ((files[path]["removed"], removed), (files[path]["added"], added)):
            for line in lines:
                stripped = line.strip()
                if not stripped or _is_ignorable_manifest_line(stripped):
                    continue
                if _INSTALL_HOOK_RE.search(line):
                    disqualifiers.append("Diff touches install scripts/hooks.")
                if _URLISH_RE.search(line):
                    disqualifiers.append("Diff changes a registry/source URL or a non-version dependency source.")
                pair = _extract_dependency(stripped)
                if pair:
                    bucket[pair[0]] = pair[1]
                else:
                    unparsed = True

    if disqualifiers:
        return FixClassification("dependency_change", False, [], _dedupe(disqualifiers), changed, kinds)
    if unparsed:
        return FixClassification(
            "dependency_change",
            False,
            [],
            ["Diff changes manifest lines that aren't a recognizable single-package version bump."],
            changed,
            kinds,
        )

    changed_names = set(removed) | set(added)
    if set(removed) != set(added) or len(changed_names) != 1:
        return FixClassification(
            "dependency_change",
            False,
            [],
            ["Diff is not a single existing package's version bump (it adds/removes a package or changes several)."],
            changed,
            kinds,
        )
    name = next(iter(changed_names))
    old_version, new_version = removed[name], added[name]
    if old_version == new_version:
        return FixClassification(
            "dependency_change", False, [], ["Manifest version did not change."], changed, kinds
        )
    if _is_major_bump(old_version, new_version):
        return FixClassification(
            "major_bump",
            False,
            [],
            [f"{name} {old_version} → {new_version} is a major version bump; always needs a human."],
            changed,
            kinds,
        )
    return FixClassification(
        "dependency_bump",
        True,
        [
            f"Diff raises a single existing dependency ({name}) {old_version} → {new_version} "
            "(patch/minor), with no package added, removed, or re-sourced."
        ],
        [],
        changed,
        kinds,
    )


# ---------------------------------------------------------------------------
# Clean-room review packet — the structural fence.
# ---------------------------------------------------------------------------

CLEAN_ROOM_REVIEWER_INSTRUCTIONS = (
    "You are reviewing a code diff in isolation. You have NOT been given, and will "
    "not be given, the security finding that motivated this change — that is by "
    "design. Judge ONLY whether the diff satisfies every listed invariant for its "
    "stated fix class. Approve only if all invariants hold on the diff in front of "
    "you; otherwise reject. Do not infer intent from commit messages, branch names, "
    "or anything outside the diff and the invariants."
)

_INVARIANTS_BY_CLASS: dict[str, list[str]] = {
    "action_sha_pin": [
        "The diff touches only files under .github/workflows/ ending in .yml or .yaml.",
        "Only `uses:` action references change; no job, step, permission, or trigger logic changes.",
        "Each changed action keeps the same owner/repo; only its ref changes.",
        "Every new ref is a full 40-character hex commit SHA (not a tag or branch).",
    ],
    "dependency_bump": [
        "The diff touches only dependency manifests (and optionally their lockfiles).",
        "Exactly one existing dependency's version changes; none is added or removed.",
        "The bump is patch or minor — not a major (semver) version change.",
        "No registry/source URL, VCS source, or install script/hook is changed.",
    ],
    "lockfile_patch": [
        "The diff touches only lockfiles — no manifest and no source code.",
        "The change is a regenerated/patched lockfile, not a hand-edited source file.",
    ],
}


def invariants_for(fix_class: str) -> list[str]:
    """The fixed invariant checklist a clean-room reviewer verifies for a class.

    Every invariant is a statement about the *diff*. None references a finding.
    """
    return list(
        _INVARIANTS_BY_CLASS.get(
            fix_class,
            [
                "This fix class is not auto-merge-eligible; a human must review the "
                "change against its security intent before it lands.",
            ],
        )
    )


def build_review_packet(
    *,
    proposal_id: str,
    diff: str,
    classification: FixClassification,
    base_branch: str,
    head_branch: str,
) -> dict[str, Any]:
    """Assemble the clean-room reviewer's *entire* input.

    The signature is the fence: it takes the diff and a diff-derived
    classification only. There is no parameter through which case/finding text
    could pass, so the returned packet is clean by construction.
    """
    return {
        "schema_version": REVIEW_PACKET_SCHEMA_VERSION,
        "proposal_id": proposal_id,
        "fix_class": classification.fix_class,
        "auto_merge_eligible": classification.auto_merge_eligible,
        "base_branch": base_branch,
        "head_branch": head_branch,
        "diff": diff,
        "diff_sha256": diff_sha256(diff),
        "changed_files": list(classification.changed_files),
        "invariants": invariants_for(classification.fix_class),
        "instructions": CLEAN_ROOM_REVIEWER_INSTRUCTIONS,
    }


# ---------------------------------------------------------------------------
# Propose → review → land, recorded through the audited fix-proposal store.
# ---------------------------------------------------------------------------


def propose_fix(
    db: Any,
    *,
    repo: str,
    diff: str,
    head_branch: str,
    title: str,
    case_id: str | None = None,
    base_branch: str = "main",
    source: str = "mcp_write",
) -> dict[str, Any]:
    """Record a code-fix proposal bound to a new, non-protected branch.

    Refuses to target a protected (or the base) branch — a proposal opens a
    branch/PR, it never commits to a protected branch directly. The diff is
    redacted, classified from its own bytes, hashed, and stored as an audited
    proposal. The physical branch/PR is opened by the orchestrating command;
    this records the audited contract and the diff-derived fix class.
    """
    repo_name, repo_path = _resolve_proposal_repo(db, repo)
    clean_diff = redact_text(str(diff or ""))
    if not clean_diff.strip():
        raise ValueError("diff is required.")
    if len(clean_diff) > MAX_DIFF_BYTES:
        raise ValueError(f"diff is too large to propose ({len(clean_diff)} > {MAX_DIFF_BYTES} chars).")
    clean_title = str(title or "").strip()
    if not clean_title:
        raise ValueError("title is required.")

    base = _require_branch(base_branch, role="base")
    head = _require_branch(head_branch, role="head")
    if head in PROTECTED_BRANCHES:
        raise ProtectedBranchError(
            f"A fix proposal must open a new branch; {head!r} is a protected branch."
        )
    if head == base:
        raise ProtectedBranchError("The head branch must differ from the base branch.")

    classification = classify_fix_class(clean_diff)
    digest = diff_sha256(clean_diff)
    record = {
        "id": f"fix_{slugify(repo_name)}_{utc_now_slug()}_{digest[:12]}",
        "schema_version": FIX_PROPOSAL_SCHEMA_VERSION,
        "repo_name": repo_name,
        "repo_path": repo_path,
        "case_id": (str(case_id).strip() or None) if case_id else None,
        "base_branch": base,
        "head_branch": head,
        "title": clean_title,
        "diff": clean_diff,
        "diff_sha256": digest,
        "fix_class": classification.fix_class,
        "auto_merge_eligible": classification.auto_merge_eligible,
        "classification": classification.to_dict(),
        "source": str(source or "mcp_write").strip() or "mcp_write",
        "status": "proposed",
        "clean_room_status": "pending",
    }
    return db.save_fix_proposal(record)


def clean_room_review_packet(db: Any, *, proposal_id: str) -> dict[str, Any]:
    """Return ONLY the clean-room review packet for a proposal.

    The packet is rebuilt from the stored *diff bytes* — the classification is
    re-derived, and the proposal's case_id/title/finding text are never read
    into it. This is the surface the (separate) reviewer agent is handed.
    """
    record = _require_proposal(db, proposal_id)
    diff = str(record.get("diff") or "")
    classification = classify_fix_class(diff)
    return build_review_packet(
        proposal_id=str(record.get("id")),
        diff=diff,
        classification=classification,
        base_branch=str(record.get("base_branch") or "main"),
        head_branch=str(record.get("head_branch") or ""),
    )


def record_clean_room_review(
    db: Any,
    *,
    proposal_id: str,
    approved: bool,
    checked_invariants: list[str] | None = None,
    diff_sha256: str,
    reviewer: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Record the clean-room verdict in the audit trail.

    The reviewer must echo the ``diff_sha256`` from the packet it reviewed; the
    verdict is refused if it does not match the diff on file, so a review can
    never be silently attributed to a different diff.
    """
    record = _require_proposal(db, proposal_id)
    stored_hash = str(record.get("diff_sha256") or "").lower()
    if str(diff_sha256 or "").strip().lower() != stored_hash:
        raise ValueError(
            "Reviewed diff hash does not match the proposal's diff; refusing to record "
            "a clean-room verdict against a different diff."
        )
    invariants = [str(item).strip() for item in (checked_invariants or []) if str(item).strip()]
    return db.record_fix_proposal_review(
        proposal_id=proposal_id,
        approved=bool(approved),
        checked_invariants=invariants,
        reviewer=reviewer,
        notes=notes,
        clean_room_diff_sha256=stored_hash,
    )


def decide_landing(db: Any, *, proposal_id: str) -> dict[str, Any]:
    """The land gate. Authorizes auto-merge only when every condition holds.

    ``auto_merge`` is returned iff: a clean-room *approval* is recorded, that
    approval is for the exact diff on file, the diff re-derives to an
    auto-merge-eligible class, and the head branch is a real (non-protected,
    non-base) branch. Anything else → ``requires_human`` (or ``blocked``).
    """
    record = _require_proposal(db, proposal_id)
    diff = str(record.get("diff") or "")
    live = classify_fix_class(diff)
    clean_room_status = str(record.get("clean_room_status") or "pending")
    head = str(record.get("head_branch") or "")
    base = str(record.get("base_branch") or "")
    approved_hash = str(record.get("clean_room_diff_sha256") or "").lower()
    stored_hash = str(record.get("diff_sha256") or "").lower()

    reasons: list[str] = []
    outcome = "requires_human"
    if head in PROTECTED_BRANCHES or head == base:
        outcome = "blocked"
        reasons.append("Proposal targets a protected or the base branch; it cannot land as a PR.")
    elif clean_room_status != "approved":
        reasons.append(
            "No clean-room approval is recorded in the audit trail."
            if clean_room_status == "pending"
            else "The clean-room reviewer rejected the diff."
        )
    elif approved_hash != stored_hash:
        reasons.append("The clean-room approval was recorded against a different diff than the one on file.")
    elif live.fix_class not in AUTO_MERGE_FIX_CLASSES:
        reasons.append(
            f"Fix class '{live.fix_class}' is not in the auto-merge allowlist; a human must land it."
        )
        reasons.extend(live.disqualifiers)
    else:
        outcome = "auto_merge"
        reasons.append(
            f"Clean-room approved and the diff re-derives to '{live.fix_class}', an auto-merge-eligible class."
        )
        reasons.extend(live.reasons)

    saved = db.record_fix_proposal_landing(proposal_id=proposal_id, outcome=outcome, reasons=_dedupe(reasons))
    return {
        "proposal_id": str(record.get("id")),
        "outcome": outcome,
        "auto_merge": outcome == "auto_merge",
        "fix_class": live.fix_class,
        "auto_merge_eligible": live.auto_merge_eligible,
        "clean_room_status": clean_room_status,
        "head_branch": head,
        "base_branch": base,
        "case_id": record.get("case_id"),
        "reasons": _dedupe(reasons),
        "status": saved.get("status") if isinstance(saved, dict) else None,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def diff_sha256(diff: str) -> str:
    return sha256(str(diff).encode("utf-8", errors="replace")).hexdigest()


def _resolve_proposal_repo(db: Any, repo: str) -> tuple[str, str | None]:
    """Resolve a repo NAME to (name, recorded path), requiring scan history.

    A fix proposal is always anchored to an already-scanned repo — the finding
    it addresses came from a scan — so an unknown repo name is refused. The tool
    never accepts a raw filesystem path.
    """
    clean = str(repo or "").strip()
    if not clean:
        raise ValueError("repo is required.")
    scan = db.latest_scan_for_repo(clean)
    if not scan:
        raise ValueError("No scan history for that repository.")
    return clean, (str(scan.get("repo_path")) if scan.get("repo_path") else None)


def _require_proposal(db: Any, proposal_id: str) -> dict[str, Any]:
    record = db.get_fix_proposal(str(proposal_id or "").strip())
    if not record:
        raise ValueError("Fix proposal not found.")
    return record


def _require_branch(value: str, *, role: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{role} branch is required.")
    if not _BRANCH_RE.match(clean) or ".." in clean or clean.startswith(("-", "/")) or clean.endswith("/"):
        raise ValueError(f"{role} branch {value!r} is not a valid git branch name.")
    return clean


def _parse_diff(diff: str) -> dict[str, dict[str, list[str]]]:
    files: dict[str, dict[str, list[str]]] = {}
    current: str | None = None
    for line in str(diff or "").splitlines():
        if line.startswith("diff --git"):
            match = re.search(r" b/(\S+)\s*$", line)
            current = _norm_path(match.group(1)) if match else None
            if current:
                files.setdefault(current, {"added": [], "removed": []})
            continue
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path and path != "/dev/null":
                current = _norm_path(path)
                files.setdefault(current, {"added": [], "removed": []})
            continue
        if line.startswith(
            ("--- ", "@@", "index ", "new file", "deleted file", "rename ", "copy ",
             "similarity ", "dissimilarity ", "old mode", "new mode", "Binary ", "\\ No newline")
        ):
            continue
        if current is None:
            continue
        if line.startswith("+"):
            files[current]["added"].append(line[1:])
        elif line.startswith("-"):
            files[current]["removed"].append(line[1:])
    return files


def _norm_path(path: str) -> str:
    clean = path.strip().strip('"')
    for prefix in ("a/", "b/"):
        if clean.startswith(prefix):
            clean = clean[2:]
            break
    while clean.startswith("./"):
        clean = clean[2:]
    return clean


def _file_kind(path: str) -> str:
    name = path.rsplit("/", 1)[-1].lower()
    if _WORKFLOW_RE.search(path):
        return "workflow"
    if name in _LOCKFILE_NAMES:
        return "lockfile"
    if name in _MANIFEST_NAMES or _REQUIREMENTS_RE.search(path):
        return "manifest"
    if _IAC_RE.search(path):
        return "iac"
    return "source"


def _is_ignorable_manifest_line(stripped: str) -> bool:
    if stripped in _IGNORABLE_MANIFEST_LINES:
        return True
    return stripped.startswith("#") or stripped.startswith("//")


def _extract_dependency(stripped: str) -> tuple[str, str] | None:
    for pattern in (_JSON_DEP_RE, _PEP508_DEP_RE, _TOML_DEP_RE, _REQ_DEP_RE, _GOMOD_DEP_RE):
        match = pattern.match(stripped) if pattern is not _JSON_DEP_RE else pattern.search(stripped)
        if not match:
            continue
        name = match.group(1).strip()
        if name.lower() in _RESERVED_MANIFEST_KEYS:
            return None
        version = _version_core(match.group(2))
        if not version:
            return None
        return name, version
    return None


def _version_core(value: str) -> str | None:
    match = _VERSION_CORE_RE.search(str(value or ""))
    return match.group(1) if match else None


def _is_major_bump(old_version: str, new_version: str) -> bool:
    old_major = _major(old_version)
    new_major = _major(new_version)
    if old_major is None or new_major is None:
        return True  # unparseable → treat as major, force a human
    return old_major != new_major


def _major(version: str) -> int | None:
    match = re.match(r"(\d+)", str(version or "").strip())
    return int(match.group(1)) if match else None


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
