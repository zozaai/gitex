from typing import List, Optional
from gitex.models import FileNode
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
        return f"{node.name}{suffix}"

    def _format_children(self, nodes: List[FileNode], prefix: str) -> List[str]:
        """Recursively format child nodes with ASCII connectors."""
        formatted = []
        count = len(nodes)
        for index, node in enumerate(nodes):
            is_last = (index == count - 1)
            connector = "└── " if is_last else "├── "
            suffix = "/" if node.node_type == "directory" else ""
            formatted.append(f"{prefix}{connector}{node.name}{suffix}")

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
