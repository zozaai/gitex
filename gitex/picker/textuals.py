from typing import List
from gitex.models import FileNode
from gitex.picker.base import Picker, DefaultPicker
from textual.app import App, ComposeResult
from textual.widgets import Tree, Button, Header, Footer
from textual.widgets.tree import TreeNode
from textual.containers import Horizontal

class TextualPicker(Picker):
    """
    Uses Textual to display a navigable tree of FileNodes with checkboxes.
    """
    def __init__(self, ignore_hidden: bool = True, respect_gitignore: bool = False):
        self.default_picker = DefaultPicker(ignore_hidden, respect_gitignore)

    def pick(self, root_path: str) -> List[FileNode]:
        raw = self.default_picker.pick(root_path)
        app = _PickerApp(raw)
        app.run()
        return app.selected_nodes

class _PickerApp(App):
    BINDINGS = [
        ("space", "toggle", "Toggle selection"),
        ("enter", "confirm", "Confirm"),
        ("q", "quit", "Quit")
    ]

    def __init__(self, nodes: List[FileNode], **kwargs):
        super().__init__(**kwargs)
        self.nodes = nodes
        self.selected_paths: set[str] = set()
        self.selected_nodes: List[FileNode] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        tree = Tree("Files to include")
        self._build_tree(tree.root, self.nodes)
        yield tree
        with Horizontal():
            yield Button("Confirm", id="confirm")
            yield Button("Quit", id="quit")
        yield Footer()

    def _build_tree(self, parent: TreeNode, nodes: List[FileNode]):
        for node in nodes:
            label = "[ ] " + node.name
            branch = parent.add(label, data=node, expand=node.node_type == "directory")
            if node.children:
                self._build_tree(branch, node.children)

    async def action_toggle(self) -> None:
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node:
            return
        data = node.data
        label = node.label.plain
        if label.startswith("[ ]"):
            node.set_label(f"[x] {data.name}")
            self.selected_paths.add(data.path)
        else:
            node.set_label(f"[ ] {data.name}")
            self.selected_paths.discard(data.path)
        node.tree.refresh_line(node.line)

    async def action_confirm(self) -> None:
        def _gather(nodes: List[FileNode]):
            for n in nodes:
                if n.path in self.selected_paths and n.node_type == "file":
                    yield n
                if n.children:
                    yield from _gather(n.children)
        self.selected_nodes = list(_gather(self.nodes))
        self.exit()

    async def action_quit(self) -> None:
        self.exit()
