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
    Create a temporary git repo with:
    - a text file (should appear in File Contents)
    - a binary file (should be skipped in File Contents, but still appear in tree)
    """
    Repo.init(tmp_path)

    # normal text file
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")

    # "binary" file: write non-UTF8 bytes (PNG header)
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    return tmp_path


def run_gitex(runner: CliRunner, repo_dir: Path):
    return runner.invoke(
        cli,
        [str(repo_dir), "-v"],  # Added -v to force output to stdout
        catch_exceptions=False,  # IMPORTANT
    )


def test_binary_file_is_listed_in_tree_but_skipped_in_file_contents(runner, repo_dir):
    result = run_gitex(runner, repo_dir)
    assert result.exit_code == 0

    out = result.stdout

    # Tree should list both files (tree output is plain, no "# " headers)
    assert "hello.txt" in out
    assert "image.png" in out

    # File Contents should include hello.txt block
    assert "\n### File Contents ###\n" in out
    assert "# hello.txt\n" in out
    assert "hello\n" in out

    # Binary should NOT appear in File Contents (your current renderer does `continue`)
    assert "# image.png\n" not in out

    # Extra safety: ensure no placeholder text accidentally exists
    assert re.search(r"binary\s+file\s+skipped", out, flags=re.IGNORECASE) is None


def test_text_file_is_rendered_normally(runner, repo_dir):
    result = run_gitex(runner, repo_dir)
    assert result.exit_code == 0
    assert "# hello.txt\n" in result.stdout
    assert "hello\n" in result.stdout