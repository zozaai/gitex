from typing import List, Set
from gitex.models import FileNode
import questionary
from .base import Picker, DefaultPicker
      
class QuestinoaryPicker(Picker):
    """
    Interactive picker that presents an interactive checkbox-based terminal UI
    for users to select which files to include.
    """
    def __init__(self, ignore_hidden: bool = True, respect_gitignore: bool = False):
        self.base_picker = DefaultPicker(ignore_hidden, respect_gitignore)

    def pick(self, root_path: str) -> List[FileNode]:
        # Build full tree of FileNodes
        nodes = self.base_picker.pick(root_path)
        # Flatten to file paths
        file_nodes = list(self._collect_files(nodes))
        choices = [fn.path for fn in file_nodes]

        # Prompt user
        selected = questionary.checkbox(
            "Select files to include:",
            choices=choices
        ).ask()
        if selected is None:
            # User aborted
            return []

        selected_set: Set[str] = set(selected)

        # Prune tree to only selected files (and include directory structure)
        pruned = self._prune_tree(nodes, selected_set)
        return pruned

    def _collect_files(self, nodes: List[FileNode]):
        for node in nodes:
            if node.node_type == "file":
                yield node
            if node.children:
                yield from self._collect_files(node.children)

    def _prune_tree(self, nodes: List[FileNode], selected_set: Set[str]) -> List[FileNode]:
        """
        Recursively retain only branches that lead to selected files.
        Directories with no selected children are removed. Selected files kept.
        """
        pruned: List[FileNode] = []
        for node in nodes:
            if node.node_type == "file":
                if node.path in selected_set:
                    pruned.append(node)
            else:
                # Directory: prune children
                children = self._prune_tree(node.children or [], selected_set)
                if children:
                    new_node = node.copy(deep=True)
                    new_node.children = children
                    pruned.append(new_node)
        return pruned
