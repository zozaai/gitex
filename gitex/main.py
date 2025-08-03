# main.py
from fnmatch import fnmatch
from pathlib import Path
import click

from gitex.picker.base import DefaultPicker
from gitex.picker.textuals import TextualPicker# <-- updated here
from gitex.renderer import Renderer

# Patterns to exclude from rendering
EXCLUDE_PATTERNS = [".git", ".gitignore", "*.egg-info", "__pycache__"]


def _filter_nodes(nodes):
    """
    Recursively filter out FileNode instances matching EXCLUDE_PATTERNS.
    """
    filtered = []
    for node in nodes:
        if any(fnmatch(node.name, pat) for pat in EXCLUDE_PATTERNS):
            continue
        if node.children:
            node.children = _filter_nodes(node.children)
        filtered.append(node)
    return filtered


@click.command()
@click.argument("path", type=click.Path(exists=True), default='.')
@click.option("--interactive", is_flag=True,
              help="Launch interactive picker to choose files")
@click.option("--no-files", is_flag=True,
              help="Only render the directory tree without file contents.")
@click.option("--base-dir", default=None,
              help="Strip this prefix from file paths when rendering file contents.")
def cli(path, interactive, no_files, base_dir):
    """
    Renders a repository's file tree and optional file contents for LLM prompts.

    You can choose files interactively, respect .gitignore, and exclude patterns.
    """
    root = Path(path).resolve()

    # Choose picker strategy
    if interactive:
        picker = TextualPicker(ignore_hidden=True, respect_gitignore=True)  # <-- updated
    else:
        picker = DefaultPicker(ignore_hidden=True, respect_gitignore=True)

    # Build FileNode hierarchy
    raw_nodes = picker.pick(str(root))

    # Apply exclusion filters
    nodes = _filter_nodes(raw_nodes)

    # Render
    renderer = Renderer(nodes)
    click.echo(renderer.render_tree())

    if not no_files:
        click.echo("\n\n### File Contents ###\n")
        click.echo(renderer.render_files(base_dir or str(root)))


if __name__ == "__main__":
    cli()
