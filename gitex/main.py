# main.py
from fnmatch import fnmatch
from pathlib import Path
import click

from gitex.picker.base import DefaultPicker
from gitex.picker.textuals import TextualPicker# <-- updated here
from gitex.renderer import Renderer
from gitex.docstring_extractor import extract_docstrings
from gitex.dependency_mapper import DependencyMapper, format_dependency_analysis

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
@click.option("--extract-docstrings", "extract_symbol",
              help="Extract docstrings for a specific symbol (e.g., gitex.renderer.Renderer) or all files if no symbol is provided.",
              metavar="SYMBOL_PATH", default=None, is_flag=False, flag_value="*")
@click.option("--include-empty-classes", is_flag=True,
              help="Include classes and functions without docstrings when using --extract-docstrings.")
@click.option("--map-dependencies", "dependency_focus",
              help="Analyze and map code dependencies and relationships. Options: 'imports', 'inheritance', 'calls', or omit for all.",
              metavar="FOCUS", default=None, is_flag=False, flag_value="all")
def cli(path, interactive, no_files, base_dir, extract_symbol, include_empty_classes, dependency_focus):
    """
    Renders a repository's file tree and optional file contents for LLM prompts.

    You can choose files interactively, respect .gitignore, and exclude patterns.
    
    Features:
    - Extract docstrings and signatures from Python files
    - Map dependencies and relationships between code components
    - Interactive file selection
    - Gitignore-aware filtering
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
            click.echo("\n\n### Extracted Docstrings and Signatures ###\n")
            symbol_target = None if extract_symbol == "*" else extract_symbol
            click.echo(renderer.render_docstrings(base_dir or str(root), symbol_target, include_empty_classes))
        else:
            click.echo("\n\n### File Contents ###\n")
            click.echo(renderer.render_files(base_dir or str(root)))


if __name__ == "__main__":
    cli()
