from fnmatch import fnmatch
from pathlib import Path

import click

EXCLUDE_PATTERNS = [".git", ".gitignore", "*.egg-info", "__pycache__"]


def print_tree(path: Path, prefix: str = ""):
    entries = sorted(
        (
            e
            for e in path.iterdir()
            if not any(fnmatch(e.name, pat) for pat in EXCLUDE_PATTERNS)
        ),
        key=lambda e: (e.is_file(), e.name.lower()),
    )
    count = len(entries)
    for idx, entry in enumerate(entries, 1):
        connector = "└── " if idx == count else "├── "
        click.echo(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if idx == count else "│   "
            print_tree(entry, prefix + extension)


@click.command()
@click.argument("path", type=click.Path(exists=True), default=".")
def cli(path):
    """
    Prints the folder tree at PATH, skipping .git, .gitignore, and *.egg-info.
    """
    root = Path(path)
    click.echo(root.resolve().name)
    print_tree(root)


if __name__ == "__main__":
    cli()
