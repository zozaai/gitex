"""

this is a module for 
ignoring the .gitignore
"""


# gitignore.py
from __future__ import annotations
from pathlib import Path
from typing import List

import pathspec  # pip install pathspec


# Hard-coded excludes that *always* apply
HARDCODED = [".git", ".gitignore", "*.egg-info", "__pycache__"]


def _load_gitignore_specs(start_dir: Path) -> List[pathspec.PathSpec]:
    """Return PathSpec objects for every .gitignore found between
    `start_dir` and the filesystem root."""
    specs: List[pathspec.PathSpec] = []
    for parent in (start_dir, *start_dir.parents):
        gitignore = parent / ".gitignore"
        if gitignore.is_file():
            with gitignore.open(encoding="utf-8") as fh:
                lines = [ln.rstrip() for ln in fh if ln.strip() and not ln.startswith("#")]
            specs.append(pathspec.PathSpec.from_lines("gitwildmatch", lines))
    return specs


class GitAwareFilter:
    """Callable that answers: *should this path be ignored?*"""

    def __init__(self, root: Path):
        self.root = root
        self.hardcoded = pathspec.PathSpec.from_lines("gitwildmatch", HARDCODED)
        self.git_specs = _load_gitignore_specs(root)

    def __call__(self, path: Path) -> bool:
        """Return True if the path should be *excluded*."""
        rel = path.relative_to(self.root).as_posix()
        if self.hardcoded.match_file(rel):
            return True
        for spec in self.git_specs:
            if spec.match_file(rel):
                return True
        return False