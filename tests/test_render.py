import pytest
from unittest.mock import patch, mock_open, MagicMock
from dataclasses import dataclass, field
from typing import List

# We import the code under test. 
# Note: Ensure your project root is in PYTHONPATH or install the package in editable mode.
from gitex.renderer import Renderer, _detect_lang, _is_binary_file, _build_fence

# --- Mocks and Fixtures ---

@dataclass
class MockFileNode:
    """A helper to simulate FileNode objects without needing models.py"""
    name: str
    path: str
    node_type: str  # "file" or "directory"
    children: List['MockFileNode'] = field(default_factory=list)

@pytest.fixture
def sample_tree():
    """
    Creates a sample file tree:
    .
    ├── main.py
    └── utils/
        ├── helper.py
        └── image.png
    """
    node_image = MockFileNode(name="image.png", path="root/utils/image.png", node_type="file")
    node_helper = MockFileNode(name="helper.py", path="root/utils/helper.py", node_type="file")
    node_utils = MockFileNode(name="utils", path="root/utils", node_type="directory", children=[node_helper, node_image])
    node_main = MockFileNode(name="main.py", path="root/main.py", node_type="file")
    
    # Root node usually represents the current dir
    root = MockFileNode(name=".", path="root", node_type="directory", children=[node_main, node_utils])
    return [root]

# --- Tests for Renderer Class ---

def test_render_tree_structure(sample_tree):
    """Test if the ASCII tree is generated correctly."""
    renderer = Renderer(sample_tree)
    tree_output = renderer.render_tree()
    
    expected_snippets = [
        ".",
        "├── main.py",
        "└── utils/",
        "    ├── helper.py",
        "    └── image.png"
    ]
    
    for snippet in expected_snippets:
        assert snippet in tree_output

def test_render_tree_formatting_connectors():
    """Test specifically for the formatting of branches (├── vs └──)."""
    # Create a simple flat list to test last-item logic
    child1 = MockFileNode("a", "path/a", "file")
    child2 = MockFileNode("b", "path/b", "file")
    root = MockFileNode("root", "path", "directory", children=[child1, child2])
    
    renderer = Renderer([root])
    output = renderer.render_tree()
    
    assert "root/" in output
    assert "├── a" in output  # Not last
    assert "└── b" in output  # Last

@patch("builtins.open", new_callable=mock_open, read_data="print('hello world')")
def test_render_files_standard(mock_file, sample_tree):
    """Test rendering of standard text files."""
    renderer = Renderer(sample_tree)
    
    # Render with a base_dir to test relative path stripping
    output = renderer.render_files(base_dir="root/")
    
    # Check if main.py content matches expected format
    assert "# main.py" in output
    assert "```python" in output
    assert "print('hello world')" in output
    
    # Check if paths are relative (stripped of 'root/')
    assert "# utils/helper.py" in output
    assert "# root/main.py" not in output # Should be relative

def test_render_files_skips_binary(sample_tree):
    """Test that binary files (like png) are skipped during file rendering."""
    # We patch open to ensure it fails if it tries to read the PNG, 
    # though the code should skip before opening.
    with patch("builtins.open", mock_open(read_data="binary_data")) as mock_file:
        renderer = Renderer(sample_tree)
        output = renderer.render_files()
        
        # It should contain main.py and helper.py
        assert "main.py" in output
        assert "helper.py" in output
        
        # It should NOT contain the content block for image.png
        assert "image.png" not in output

@patch("gitex.renderer.extract_docstrings")
def test_render_docstrings_all(mock_extract, sample_tree):
    """Test rendering docstrings for all files."""
    mock_extract.return_value = '"""Extracted Docstring"""'
    
    renderer = Renderer(sample_tree)
    output = renderer.render_docstrings()
    
    # Should call extractor for python files
    assert output.count('"""Extracted Docstring"""') == 2 # main.py and helper.py
    assert "# root/main.py" in output

@patch("gitex.renderer.extract_docstrings")
def test_render_docstrings_symbol_targeting(mock_extract, sample_tree):
    """Test targeting a specific symbol maps to the correct file."""
    mock_extract.return_value = '"""Symbol Docstring"""'
    
    renderer = Renderer(sample_tree)
    
    # Target 'root.utils.helper.MyClass'
    # The logic in renderer tries to find a file path ending in:
    # root/utils/helper/MyClass.py (no) -> root/utils/helper.py (yes)
    output = renderer.render_docstrings(symbol_target="root.utils.helper.MyClass")
    
    assert '"""Symbol Docstring"""' in output
    # Should only contain the targeted file, not main.py
    assert "main.py" not in output
    assert "helper.py" in output

def test_render_docstrings_symbol_not_found(sample_tree):
    """Test error message when symbol file cannot be found."""
    renderer = Renderer(sample_tree)
    output = renderer.render_docstrings(symbol_target="non.existent.path")
    assert "Error: Could not find a Python file" in output

def test_read_file_exception_handling():
    """Test that file read errors are caught and formatted."""
    node = MockFileNode("bad.py", "bad.py", "file")
    renderer = Renderer([node])
    
    # Simulate an IOError
    with patch("builtins.open", side_effect=IOError("Permission denied")):
        output = renderer.render_files()
        assert "<Error reading file: Permission denied>" in output

# --- Tests for Helper Functions ---

def test_is_binary_file():
    """Test binary extension detection."""
    assert _is_binary_file("image.png") is True
    assert _is_binary_file("archive.tar.gz") is True
    assert _is_binary_file("script.py") is False
    assert _is_binary_file("README.md") is False

def test_detect_lang():
    """Test language detection from extension and filenames."""
    assert _detect_lang("script.py") == "python"
    assert _detect_lang("style.css") == "css"
    assert _detect_lang("Dockerfile") == "dockerfile"
    assert _detect_lang("dockerfile.prod") == "dockerfile"
    assert _detect_lang("Makefile") == "makefile"
    assert _detect_lang("unknown.xyz") == ""

def test_build_fence_simple():
    """Test basic fence creation."""
    open_fence, close_fence = _build_fence("print('hi')", "python")
    assert open_fence == "```python"
    assert close_fence == "```"

def test_build_fence_escaping():
    """Test that fences expand if the content contains backticks."""
    content = """
    Here is some markdown:
    ```
    code block
    ```
    """
    open_fence, close_fence = _build_fence(content, "markdown")
    
    # Since content has 3 ticks, fence should use 4
    assert open_fence == "````markdown"
    assert close_fence == "````"

def test_build_fence_complex_escaping():
    """Test extreme backtick nesting."""
    content = "Check this out: ````"
    open_fence, close_fence = _build_fence(content, "text")
    
    # Content has 4 ticks, fence needs 5
    assert open_fence == "`````text"
    assert close_fence == "`````"