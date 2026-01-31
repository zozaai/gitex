import pytest
from unittest.mock import patch
from textual.widgets import Tree
from gitex.models import FileNode, NodeType
from gitex.picker.textuals import TextualPicker, _PickerApp

# --- Fixtures ---

@pytest.fixture
def mock_file_tree():
    """
    Creates a mock FileNode tree:
    .
    ├── folder/
    │   ├── file1.py
    │   └── file2.py
    └── root_file.txt
    """
    file1 = FileNode(name="file1.py", path="root/folder/file1.py", node_type=NodeType.FILE)
    file2 = FileNode(name="file2.py", path="root/folder/file2.py", node_type=NodeType.FILE)
    folder = FileNode(
        name="folder", 
        path="root/folder", 
        node_type=NodeType.DIRECTORY, 
        children=[file1, file2]
    )
    root_file = FileNode(name="root_file.txt", path="root/root_file.txt", node_type=NodeType.FILE)
    
    root = FileNode(
        name=".", 
        path="root", 
        node_type=NodeType.DIRECTORY, 
        children=[folder, root_file]
    )
    return [root]


# --- Unit Tests for TextualPicker Wrapper ---

def test_textual_picker_pick_calls_app(mock_file_tree):
    """Test that the wrapper class initializes the App and returns selected nodes."""
    picker = TextualPicker(ignore_hidden=True)
    
    with patch("gitex.picker.textuals.DefaultPicker.pick", return_value=mock_file_tree):
        with patch("gitex.picker.textuals._PickerApp") as MockApp:
            mock_app_instance = MockApp.return_value
            mock_app_instance.run.return_value = None
            mock_app_instance.selected_nodes = ["result_node"]
            
            result = picker.pick("root")
            
            assert result == ["result_node"]
            MockApp.assert_called_once_with(mock_file_tree)
            mock_app_instance.run.assert_called_once()


# --- Integration Tests for _PickerApp using Pilot ---

@pytest.mark.asyncio
async def test_app_initialization(mock_file_tree):
    """Test that the app loads the tree and expands the root."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        assert tree is not None
        assert tree.root.is_expanded
        assert "." in str(tree.root.label)
        assert len(tree.root.children) == 2


@pytest.mark.asyncio
async def test_lazy_loading_children(mock_file_tree):
    """Test that expanding a node lazy-loads its children."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        folder_node = tree.root.children[0]
        
        # Collapse and expand to trigger on_tree_node_expanded
        folder_node.collapse()
        folder_node.expand()
        # Pause to allow the event loop to process the expansion and add children
        await pilot.pause()
        
        assert len(folder_node.children) == 2
        assert "file1.py" in str(folder_node.children[0].label)


@pytest.mark.asyncio
async def test_toggle_file_selection(mock_file_tree):
    """Test selecting a single file updates its visual state via space key."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        tree.root.expand()
        
        # Navigate to root_file.txt
        target_node = tree.root.children[1]
        tree.select_node(target_node)
        
        # Toggle ON
        await pilot.press("space")
        assert "[✓]" in str(target_node.label)
        assert "root/root_file.txt" in app.selected_paths
        
        # Toggle OFF
        await pilot.press("space")
        assert "[ ]" in str(target_node.label)
        assert "root/root_file.txt" not in app.selected_paths


@pytest.mark.asyncio
async def test_recursive_selection(mock_file_tree):
    """Test that toggling a folder selects all descendants."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        folder_ui_node = tree.root.children[0]
        folder_ui_node.expand()
        tree.select_node(folder_ui_node)
        
        # Toggle folder ON
        await pilot.press("space")
        
        assert "[✓]" in str(folder_ui_node.label)
        assert "root/folder/file1.py" in app.selected_paths
        assert "root/folder/file2.py" in app.selected_paths
        
        # Toggle folder OFF
        await pilot.press("space")
        assert "root/folder/file1.py" not in app.selected_paths


