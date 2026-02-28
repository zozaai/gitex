# gitex/picker/textuals.py
import logging
from typing import List, Set, Dict
from pathlib import Path
from gitex.models import FileNode
from gitex.picker.base import Picker, DefaultPicker
from textual.app import App, ComposeResult
from textual.widgets import Tree, Button, Header, Footer, OptionList, Label
from textual.widgets.tree import TreeNode
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual import events
from rich.text import Text

from gitex.slicer import get_symbols_in_file, resolve_slice_dependencies

class SymbolSelectionScreen(ModalScreen[str]):
    """Screen to select a symbol for slicing."""
    
    CSS = """
    SymbolSelectionScreen {
        align: center middle;
    }
    #dialog {
        padding: 1 2;
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $background 80%;
        background: $surface;
    }
    """
    
    def __init__(self, file_name: str, symbols: List[str], **kwargs):
        super().__init__(**kwargs)
        self.file_name = file_name
        self.symbols = symbols
        
    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Select a class/function in [bold cyan]{self.file_name}[/] to slice:")
            yield OptionList(*self.symbols, id="symbol_list")
            
    def on_mount(self) -> None:
        self.query_one(OptionList).focus()
        
    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # Fired natively when the user presses Enter on an option
        self.dismiss(str(event.option.prompt))
        
    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


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

    BINDINGS = [ 
        ("space", "toggle", "Toggle file/folder selection"), 
        ("enter", "confirm", "Confirm selection"), 
        ("s", "slice", "Slice Python file"),
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
        tree.root.expand()

    async def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Lazy-load children on expand."""
        node = event.node
        file_node: FileNode = node.data
        if file_node and not node.children:
            for child in file_node.children:
                node.add(self._format_label(child), data=child, allow_expand=bool(child.children))

    def _get_selection_state(self, file_node: FileNode) -> int:
        """Calculates selection from Data Model. 2 if fully selected, 1 if partially selected, 0 if not selected."""
        if file_node.path in self.selected_paths:
            return 2
            
        if file_node.node_type == "file" or not file_node.children:
            return 0
            
        child_states = [self._get_selection_state(c) for c in file_node.children]
        
        if all(s == 2 for s in child_states) and child_states:
            return 2
        if any(s > 0 for s in child_states):
            return 1
        return 0

    def _format_label(self, file_node: FileNode) -> Text:
        """Generate label with colored checkbox and name based on Data Model selection state."""
        state = self._get_selection_state(file_node)
        if state == 2:
            mark = "[✓]"
            style = "bold green"
        elif state == 1:
            mark = "[-]"
            style = ""
        else:
            mark = "[ ]"
            style = ""
            
        label = f"{mark} {file_node.name}"
        return Text(label, style=style)

    def _set_subtree_selection(self, file_node: FileNode, select: bool) -> None:
        """Recursively update selected_paths using the Data Model (FileNode)."""
        if select:
            self.selected_paths.add(file_node.path)
        else:
            self.selected_paths.discard(file_node.path)
        
        if file_node.children:
            for child in file_node.children:
                self._set_subtree_selection(child, select)

    def _update_parent_label(self, node: TreeNode) -> None:
        """Update a parent node's label based on selection state."""
        if not node.data: return
        node.set_label(self._format_label(node.data))
        if node.parent: self._update_parent_label(node.parent)

    def _refresh_subtree_visuals(self, tree_node: TreeNode) -> None:
        """Recursively update labels for existing UI TreeNodes."""
        if tree_node.data:
            tree_node.set_label(self._format_label(tree_node.data))
        for child in tree_node.children:
            self._refresh_subtree_visuals(child)

    async def on_key(self, event: events.Key) -> None:
        """Handle key presses: space to toggle, enter to confirm, q to quit."""
        
        # CRITICAL FIX: If a modal popup is active, DO NOT intercept its keys!
        if isinstance(self.screen, ModalScreen):
            return

        if event.key == "space":
            await self.action_toggle()
            event.stop()
        elif event.key == "enter":
            await self.action_confirm()
            event.stop()
        elif event.key == "q":
            await self.action_quit()
            event.stop()

    async def action_slice(self) -> None:
        """Invoked via `s` key. Opens Modal to Slice logic from a Class/Func."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node or node.data is None:
            return

        file_node: FileNode = node.data
        if file_node.node_type != "file" or not file_node.name.endswith(".py"):
            self.notify("Slicing is only supported on Python (.py) files.", severity="warning")
            return

        try:
            symbols = get_symbols_in_file(file_node.path)
        except Exception as e:
            self.notify(f"Failed to read file: {e}", severity="error")
            return

        if not symbols:
            self.notify(f"No classes or functions found in {file_node.name}.", severity="warning")
            return

        def handle_slice_selection(selected_symbol: str | None) -> None:
            if not selected_symbol:
                return
            try:
                logging.info(f"User selected symbol to slice: {selected_symbol}")
                root_path = self.nodes[0].path
                deps = resolve_slice_dependencies(root_path, file_node.path, selected_symbol)

                abs_to_node = self._get_absolute_to_node_path_mapping(self.nodes)
                
                matched_count = 0
                for abs_path in deps:
                    if abs_path in abs_to_node:
                        internal_path = abs_to_node[abs_path]
                        self.selected_paths.add(internal_path)
                        logging.info(f"Matched and selected internal path: {internal_path}")
                        matched_count += 1

                self._refresh_subtree_visuals(tree.root)
                self.notify(f"Sliced '{selected_symbol}': Auto-checked {matched_count} file(s).", severity="information")
            except Exception as e:
                logging.exception("Slicing process failed critically.")
                self.notify(f"Slicing failed: {e}", severity="error")

        # Open the modal and pass the callback function
        self.push_screen(SymbolSelectionScreen(file_node.name, symbols), callback=handle_slice_selection)

    def _get_absolute_to_node_path_mapping(self, nodes: List[FileNode]) -> Dict[str, str]:
        """Pre-computes lookup tables since path representation may vary."""
        mapping = {}
        for n in nodes:
            try:
                mapping[str(Path(n.path).resolve())] = n.path
            except Exception:
                pass
            if n.children:
                mapping.update(self._get_absolute_to_node_path_mapping(n.children))
        return mapping

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
        if not node: return
        if node.allow_expand and not node.is_expanded:
            node.expand()
            tree.refresh(layout=True)
            return
        if node.children:
            tree.select_node(node.children[0])

    async def action_collapse_or_parent(self) -> None:
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node: return
        if node.is_expanded:
            node.collapse()
            tree.refresh(layout=True)
            return
        if node.parent:
            tree.select_node(node.parent)

    async def action_toggle(self) -> None:
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if not node or node.data is None: return

        file_node: FileNode = node.data
        is_selecting = file_node.path not in self.selected_paths

        self._set_subtree_selection(file_node, is_selecting)
        self._refresh_subtree_visuals(node)
        
        if node.parent:
            self._update_parent_label(node.parent)

    async def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Keep the highlighted (cursor) node visible while navigating."""
        tree = event.control
        tree.scroll_to_node(event.node, animate=False)