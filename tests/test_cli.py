import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from loganalyzer.cli import app


def test_generated_logs_and_resume(tmp_path: Path) -> None:
    generator = Path(__file__).resolve().parents[1] / "scripts" / "generate_logs.py"
    subprocess.run([sys.executable, str(generator), str(tmp_path)], check=True)
    runner = CliRunner()
    db = str(tmp_path / "sample.sqlite3")
    for name in ["auth.log", "access.log"]:
        args = ["ingest", str(tmp_path / name), "--db", db]
        first = runner.invoke(app, args)
        assert first.exit_code == 0, first.output
        assert "Events 60 | malformed 1 | ignored 0" in first.output
        assert "Events 0 | malformed 0" in runner.invoke(app, args).output
    assert "Events 120 | alerts 4" in runner.invoke(app, ["stats", "--db", db]).output
