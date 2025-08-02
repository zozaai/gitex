from pathlib import Path

import click


def print_tree(path: Path, prefix: str = ""):
    """Recursively prints a directory tree for `path`."""
    # List entries, sorting directories first
    entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    count = len(entries)
    for idx, entry in enumerate(entries, start=1):
        connector = "└── " if idx == count else "├── "
        click.echo(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if idx == count else "│   "
            # Recurse into subdirectory
            print_tree(entry, prefix=prefix + extension)


@click.command()
@click.argument("path", type=click.Path(exists=True), default=".")
def cli(path):
    """
    Process a repository at PATH and output prompt-ready text.
    Currently: prints the folder tree at PATH.
    """
    root = Path(path)
    click.echo(root.resolve().name)
    print_tree(root)


if __name__ == "__main__":
    cli()
