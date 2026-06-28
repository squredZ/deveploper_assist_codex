from typer.testing import CliRunner

from hilog_agent.cli import app


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "hilog-agent" in result.stdout
