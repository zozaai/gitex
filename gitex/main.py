from pathlib import Path
from typing import List

import click

# Default names to skip
DEFAULT_EXCLUDES = {".git", ".gitignore"}


def print_tree(path: Path, prefix: str = "", excludes: List[str] = None):
    """Recursively prints a directory tree for `path`, skipping excluded names."""
    excludes = set(excludes or []) | DEFAULT_EXCLUDES
    entries = sorted(
        (e for e in path.iterdir() if e.name not in excludes),
        key=lambda e: (e.is_file(), e.name.lower()),
    )
    count = len(entries)
    for idx, entry in enumerate(entries, start=1):
        connector = "└── " if idx == count else "├── "
        click.echo(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if idx == count else "│   "
            print_tree(entry, prefix=prefix + extension, excludes=excludes)


@click.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "-e",
    "--exclude",
    multiple=True,
    help="Additional file or directory names to skip (can be repeated).",
)
def cli(path, exclude):
    """
    Prints the folder tree at PATH, ignoring .git and .gitignore by default.
    """
    root = Path(path)
    click.echo(root.resolve().name)
    print_tree(root, excludes=list(exclude))


if __name__ == "__main__":
    cli()
