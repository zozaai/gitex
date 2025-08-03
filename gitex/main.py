# main.py
from fnmatch import fnmatch
from pathlib import Path
import click
from gitex.picker import DefaultPicker
from gitex.renderer import Renderer

# Patterns to exclude from rendering
EXCLUDE_PATTERNS = [".git", ".gitignore", "*.egg-info", "__pycache__"]

def _filter_nodes(nodes):
    """
    Recursively filter out FileNode instances matching EXCLUDE_PATTERNS.
    """
    filtered = []
    for node in nodes:
        # Skip if name matches any exclude pattern
        if any(fnmatch(node.name, pat) for pat in EXCLUDE_PATTERNS):
            continue
        # If directory, filter its children too
        children = node.children
        if children:
            node.children = _filter_nodes(children)
        filtered.append(node)
    return filtered

@click.command()
@click.argument("path", type=click.Path(exists=True), default='.')
@click.option("--no-files", is_flag=True, help="Only render the directory tree without file contents.")
@click.option("--base-dir", default=None,
              help="Strip this prefix from file paths when rendering file contents.")
def cli(path, no_files, base_dir):
    """
    Prints the folder tree at PATH and optionally file contents, skipping excluded patterns.
    """
    root = Path(path).resolve()

    # Build FileNode hierarchy
    picker = DefaultPicker(ignore_hidden=True, respect_gitignore=True)
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
