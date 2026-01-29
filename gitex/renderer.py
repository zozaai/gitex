import os
import re
from typing import List, Optional, Tuple
from gitex.models import FileNode
from gitex.docstring_extractor import extract_docstrings
from pathlib import Path

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
        if node.name == ".":
            return "."
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
        file_nodes = self._collect_files(self.nodes)
        blocks = []

        for node in file_nodes:
            path_display = self._relative_path(node.path, base_dir)

            # Skip decoding/reading image files; just list them later
            if _is_binary_file(node.path):
                continue

            content = self._read_file(node.path)

            lang = _detect_lang(node.path)
            open_fence, close_fence = _build_fence(content, lang)

            blocks.append(
                f"# {path_display}\n"
                f"{open_fence}\n"
                f"{content}\n"
                f"{close_fence}"
            )

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


def _is_binary_file(path: str) -> bool:
    return Path(path).suffix.lower() in {
        # images
        ".png", ".jpg", ".jpeg", ".gif", ".webp",
        ".bmp", ".tif", ".tiff", ".ico",
        ".svg",

        # documents
        ".pdf",

        # notebooks
        ".ipynb",

        # archives
        ".zip", ".tar", ".gz", ".tgz", ".rar", ".7z",

        # python / binaries
        ".whl", ".egg", ".pyc",
        ".so", ".dll", ".exe", ".dylib",

        # media
        ".mp4", ".mov", ".avi", ".mkv",
        ".mp3", ".wav",

        # office
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    }


def _detect_lang(path: str) -> str:
    ext = Path(path).suffix.lower()
    mapping = {
        ".py": "python",
        ".sh": "bash",
        ".bash": "bash",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".md": "markdown",
        ".txt": "text",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
    }

    name = Path(path).name
    if name == "Dockerfile" or name.lower().startswith("dockerfile."):
        return "dockerfile"
    if name == "Makefile":
        return "makefile"

    return mapping.get(ext, "")



def _build_fence(content: str, lang: str) -> Tuple[str, str]:
    """
    Build a safe Markdown code fence.
    Always uses triple backticks or more.
    """
    runs = re.findall(r"`+", content)
    max_ticks = max((len(r) for r in runs), default=0)

    fence_len = max(3, max_ticks + 1)   # ✅ enforce minimum triple backticks
    fence = "`" * fence_len

    opening = f"{fence}{lang}".rstrip()
    closing = fence
    return opening, closing
