from typing import List, Set
from gitex.models import FileNode
from gitex.picker.base import Picker, DefaultPicker
from textual.app import App, ComposeResult
from textual.widgets import Tree, Button, Header, Footer
# from textual.scroll_view import ScrollView
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
    #picker-tree {
        height: 1fr;
        width: 1fr;
        border: solid gray;
        padding: 1;
    }

    #actions {
        height: auto;
    }

    #picker-tree .cursor-line {
        background: blue;
        color: white;
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

        root_node = self.nodes[0]
        tree = Tree(self._format_label(root_node), id="picker-tree", data=root_node)

        if root_node.children:
            for child in root_node.children:
                tree.root.add(self._format_label(child), data=child, allow_expand=bool(child.children))

        yield tree

        with Horizontal(id="actions"):
            yield Button("Quit", id="quit", variant="error")

        yield Footer()


    async def on_mount(self) -> None:
        tree = self.query_one(Tree)
        tree.focus()
        # The root "." is now visible and focusable; it is expanded by default to show its contents
        tree.root.expand()

    async def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Lazy-load children on expand."""
        node = event.node
        file_node: FileNode = node.data
        if file_node and not node.children:
            for child in file_node.children:
                node.add(self._format_label(child), data=child, allow_expand=bool(child.children))

    def _format_label(self, file_node: FileNode) -> Text:
        """Generate label with colored checkbox and name based on selection state."""
        mark = "[✓]" if file_node.path in self.selected_paths else "[ ]"
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
        """Update a parent node's label based on selection state."""
        if not node.data:
            return

        file_node: FileNode = node.data
        
        # If the parent itself is explicitly selected, mark it Green [✓]
        if file_node.path in self.selected_paths:
            mark = "[✓]"
            style = "bold green"
        else:
            # Check children to see if we need a partial state [-]
            # We can only check UI children easily here
            child_paths = [c.data.path for c in node.children if c.data]
            selected_children = [p for p in child_paths if p in self.selected_paths]
            
            if child_paths and len(selected_children) == len(child_paths):
                # All UI children selected (and parent not in set? shouldn't happen often if logic holds)
                mark = "[✓]"
                style = "bold green"
            elif selected_children:
                # Some children selected
                mark = "[-]"
                style = "" # Default color for partial
            else:
                # No children selected
                mark = "[ ]"
                style = ""

        label = f"{mark} {file_node.name}"
        node.set_label(Text(label, style=style))
        
        if node.parent:
            self._update_parent_label(node.parent)

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses: space to toggle, enter to confirm, q to quit."""
        
        # Note: Left/Right arrows are handled by BINDINGS automatically
        
        if event.key == "space":
            # Pure toggle, no expansion
            await self.action_toggle()
            event.stop()
        elif event.key == "enter":
            await self.action_confirm()
            event.stop()
        elif event.key == "q":
            await self.action_quit()
            event.stop()


    async def action_confirm(self) -> None:
        """Gather selected nodes while preserving hierarchy, then exit."""
        def prune(nodes: List[FileNode]) -> List[FileNode]:
            out: List[FileNode] = []
            for n in nodes:
                if n.node_type == "file":
                    if n.path in self.selected_paths:
                        out.append(n)
                else:
                    children = prune(n.children or [])
                    # Include directory if it contains selected items
                    if children or n.path in self.selected_paths:
                        new_node = n.model_copy(deep=True)
                        new_node.children = children
                        out.append(new_node)
            return out

        self.selected_nodes = prune(self.nodes)
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
        
        # tree.scroll_to_node(node, animate=False)


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



    async def action_toggle(self) -> None:
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node or node.data is None:
            return

        # 1. Determine target state (if currently selected, deselect, etc.)
        file_node: FileNode = node.data
        is_selecting = file_node.path not in self.selected_paths

        # 2. Update the logical set (The Data)
        # We walk the FileNode data structure, NOT the UI Tree
        self._set_subtree_selection(file_node, is_selecting)

        # 3. Update the visuals (The UI)
        # We only update UI nodes that actually exist (are expanded/visible)
        self._refresh_subtree_visuals(node)
        
        # 4. Update parent labels (to handle partial states up the tree)
        if node.parent:
            self._update_parent_label(node.parent)

    def _set_subtree_selection(self, file_node: FileNode, select: bool) -> None:
        """Recursively update selected_paths using the Data Model (FileNode)."""
        if select:
            self.selected_paths.add(file_node.path)
        else:
            self.selected_paths.discard(file_node.path)
        
        # Recurse through data children even if UI node is collapsed
        if file_node.children:
            for child in file_node.children:
                self._set_subtree_selection(child, select)

    def _refresh_subtree_visuals(self, tree_node: TreeNode) -> None:
        """Recursively update labels for existing UI TreeNodes."""
        if tree_node.data:
            tree_node.set_label(self._format_label(tree_node.data))
        
        # Only recurse if the UI node has children (is expanded)
        for child in tree_node.children:
            self._refresh_subtree_visuals(child)

    async def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Keep the highlighted (cursor) node visible while navigating."""
        tree = event.control  # the Tree that emitted the event
        tree.scroll_to_node(event.node, animate=False)
