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
    Create a temporary git repo with test files.
    """
    Repo.init(tmp_path)

    def write(relpath: str, content: str):
        p = tmp_path / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    write(
        "Dockerfile",
        "FROM python:3.13-slim\n"
        "WORKDIR /app\n"
        "COPY . /app\n"
        'CMD ["python", "pythonfile.py"]\n',
    )

    write(
        "Makefile",
        ".PHONY: run\n\n"
        "run:\n"
        "\techo running\n",
    )

    write(
        "compose.yml",
        "services:\n"
        "  app:\n"
        "    image: python:3.13-slim\n",
    )

    # Contains nested markdown code fences
    write(
        "file_with_nested_code_block.py",
        "def demo():\n"
        "    s = '''\n"
        "```bash\n"
        "echo hello\n"
        "```\n"
        "'''\n"
        "    return s\n",
    )

    write(
        "main.cpp",
        "#include <iostream>\n"
        'int main(){ std::cout << "hi"; }\n',
    )

    write(
        "main.sh",
        "#!/usr/bin/env bash\n"
        "set -e\n"
        "echo hi\n",
    )

    write("pythonfile.py", "print('hello')\n")
    write("textfile.txt", "plain text\nsecond line\n")

    return tmp_path


def run_gitex(runner: CliRunner, repo_dir: Path):
    return runner.invoke(
        cli,
        [str(repo_dir), "-v"],  # Added -v to force output to stdout
        catch_exceptions=False,  # IMPORTANT
    )


def extract_block(output: str, filename: str) -> str:
    """
    Extract the fenced block for a file:
    starts after '# filename' and ends before next '# ' header.
    """
    pattern = re.compile(
        rf"^#\s+{re.escape(filename)}\s*\n(.*?)(?=^\#\s+|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(output)
    assert match, f"Block for {filename} not found"
    return match.group(1).strip("\n")


def test_all_files_use_triple_backticks_or_more(runner, repo_dir):
    result = run_gitex(runner, repo_dir)
    assert result.exit_code == 0

    files = [
        "Dockerfile",
        "Makefile",
        "compose.yml",
        "file_with_nested_code_block.py",
        "main.cpp",
        "main.sh",
        "pythonfile.py",
        "textfile.txt",
    ]

    for fname in files:
        block = extract_block(result.stdout, fname)
        lines = block.splitlines()

        assert len(lines) >= 2, f"Block too short for {fname}"

        first = lines[0]
        last = lines[-1]

        # Opening fence: at least 3 backticks + optional language
        assert re.match(r"^`{3,}\w*$", first), f"Bad opening fence for {fname}: {first!r}"

        # Closing fence: at least 3 backticks
        assert re.match(r"^`{3,}$", last), f"Bad closing fence for {fname}: {last!r}"

        # Fence lengths must match
        open_len = len(re.match(r"^`+", first).group(0))
        close_len = len(re.match(r"^`+", last).group(0))
        assert open_len == close_len, f"Fence length mismatch in {fname}"


def test_nested_code_block_uses_longer_outer_fence(runner, repo_dir):
    result = run_gitex(runner, repo_dir)
    assert result.exit_code == 0

    block = extract_block(result.stdout, "file_with_nested_code_block.py")
    first = block.splitlines()[0]

    outer_len = len(re.match(r"^`+", first).group(0))
    assert outer_len >= 4, f"Expected >=4 backticks, got {outer_len}"

    # Inner fence must survive intact
    assert "```bash" in block


def test_language_tags_for_known_files(runner, repo_dir):
    result = run_gitex(runner, repo_dir)
    assert result.exit_code == 0

    expected = {
        "Dockerfile": "dockerfile",
        "Makefile": "makefile",
        "compose.yml": "yaml",
        "main.cpp": "cpp",
        "main.sh": "bash",
        "pythonfile.py": "python",
        "textfile.txt": "text",
    }

    for fname, lang in expected.items():
        block = extract_block(result.stdout, fname)
        first = block.splitlines()[0]
        assert first.endswith(lang), f"{fname} expected lang '{lang}', got {first!r}"