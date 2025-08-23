from typing import List, Optional
from gitex.models import FileNode
from gitex.docstring_extractor import extract_docstrings
from pathlib import Path
import os

class Renderer:
    """
    Rendered takes a list of FileNode objects and produces prompt-ready representations:
      - render_tree(): shows the directory/file hierarchy in ASCII form
      - render_files(): prints each file's contents, prefixed by its full path
    """
    def __init__(self, nodes: List[FileNode]):
        self.nodes = nodes

    def render_tree(self) -> str:
        """Return an ASCII tree of the FileNode hierarchy."""
        lines = []
        for root in self.nodes:
            lines.append(self._format_node_header(root))
            if root.children:
                lines.extend(self._format_children(root.children, prefix=""))
        return "\n".join(lines)

    def _format_node_header(self, node: FileNode) -> str:
        """Format the header line for a root node."""
        suffix = "/" if node.node_type == "directory" else ""
        error_indicator = " [Permission Denied]" if node.metadata.get('permission_denied') else ""
        return f"{node.name}{suffix}{error_indicator}"

    def _format_children(self, nodes: List[FileNode], prefix: str) -> List[str]:
        """Recursively format child nodes with ASCII connectors."""
        formatted = []
        count = len(nodes)
        for index, node in enumerate(nodes):
            is_last = (index == count - 1)
            connector = "└── " if is_last else "├── "
            suffix = "/" if node.node_type == "directory" else ""
            error_indicator = ""
            if node.metadata.get('permission_denied'):
                error_indicator = " [Permission Denied]"
                
            formatted.append(f"{prefix}{connector}{node.name}{suffix}{error_indicator}")

            if node.children:
                next_prefix = prefix + ("    " if is_last else "│   ")
                formatted.extend(self._format_children(node.children, next_prefix))
        return formatted

    def render_files(self, base_dir: Optional[str] = None) -> str:
        """Return all file contents, each block prefixed by its full or relative path."""
        file_nodes = self._collect_files(self.nodes)
        blocks = []

        for node in file_nodes:
            path_display = self._relative_path(node.path, base_dir)
            content = self._read_file(node.path)
            blocks.append(f"# {path_display}\n{content}")

        return "\n\n".join(blocks)

    def render_docstrings(self, base_dir: Optional[str] = None, symbol_target: Optional[str] = None, include_empty_classes: bool = False) -> str:
        """Return all file contents, each block prefixed by its full or relative path."""
        file_nodes = self._collect_files(self.nodes)
        blocks = []

        if symbol_target:
            # If a symbol is targeted, we find the corresponding file and extract from it.
            path_parts = symbol_target.split('.')
            # First, try to find a file path that matches the symbol
            target_file_path = None
            for i in range(len(path_parts), 0, -1):
                potential_path = os.path.join(*path_parts[:i]) + ".py"
                for node in file_nodes:
                    if node.path.endswith(potential_path):
                        target_file_path = node.path
                        break
                if target_file_path:
                    break
            
            if target_file_path:
                path_display = self._relative_path(target_file_path, base_dir)
                content = extract_docstrings(Path(target_file_path), symbol_target, include_empty_classes)
                blocks.append(f"# {path_display}\n{content}")
            else:
                return f"Error: Could not find a Python file corresponding to the symbol '{symbol_target}'."

        else:
            # Original behavior: extract from all Python files.
            for node in file_nodes:
                if not node.name.endswith(".py"):
                    continue
                path_display = self._relative_path(node.path, base_dir)
                content = extract_docstrings(Path(node.path), None, include_empty_classes)
                blocks.append(f"# {path_display}\n{content}")

        return "\n\n".join(blocks)

    def _collect_files(self, nodes: List[FileNode]) -> List[FileNode]:
        """Traverse nodes and return a list of FileNode objects of type 'file'."""
        files = []
        for node in nodes:
            if node.node_type == "file":
                files.append(node)
            if node.children:
                files.extend(self._collect_files(node.children))
        return files

    def _relative_path(self, path: str, base_dir: Optional[str]) -> str:
        """Strip base_dir prefix from path if provided, else return full path."""
        if base_dir and path.startswith(base_dir):
            return path[len(base_dir):].lstrip(os.sep)
        return path

    def _read_file(self, path: str) -> str:
        """Safely read file contents, returning error message on failure."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"<Error reading file: {e}>"
