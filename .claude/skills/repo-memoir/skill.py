from __future__ import annotations

from pathlib import Path

import typer

from repomemoir.cli import generate, update


app = typer.Typer(help="OpenClaw wrapper for repo-memoir")


@app.command()
def run(repo: str) -> None:
    sidecar = Path("memoirs") / f"{repo.replace('/', '_')}.memoir.json"
    if sidecar.exists():
        update(repo=repo)
    else:
        generate(repo=repo)


if __name__ == "__main__":
    app()
