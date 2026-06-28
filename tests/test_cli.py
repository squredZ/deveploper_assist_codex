from typer.testing import CliRunner

from hilog_agent.cli import app


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "hilog-agent" in result.stdout


def test_ask_command_requires_question():
    runner = CliRunner()
    result = runner.invoke(app, ["ask"])
    assert result.exit_code != 0


def test_analyze_log_command_exists():
    runner = CliRunner()
    result = runner.invoke(app, ["analyze-log", "--help"])
    assert result.exit_code == 0
    assert "--log" in result.stdout


def test_add_module_command_exists():
    runner = CliRunner()
    result = runner.invoke(app, ["add-module", "--help"])
    assert result.exit_code == 0
    assert "--module" in result.stdout
    assert "--force" in result.stdout
