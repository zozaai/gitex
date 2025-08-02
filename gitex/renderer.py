from typing import List, Optional
from gitex.models import FileNode
import os

class Rendered:
    """
    Rendered takes a list of FileNode objects and produces prompt-ready representations:
      - render_tree(): shows the directory/file hierarchy in ASCII form
      - render_files(): prints each file's contents, prefixed by its full path
    """
    def __init__(self, nodes: List[FileNode]):
        self.nodes = nodes

    def render_tree(self) -> str:
        """Return an ASCII tree of the FileNode hierarchy."""
        def _render(nodes: List[FileNode], prefix: str = "") -> List[str]:
            lines: List[str] = []
            count = len(nodes)
            for idx, node in enumerate(nodes):
                connector = "└── " if idx == count - 1 else "├── "
                line = f"{prefix}{connector}{node.name}" + ("/" if node.node_type == "directory" else "")
                lines.append(line)
                if node.children:
                    extension = "    " if idx == count - 1 else "│   "
                    lines.extend(_render(node.children, prefix + extension))
            return lines

        header = []
        for node in self.nodes:
            # top-level nodes: no connector, name as root
            header.append(node.name + ("/" if node.node_type == "directory" else ""))
            if node.children:
                header.extend(_render(node.children, ""))
        return "\n".join(header)

    def render_files(self, base_dir: Optional[str] = None) -> str:
        """Return all file contents, each prefixed by its full path."""
        outputs: List[str] = []
        def _collect_files(nodes: List[FileNode]):
            for node in nodes:
                if node.node_type == "file":
                    yield node
                if node.children:
                    yield from _collect_files(node.children)

        for file_node in _collect_files(self.nodes):
            path = file_node.path
            if base_dir and path.startswith(base_dir):
                path_display = path[len(base_dir):].lstrip(os.sep)
            else:
                path_display = path

            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                content = f"<Error reading file: {e}>"

            outputs.append(f"# {path_display}\n{content}")

        return "\n\n".join(outputs)
