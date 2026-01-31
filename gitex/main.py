# main.py
from fnmatch import fnmatch
from pathlib import Path
import click
import git
from git.exc import InvalidGitRepositoryError

from gitex.picker.base import DefaultPicker
from gitex.picker.textuals import TextualPicker
from gitex.renderer import Renderer
from gitex.docstring_extractor import extract_docstrings
from gitex.dependency_mapper import DependencyMapper, format_dependency_analysis
from gitex.utils import copy_to_clipboard

# Patterns to exclude from rendering
EXCLUDE_PATTERNS = [".git", "*.egg-info", "__pycache__"]


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


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument("path", type=click.Path(exists=True), default='.')
@click.version_option(version=None, message="%(prog)s version %(version)s")
@click.option("-i", "--interactive", is_flag=True,
              help="Launch interactive picker to choose files")
@click.option("--no-files", is_flag=True,
              help="Only render the directory tree without file contents.")
@click.option("-v", "--verbose", is_flag=True,
              help="Print output to terminal in addition to copying.")
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
@click.option("-g", "--ignore-gitignore", is_flag=True, help="Include files normally ignored by .gitignore.")
@click.option("-a", "--all", "show_hidden", is_flag=True, help="Include hidden files (files starting with .).")
@click.option("--force", is_flag=True, help="Force execution on non-git directories (caution: may be slow).")


def cli(path, interactive, no_files, verbose, base_dir, extract_symbol, include_empty_classes, dependency_focus, ignore_gitignore, show_hidden, force):
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
    
    # Safety Check: Ensure we are in a git repository to prevent accidental massive scans (like ~)
    # The --force flag allows bypassing this check for intentional non-git directory scanning.
    try:
        git.Repo(str(root), search_parent_directories=True)
    except InvalidGitRepositoryError:
        if not force:
            click.secho(f"⚠️  Skipping: '{root}' is not a valid Git repository.", fg="yellow", err=True)
            click.secho("   gitex defaults to Git repositories to prevent scanning huge directories (like $HOME).", err=True)
            click.secho("   To force scanning this directory anyway, use: gitex --force ...", dim=True, err=True)
            return

    out_parts = []

    # Choose picker strategy
    respect_gitignore = not ignore_gitignore

    # If -a is passed, show_hidden is True, so ignore_hidden should be False
    ignore_hidden = not show_hidden

    if interactive:
        picker = TextualPicker(ignore_hidden=ignore_hidden, respect_gitignore=respect_gitignore)
    else:
        picker = DefaultPicker(ignore_hidden=ignore_hidden, respect_gitignore=respect_gitignore)

    # Build FileNode hierarchy
    raw_nodes = picker.pick(str(root))

    # Apply exclusion filters
    nodes = _filter_nodes(raw_nodes)

    # Always render tree first
    renderer = Renderer(nodes)

    # Wrap the rendered tree in triple quotes
    out_parts.append(f'"""\n{renderer.render_tree()}\n"""')

    # Handle dependency mapping (works independently of --no-files)
    if dependency_focus:
        out_parts.append("\n\n### Dependency & Relationship Map ###\n")
        
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
        out_parts.append(formatted_output)
    
    elif not no_files:
        # Render file contents using the filtered nodes
        if extract_symbol:
            out_parts.append("\n\n### Extracted Docstrings and Signatures ###\n")
            symbol_target = None if extract_symbol == "*" else extract_symbol
            out_parts.append(renderer.render_docstrings(base_dir or str(root), symbol_target, include_empty_classes))
        else:
            out_parts.append("\n\n### File Contents ###\n")
            out_parts.append(renderer.render_files(base_dir or str(root)))

    final_output = "".join(out_parts)

    ok = copy_to_clipboard(final_output)
    if ok:
        click.secho("[Copied to clipboard]", err=True)
        if verbose:
            click.echo(final_output)
    else:
        click.secho("[Failed to copy to clipboard – install wl-clipboard or xclip or xsel]", fg="yellow", err=True)
        click.echo(final_output)

if __name__ == "__main__":
    cli()