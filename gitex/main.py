# main.py
from fnmatch import fnmatch
from pathlib import Path
import click

from gitex.picker.base import DefaultPicker
from gitex.picker.textuals import TextualPicker
from gitex.renderer import Renderer
from gitex.docstring_extractor import extract_docstrings
from gitex.dependency_mapper import DependencyMapper, format_dependency_analysis
from gitex.utils import copy_to_clipboard

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
@click.option("-i", "--interactive", is_flag=True,
              help="Launch interactive picker to choose files")
@click.option("--no-files", is_flag=True,
              help="Only render the directory tree without file contents.")
@click.option("-c", "--copy", "copy_clipboard", is_flag=True,
              help="Copy the final output to clipboard (Linux: wl-copy/xclip/xsel).")
@click.option("-d", "--base-dir", default=None,
              help="Strip this prefix from file paths when rendering file contents.")
@click.option("-ds", "--extract-docstrings", "extract_symbol",
              help="Extract docstrings for a specific symbol (e.g., gitex.renderer.Renderer) or all files if no symbol is provided.",
              metavar="SYMBOL_PATH", default=None, is_flag=False, flag_value="*")
@click.option("--include-empty-classes", is_flag=True,
              help="Include classes and functions without docstrings when using --extract-docstrings.")
@click.option("--map-dependencies", "dependency_focus",
              help="Analyze and map code dependencies and relationships. Options: 'imports', 'inheritance', 'calls', or omit for all.",
              metavar="FOCUS", default=None, is_flag=False, flag_value="all")
def cli(path, interactive, no_files, copy_clipboard, base_dir, extract_symbol, include_empty_classes, dependency_focus):
    """
    Renders a repository's file tree and optional file contents for LLM prompts.

    You can choose files interactively, respect .gitignore, and exclude patterns.
    
    Features:
    - Extract docstrings and signatures from Python files
    - Map dependencies and relationships between code components
    - Interactive file selection
    - Gitignore-aware filtering
    Renders a repository's file tree and optional file contents for LLM prompts.
    """
    out_parts = []

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

    # Handle dependency mapping (works independently of --no-files)
    if dependency_focus:
        click.echo("\n\n### Dependency & Relationship Map ###\n")
        
        # Get Python files from the selected nodes
        python_files = []
        def collect_python_files(nodes):
            for node in nodes:
                if node.node_type == "file" and node.name.endswith(".py"):
                    python_files.append(node.path)
                if node.children:
                    collect_python_files(node.children)
        
        collect_python_files(nodes)
        
        # Analyze dependencies
        mapper = DependencyMapper(str(root))
        analysis = mapper.analyze(python_files)
        
        # Format and display results
        focus_value = None if dependency_focus == "all" else dependency_focus
        formatted_output = format_dependency_analysis(analysis, focus_value)
        click.echo(formatted_output)
    
    elif not no_files:

        if extract_symbol:
            out_parts.append("\n\n### Extracted Docstrings and Signatures ###\n")
            symbol_target = None if extract_symbol == "*" else extract_symbol
            out_parts.append(renderer.render_docstrings(base_dir or str(root), symbol_target, include_empty_classes))
        else:
            out_parts.append("\n\n### File Contents ###\n")
            out_parts.append(renderer.render_files(base_dir or str(root)))

    final_output = "".join(out_parts)
    click.echo(final_output)

    if copy_clipboard:
        ok = copy_to_clipboard(final_output)
        if ok:
            click.secho("[Copied to clipboard]", err=True)
        else:
            click.secho("[Failed to copy to clipboard — install wl-clipboard or xclip or xsel]", fg="yellow", err=True)


if __name__ == "__main__":
    cli()