@pytest.mark.asyncio
async def test_partial_selection_visuals(mock_file_tree):
    """Test that parent gets '[-]' if only some children are selected."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        folder_ui_node = tree.root.children[0]
        
        folder_ui_node.expand()
        # CRITICAL: Pause to allow children nodes to be created in the UI
        await pilot.pause()
        
        # Select specifically file1.py
        file1_ui_node = folder_ui_node.children[0]
        tree.select_node(file1_ui_node)
        await pilot.press("space")
        
        # Parent folder should be partial [-]
        assert "[-]" in str(folder_ui_node.label)
        
        # Select file2.py
        file2_ui_node = folder_ui_node.children[1]
        tree.select_node(file2_ui_node)
        await pilot.press("space")
        
        # Now parent should be fully checked [✓]
        assert "[✓]" in str(folder_ui_node.label)


@pytest.mark.asyncio
async def test_keyboard_navigation_custom_actions(mock_file_tree):
    """Test custom Left/Right navigation bindings."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        folder_node = tree.root.children[0]
        
        folder_node.collapse()
        tree.select_node(folder_node)
        
        # RIGHT -> Expand
        await pilot.press("right")
        assert folder_node.is_expanded
        
        # RIGHT -> Go to child
        await pilot.press("right")
        assert tree.cursor_node == folder_node.children[0]
        
        # LEFT -> Go to parent
        await pilot.press("left")
        assert tree.cursor_node == folder_node
        
        # LEFT -> Collapse
        await pilot.press("left")
        assert not folder_node.is_expanded


@pytest.mark.asyncio
async def test_highlight_scroll_event(mock_file_tree):
    """Test that highlighting a node triggers scroll logic."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        # Move cursor to trigger on_tree_node_highlighted
        await pilot.press("down")
        assert tree.cursor_node is not None


@pytest.mark.asyncio
async def test_quit_action_key(mock_file_tree):
    """Test 'q' quits the app."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        await pilot.press("q")
        # Textual returns 0 on clean exit
        assert app.return_code == 0 


@pytest.mark.asyncio
async def test_confirm_pruning_logic(mock_file_tree):
    """Test that confirming selection prunes the FileNode tree correctly."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        # Manually select just one deep file
        app.selected_paths.add("root/folder/file1.py")
        
        await pilot.press("enter")
        
        assert not app.is_running
        
        # Check pruning result
        result_nodes = app.selected_nodes
        root = result_nodes[0]
        # 'root_file' should be gone
        assert len(root.children) == 1 
        # 'folder' kept
        folder = root.children[0]
        # 'file2' should be gone
        assert len(folder.children) == 1
        assert folder.children[0].name == "file1.py"


@pytest.mark.asyncio
async def test_confirm_directory_explicit_selection(mock_file_tree):
    """Test pruning when a directory is explicitly selected."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        app.selected_paths.add("root/folder")
        await pilot.press("enter")
        
        root = app.selected_nodes[0]
        folder = root.children[0]
        assert folder.name == "folder"
        # Children were not explicitly selected, so list is empty
        # (Pruning logic includes directory if path is selected OR children exist)
        assert len(folder.children) == 0


@pytest.mark.asyncio
async def test_toggle_safe_guard(mock_file_tree):
    """Ensure toggle doesn't crash if node data is None."""
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        tree.root.add("Ghost Node", data=None)
        tree.select_node(tree.root.children[-1])
        
        await pilot.press("space") 
        assert app.is_running


@pytest.mark.asyncio
async def test_unused_toggle_recursively_method(mock_file_tree):
    """
    Test the `_toggle_recursively` method directly to ensure 100% coverage.
    Note: This method is currently unused by the App (which uses `_set_subtree_selection`), 
    but still exists in the source code.
    """
    app = _PickerApp(mock_file_tree)
    async with app.run_test() as pilot:
        tree = app.query_one(Tree)
        folder_node = tree.root.children[0]
        
        folder_node.expand()
        # CRITICAL: Pause so the UI children are actually created
        await pilot.pause()
        
        # Call the method manually
        app._toggle_recursively(folder_node, select=True)
        
        # Check that it updated the paths
        assert "root/folder/file1.py" in app.selected_paths
        
        # Check that it updated the UI label
        assert "[✓]" in str(folder_node.label)
        
        # Toggle off
        app._toggle_recursively(folder_node, select=False)
        assert "root/folder/file1.py" not in app.selected_paths