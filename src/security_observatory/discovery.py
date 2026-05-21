from __future__ import annotations

from pathlib import Path

from .model import DEFAULT_EXCLUDES


def is_git_repo(path: Path) -> bool:
    git_marker = path / ".git"
    return git_marker.is_dir() or git_marker.is_file()


def discover_repos(root: Path = Path("~/Dev").expanduser(), limit: int | None = None) -> list[Path]:
    repos: list[Path] = []
    root = root.expanduser().resolve()
    if not root.exists():
        return repos

    def walk(path: Path) -> None:
        if limit and len(repos) >= limit:
            return
        if path.name in DEFAULT_EXCLUDES or path.name.startswith(".Trash"):
            return
        if is_git_repo(path):
            repos.append(path)
            return
        try:
            children = sorted([child for child in path.iterdir() if child.is_dir()], key=lambda p: p.name.lower())
        except (OSError, PermissionError):
            return
        for child in children:
            if child.name in DEFAULT_EXCLUDES:
                continue
            walk(child)

    walk(root)
    return repos
