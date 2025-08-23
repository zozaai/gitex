from typing import List, Set
from gitex.models import FileNode
from gitex.picker.base import Picker, DefaultPicker
from textual.app import App, ComposeResult
from textual.widgets import Tree, Button, Header, Footer
from textual.scroll_view import ScrollView
from textual.widgets.tree import TreeNode
from textual.containers import Horizontal
from textual.message import Message
from textual import events
from rich.text import Text

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

class _PickerApp(App):  # pylint: disable=too-many-public-methods
    CSS = """
    ScrollView {
        height: 1fr;
        width: 1fr;
    }
    #picker-tree {
        border: solid gray;
        padding: 1;
    }
    /* this is the focused row highlight */
    #picker-tree .cursor-line {
        background: blue;
        color: white;      /* optional: make text pop on the blue bar */
    }
    Button {
        margin: 1 2;
    }
    """
    # BINDINGS = [
    #     ("space", "toggle", "Toggle file or folder selection"),
    #     ("enter", "confirm", "Confirm selection"),
    #     ("q", "quit", "Quit without selecting"),
    # ]

    BINDINGS = [ ("space", "toggle", "Toggle file or folder selection"), 
                 ("enter", "confirm", "Confirm selection"), 
                 ("q", "quit", "Quit without selecting"), 
                 ("left", "collapse_or_parent", "Collapse / go to parent"), 
                 ("right", "expand_or_child", "Expand / go to first child")
              ]

    class Confirmed(Message):
        """Message sent when selection is confirmed."""
        def __init__(self, paths: List[str]) -> None:
            super().__init__()
            self.paths = paths

    def __init__(self, nodes: List[FileNode], **kwargs):
        super().__init__(**kwargs)
        self.nodes = nodes
        self.selected_paths: Set[str] = set()
        self.selected_nodes: List[FileNode] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        tree = Tree("Files to include", id="picker-tree")
        # build only root level
        for node in self.nodes:
            tree.root.add(self._format_label(node), data=node, allow_expand=bool(node.children))
        yield ScrollView(tree)
        with Horizontal():
            yield Button("Quit", id="quit", variant="error")
        yield Footer()

    # async def on_mount(self) -> None:
    #     # Focus the tree for keyboard navigation
    #     self.query_one(Tree).focus()
    async def on_mount(self) -> None:
        tree = self.query_one(Tree)
        tree.focus()
        tree.root.expand()   # show top-level entries immediately

    async def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Lazy-load children on expand."""
        node = event.node
        file_node: FileNode = node.data
        if file_node and not node.children:
            for child in file_node.children:
                node.add(self._format_label(child), data=child, allow_expand=bool(child.children))

    def _format_label(self, file_node: FileNode) -> Text:
        """Generate label with colored checkbox and name based on selection state."""
        mark = "[x]" if file_node.path in self.selected_paths else "[ ]"
        label = f"{mark} {file_node.name}"
        if file_node.path in self.selected_paths:
            return Text(label, style="bold green")
        return Text(label)

    def _toggle_recursively(self, node: TreeNode, select: bool) -> None:
        """Recursively toggle node and its children, then update ancestors."""
        if node.data is None:
            return
        file_node: FileNode = node.data
        if select:
            self.selected_paths.add(file_node.path)
        else:
            self.selected_paths.discard(file_node.path)
        node.set_label(self._format_label(file_node))
        for child in node.children:
            self._toggle_recursively(child, select)
        if node.parent and node.parent.data:
            self._update_parent_label(node.parent)

    def _update_parent_label(self, node: TreeNode) -> None:
        """Update a parent node's label based on its children's selection state."""
        file_node: FileNode = node.data  # type: ignore
        child_paths = [c.data.path for c in node.children if c.data]
        selected = [p for p in child_paths if p in self.selected_paths]
        if child_paths and len(selected) == len(child_paths):
            mark = "[x]"
        elif selected:
            mark = "[-]"
        else:
            mark = "[ ]"
        label = f"{mark} {file_node.name}"
        if file_node.path in self.selected_paths:
            node.set_label(Text(label, style="bold green"))
        else:
            node.set_label(Text(label))
        if node.parent and node.parent.data:
            self._update_parent_label(node.parent)

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses: space to expand/toggle, enter to confirm, q to quit."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        
        if event.key == "space" and node and node.data:
            # If it's a directory that can be expanded/collapsed, do that instead of selecting
            if node.allow_expand:
                if node.is_expanded:
                    node.collapse()
                else:
                    node.expand()
                tree.refresh(layout=True)
            else:
                # It's a file, so toggle selection
                await self.action_toggle()
            event.stop()
        elif event.key == "enter":
            await self.action_confirm()
            event.stop()
        elif event.key == "q":
            await self.action_quit()
            event.stop()
        elif event.key == "enter":
            await self.action_confirm()
            event.stop()
        elif event.key == "q":
            await self.action_quit()
            event.stop()

    async def action_toggle(self) -> None:
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node or node.data is None:
            return  # don't toggle the synthetic root
        self._toggle_recursively(node, node.data.path not in self.selected_paths)
        tree.refresh(layout=True)


    async def action_confirm(self) -> None:
        """Gather selected nodes, post message, and exit."""
        def gather(nodes: List[FileNode]) -> List[FileNode]:
            out: List[FileNode] = []
            for n in nodes:
                if n.path in self.selected_paths:
                    out.append(n)
                if n.children:
                    out.extend(gather(n.children))
            return out
        self.selected_nodes = gather(self.nodes)
        self.post_message(self.Confirmed(list(self.selected_paths)))
        self.exit()

    async def action_quit(self) -> None:
        self.exit()

    async def action_expand_or_child(self) -> None:
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node:
            return
        # If this row can expand and is currently collapsed, expand it (works for root and folders)
        if node.allow_expand and not node.is_expanded:
            node.expand()                  # sync
            tree.refresh(layout=True)
            return
        # Already expanded: move into first child if any
        if node.children:
            tree.select_node(node.children[0])

    async def action_collapse_or_parent(self) -> None:
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node:
            return
        if node.is_expanded:
            node.collapse()                # sync
            tree.refresh(layout=True)
            return
        if node.parent:
            tree.select_node(node.parent)
