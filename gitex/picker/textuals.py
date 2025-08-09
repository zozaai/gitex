from typing import List, Set
from gitex.models import FileNode
from gitex.picker.base import Picker, DefaultPicker
from textual.app import App, ComposeResult
from textual.widgets import Tree, Button, Header, Footer, Checkbox
from textual.scroll_view import ScrollView
from textual.widgets.tree import TreeNode
from textual.containers import Horizontal, Vertical
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

class _PickerApp(App):
    CSS = """
    ScrollView {
        height: 1fr;
        width: 1fr;
    }
    #picker-tree {
        border: solid gray;
        padding: 1;
    }
    #picker-tree .cursor-line {
        background: blue;
        color: white;
    }
    Button {
        margin: 1 2;
    }
    #select-all-container {
        padding: 1;
        border: solid gray;
        margin-bottom: 1;
    }
    #help-text {
        margin: 1;
        color: gray;
    }
    """
    
    BINDINGS = [
        ("up,down,left,right", "navigate", "Navigate tree"),
        ("space", "toggle_selection", "Toggle file/folder selection"),
        ("enter,return", "expand_collapse", "Expand/collapse folder"),
        ("ctrl+a", "select_all", "Select all files"),
        ("ctrl+d", "deselect_all", "Deselect all files"),
        ("ctrl+enter", "confirm", "Confirm selection"),
        ("q,escape", "quit", "Quit without selecting"),
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
        self.select_all_checkbox = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Vertical():
            # Select all checkbox at top
            with Horizontal(id="select-all-container"):
                self.select_all_checkbox = Checkbox("Select entire repository", id="select-all")
                yield self.select_all_checkbox
            
            # Help text
            yield Button("📖 Arrow keys: navigate | Space: select/deselect | Enter: expand/collapse | Ctrl+Enter: confirm", 
                        id="help-text", variant="default")
            
            # File tree
            tree = Tree("Files to include", id="picker-tree")
            for node in self.nodes:
                tree.root.add(self._format_label(node), data=node, allow_expand=bool(node.children))
            yield ScrollView(tree)
            
            # Action buttons
            with Horizontal():
                yield Button("Confirm Selection (Ctrl+Enter)", id="confirm", variant="success")
                yield Button("Select All (Ctrl+A)", id="select-all-btn", variant="primary") 
                yield Button("Deselect All (Ctrl+D)", id="deselect-all-btn", variant="warning")
                yield Button("Quit (Q)", id="quit", variant="error")

    async def on_mount(self) -> None:
        self.query_one(Tree).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            await self.action_confirm()
        elif event.button.id == "select-all-btn":
            await self.action_select_all()
        elif event.button.id == "deselect-all-btn":
            await self.action_deselect_all()
        elif event.button.id == "quit":
            await self.action_quit()

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "select-all":
            if event.value:
                await self.action_select_all()
            else:
                await self.action_deselect_all()

    async def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Lazy-load children on expand."""
        node = event.node
        file_node: FileNode = node.data
        if file_node and not node.children:
            for child in file_node.children:
                node.add(self._format_label(child), data=child, allow_expand=bool(child.children))

    def _format_label(self, file_node: FileNode) -> Text:
        """Generate label with colored checkbox and name based on selection state."""
        mark = "☑" if file_node.path in self.selected_paths else "☐"
        icon = "📁" if file_node.node_type == "directory" else "📄"
        label = f"{mark} {icon} {file_node.name}"
        
        if file_node.path in self.selected_paths:
            return Text(label, style="bold green")
        return Text(label)

    def _toggle_selection(self, node: TreeNode) -> None:
        """Toggle selection for a single node and update its children."""
        if node.data is None:
            return
            
        file_node: FileNode = node.data
        is_selected = file_node.path in self.selected_paths
        
        if is_selected:
            self.selected_paths.discard(file_node.path)
            # Also deselect all children
            self._deselect_recursively(node)
        else:
            self.selected_paths.add(file_node.path)
            # Also select all children
            self._select_recursively(node)
        
        # Update visual representation
        node.set_label(self._format_label(file_node))
        self._update_children_labels(node)
        self._update_ancestors(node)

    def _select_recursively(self, node: TreeNode) -> None:
        """Recursively select node and all its descendants."""
        if node.data is None:
            return
        
        file_node: FileNode = node.data
        self.selected_paths.add(file_node.path)
        
        # Select all file children in the actual FileNode structure
        if file_node.children:
            for child in file_node.children:
                self._select_file_node_recursively(child)

    def _deselect_recursively(self, node: TreeNode) -> None:
        """Recursively deselect node and all its descendants."""
        if node.data is None:
            return
            
        file_node: FileNode = node.data
        self.selected_paths.discard(file_node.path)
        
        # Deselect all file children in the actual FileNode structure
        if file_node.children:
            for child in file_node.children:
                self._deselect_file_node_recursively(child)

    def _select_file_node_recursively(self, file_node: FileNode) -> None:
        """Helper to recursively select FileNode and its children."""
        self.selected_paths.add(file_node.path)
        if file_node.children:
            for child in file_node.children:
                self._select_file_node_recursively(child)

    def _deselect_file_node_recursively(self, file_node: FileNode) -> None:
        """Helper to recursively deselect FileNode and its children."""
        self.selected_paths.discard(file_node.path)
        if file_node.children:
            for child in file_node.children:
                self._deselect_file_node_recursively(child)

    def _update_children_labels(self, node: TreeNode) -> None:
        """Update labels for all loaded children."""
        for child in node.children:
            if child.data:
                child.set_label(self._format_label(child.data))
                self._update_children_labels(child)

    def _update_ancestors(self, node: TreeNode) -> None:
        """Update parent labels up the tree."""
        if node.parent and node.parent.data:
            parent_node = node.parent
            parent_file_node = parent_node.data
            parent_node.set_label(self._format_label(parent_file_node))
            self._update_ancestors(parent_node)

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses with improved bindings."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        
        if event.key == "space" and node and node.data:
            await self.action_toggle_selection()
            event.stop()
        elif event.key == "enter" and node and node.data:
            await self.action_expand_collapse()
            event.stop()
        elif event.key == "ctrl+enter":
            await self.action_confirm()
            event.stop()
        elif event.key == "ctrl+a":
            await self.action_select_all()
            event.stop()
        elif event.key == "ctrl+d":
            await self.action_deselect_all()  
            event.stop()
        elif event.key == "q" or event.key == "escape":
            await self.action_quit()
            event.stop()

    async def action_navigate(self) -> None:
        """Navigation is handled by default Tree behavior."""
        pass

    async def action_toggle_selection(self) -> None:
        """Toggle selection of current node."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if node and node.data:
            self._toggle_selection(node)
            tree.refresh(layout=True)

    async def action_expand_collapse(self) -> None:
        """Expand or collapse current directory node."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if node and node.data and node.data.node_type == "directory":
            if node.is_expanded:
                node.collapse()
            else:
                node.expand()

    async def action_select_all(self) -> None:
        """Select all files in the tree."""
        def select_all_nodes(nodes: List[FileNode]) -> None:
            for node in nodes:
                self.selected_paths.add(node.path)
                if node.children:
                    select_all_nodes(node.children)
        
        select_all_nodes(self.nodes)
        if self.select_all_checkbox:
            self.select_all_checkbox.value = True
        await self._refresh_all_labels()

    async def action_deselect_all(self) -> None:
        """Deselect all files in the tree."""
        self.selected_paths.clear()
        if self.select_all_checkbox:
            self.select_all_checkbox.value = False
        await self._refresh_all_labels()

    async def _refresh_all_labels(self) -> None:
        """Refresh all visible tree node labels."""
        tree = self.query_one(Tree)
        
        def refresh_node_labels(node: TreeNode) -> None:
            if node.data:
                node.set_label(self._format_label(node.data))
            for child in node.children:
                refresh_node_labels(child)
        
        refresh_node_labels(tree.root)
        tree.refresh(layout=True)

    async def action_confirm(self) -> None:
        """Gather selected nodes and exit."""
        def gather_selected(nodes: List[FileNode]) -> List[FileNode]:
            result: List[FileNode] = []
            for node in nodes:
                if node.path in self.selected_paths:
                    result.append(node)
                if node.children:
                    result.extend(gather_selected(node.children))
            return result
        
        self.selected_nodes = gather_selected(self.nodes)
        self.post_message(self.Confirmed(list(self.selected_paths)))
        self.exit()

    async def action_quit(self) -> None:
        """Exit without selecting anything."""
        self.selected_nodes = []
        self.exit()