# tests/test_tree.py
import re
from pathlib import Path
import pytest
from click.testing import CliRunner
from git import Repo
from gitex.main import cli

@pytest.fixture
def runner():
    return CliRunner(mix_stderr=False)

@pytest.fixture
def repo_dir(tmp_path: Path):
    """
    Create a temporary git repo with a nested structure.
    """
    Repo.init(tmp_path)
    
    # Create a nested structure
    autopilot = tmp_path / "autopilot" / "asset"
    autopilot.mkdir(parents=True)
    
    (tmp_path / ".env").write_text("USEGPU=False", encoding="utf-8")
    (tmp_path / "autopilot" / "asset" / "3.jpg").write_text("image_data", encoding="utf-8")
    
    return tmp_path

def test_tree_output_uses_dot_and_triple_quotes(runner, repo_dir):
    """
    Test that the output starts with triple quotes and uses '.' for the root.
    """
    # Added -a to include hidden files like .env
    result = runner.invoke(cli, [str(repo_dir), "--force", "-a"]) 
    assert result.exit_code == 0
    
    out = result.stdout
    
    # Check for triple quote wrapping at the start
    assert out.startswith('"""')
    
    lines = out.splitlines()
    assert lines[1].strip() == "."
    
    # These assertions will now pass because .env is included
    assert "├── .env" in out
    assert "└── autopilot" in out
    

def test_flat_tree_preservation(runner, repo_dir):
    """
    Ensures that even with multiple sub-directories, the tree is minimum and accurate.
    """
    result = runner.invoke(cli, [str(repo_dir), "--force"])
    assert result.exit_code == 0
    
    # The output should NOT just be a flat list of filenames
    # It must contain the ASCII tree connectors
    assert "│" in result.stdout or "├" in result.stdout or "└" in result.stdout