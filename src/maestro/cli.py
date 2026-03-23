"""Maestro CLI entry point."""

import click


@click.group()
def main() -> None:
    """Maestro - task orchestration daemon."""


if __name__ == "__main__":
    main()
