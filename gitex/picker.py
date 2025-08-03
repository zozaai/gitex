from abc import ABC, abstractmethod
from typing import List
from gitex.models import FileNode
import os

class Picker(ABC):
    """
    Abstract base class for selecting which FileNode objects to include from a filesystem path.
    Concrete strategies should implement the `pick` method to return a list of FileNode nodes.
    """
    @abstractmethod
    def pick(self, root_path: str) -> List[FileNode]:
        """
        Given a root path, return a list of FileNode objects representing
        the selected files and directories under that path.
        """

class DefaultPicker(Picker):
    """
    Default Picker strategy: recursively includes all files and directories,
    optionally ignoring hidden entries.
    """
    def __init__(self, ignore_hidden: bool = True):
        self.ignore_hidden = ignore_hidden

    def pick(self, root_path: str) -> List[FileNode]:
        def _build(path: str) -> FileNode:
            name = os.path.basename(path) or path
            is_dir = os.path.isdir(path)
            node = FileNode(
                name=name,
                path=path,
                node_type="directory" if is_dir else "file",
                children=None
            )
            if is_dir:
                try:
                    entries = os.listdir(path)
                except PermissionError:
                    entries = []
                children = []
                for entry in entries:
                    if self.ignore_hidden and entry.startswith('.'):
                        continue
                    child_path = os.path.join(path, entry)
                    children.append(_build(child_path))
                node.children = children
            return node

        if os.path.isdir(root_path):
            nodes: List[FileNode] = []
            for entry in os.listdir(root_path):
                if self.ignore_hidden and entry.startswith('.'):
                    continue
                nodes.append(_build(os.path.join(root_path, entry)))
            return nodes
        else:
            return [_build(root_path)]
