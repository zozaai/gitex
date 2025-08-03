from typing import List
from gitex.models import FileNode
from gitex.picker.base import Picker, DefaultPicker
from textual.app import App, ComposeResult
from textual.widgets import Tree, Button, Header, Footer
from textual.widgets.tree import TreeNode
from textual.containers import Horizontal
from textual import events

class TextualPicker(Picker):
    """
    Uses Textual to display a navigable tree of FileNodes with checkboxes.
    """
    def __init__(self, ignore_hidden: bool = True, respect_gitignore: bool = False):
        self.default_picker = DefaultPicker(ignore_hidden=ignore_hidden, respect_gitignore=respect_gitignore)

    def pick(self, root_path: str) -> List[FileNode]:
        raw = self.default_picker.pick(root_path)
        app = _PickerApp(raw)
        app.run()
        return app.selected_nodes

class _PickerApp(App):
    CSS_PATH = None  # Optional: provide a CSS file for styling
    BINDINGS = [
        ("space", "toggle", "Toggle file or folder selection"),
        ("c", "confirm", "Confirm selection"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, nodes: List[FileNode], **kwargs):
        super().__init__(**kwargs)
        self.nodes = nodes
        self.selected_paths: set[str] = set()
        self.selected_nodes: List[FileNode] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        tree = Tree("Files to include", id="picker-tree")
        self._build_tree(tree.root, self.nodes)
        yield tree
        with Horizontal():
            yield Button("Confirm", id="confirm", variant="success")
            yield Button("Quit", id="quit", variant="error")
        yield Footer()

    async def on_mount(self) -> None:
        tree = self.query_one("#picker-tree", Tree)
        tree.focus()

    def _build_tree(self, parent: TreeNode, nodes: List[FileNode]):
        for node in nodes:
            label = "[ ] " + node.name
            branch = parent.add(label, data=node, expand=node.node_type == "directory")
            if node.children:
                self._build_tree(branch, node.children)

    def on_key(self, event: events.Key) -> None:
        # Prevent default Enter behavior (expand/collapse) for Tree
        if event.key == "enter":
            event.stop()
            self.action_toggle()

    def _toggle_node_and_children(self, node: TreeNode, select: bool) -> None:
        """Recursively toggle a node and its children."""
        file_node: FileNode = node.data
        label = node.label.plain
        new_label = f"[{'x' if select else ' '}] {file_node.name}"
        node.set_label(new_label)
        if select:
            self.selected_paths.add(file_node.path)
        else:
            self.selected_paths.discard(file_node.path)
        # Recursively update children for directories
        if file_node.node_type == "directory":
            for child in node.children:
                self._toggle_node_and_children(child, select)
        node.tree.refresh_line(node.line)

    def action_toggle(self):
        tree = self.query_one("#picker-tree", Tree)
        node: TreeNode = tree.cursor_node
        if not node or not node.data:
            return
        file_node: FileNode = node.data
        label = node.label.plain
        select = not label.startswith("[x]")
        self._toggle_node_and_children(node, select)

    async def action_confirm(self) -> None:
        def _gather(nodes: List[FileNode]):
            for n in nodes:
                # Include files and optionally folders if desired
                if n.path in self.selected_paths and n.node_type == "file":
                    yield n
                if n.children:
                    yield from _gather(n.children)
        self.selected_nodes = list(_gather(self.nodes))
        self.exit()

    async def action_quit(self) -> None:
        self.exit()