from pathlib import Path

import typer

from hilog_agent import __version__
from hilog_agent.analyze import analyze_log_summary, ask_feature

app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"hilog-agent {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    return None


@app.command("ask")
def ask(
    question: str = typer.Option(..., "--question"),
    feature: str = typer.Option(..., "--feature"),
    features_dir: Path = typer.Option(Path("features"), "--features-dir"),
) -> None:
    typer.echo(ask_feature(features_dir, feature, question))


@app.command("analyze-log")
def analyze_log(
    log: Path = typer.Option(..., "--log"),
) -> None:
    typer.echo(analyze_log_summary(log))


@app.command("add-module")
def add_module(
    feature: str = typer.Option(..., "--feature"),
    module: str = typer.Option(..., "--module"),
    path: str = typer.Option(..., "--path"),
    force: bool = typer.Option(False, "--force"),
    backup: bool = typer.Option(False, "--backup"),
) -> None:
    typer.echo(
        f"add-module requested for feature={feature}, module={module}, path={path}, "
        f"force={force}, backup={backup}"
    )


def main() -> None:
    app()
