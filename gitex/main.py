import click


@click.command()
@click.argument("path", default=".")
def cli(path):
    """Process a repository at PATH and output prompt-ready text."""
    click.echo(f"Processing repository at {path}...")


if __name__ == "__main__":
    cli()
