from abc import ABC, abstractmethod
from typing import List, Optional
from gitex.models import FileNode
import os
import pathspec


class Picker(ABC):
    """
    Abstract base class for selecting which FileNode objects to include from a filesystem path.
    Concrete strategies should implement the `pick` method.
    """
    @abstractmethod
    def pick(self, root_path: str) -> List[FileNode]:
        """
        Given a root path, return a list of FileNode nodes under that path.
        """

class DefaultPicker(Picker):
    """
    Default picker that recursively collects FileNode objects.
    Can ignore hidden files, and optionally respect .gitignore patterns.
    """
    def __init__(self, ignore_hidden: bool = True, respect_gitignore: bool = False):
        self.ignore_hidden = ignore_hidden
        self.respect_gitignore = respect_gitignore
        self._gitignore_spec: Optional[pathspec.PathSpec] = None

    def pick(self, root_path: str) -> List[FileNode]:
        # Load .gitignore patterns if needed
        if self.respect_gitignore:
            self._load_gitignore(root_path)

        # Return the root directory itself to preserve structure
        return [self._walk(root_path, root_path)]
    
    def _walk(self, path: str, root_path: str) -> FileNode:
        # Use "." for the root node name to match standard tree output
        if path == root_path:
            name = "."
        else:
            name = os.path.basename(path) or path

        is_dir = os.path.isdir(path)
        children = None
        if is_dir:
            try:
                entries = sorted(os.listdir(path))
            except PermissionError:
                entries = []
            children = []
            for entry in entries:
                if self._should_skip(entry, root_path, parent_path=path):
                    continue
                children.append(self._walk(os.path.join(path, entry), root_path))
        return FileNode(
            name=name,
            path=path,
            node_type="directory" if is_dir else "file",
            children=children
        )

    def _should_skip(self, name: str, root_path: str, parent_path: Optional[str] = None) -> bool:
        # Hidden files
        if self.ignore_hidden and name.startswith('.'):
            return True

        # Gitignore
        if self.respect_gitignore and self._gitignore_spec is not None:
            # compute relative path from root for matching
            rel_dir = parent_path[len(root_path) + 1:] if parent_path and parent_path.startswith(root_path) else ''
            rel_path = os.path.join(rel_dir, name) if rel_dir else name
            if self._gitignore_spec.match_file(rel_path):
                return True
        return False

    def _load_gitignore(self, root_path: str):
        gitignore_file = os.path.join(root_path, '.gitignore')
        if pathspec and os.path.isfile(gitignore_file):
            with open(gitignore_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            self._gitignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', lines)
        else:
            self._gitignore_spec = None
            