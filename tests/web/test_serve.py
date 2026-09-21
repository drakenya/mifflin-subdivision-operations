import shutil

from click.testing import CliRunner

from tests.web.conftest import FIXTURES
from waybill_generator.cli import main


def test_serve_starts_uvicorn_on_loopback_only(monkeypatch):
    import uvicorn
    calls = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.update(kwargs))
    result = CliRunner().invoke(main, ["--data-path", str(FIXTURES), "serve", "--port", "9123"])
    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:9123" in result.output
    assert calls == {"host": "127.0.0.1", "port": 9123, "log_level": "warning"}


def test_serve_open_flag_opens_the_browser(monkeypatch):
    import webbrowser

    import uvicorn
    opened = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: None)
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))
    CliRunner().invoke(main, ["--data-path", str(FIXTURES), "serve", "--open"])
    assert opened == ["http://127.0.0.1:8000"]


def test_serve_reports_unreadable_data_and_exits_nonzero(tmp_path):
    bad = tmp_path / "bad"
    shutil.copytree(FIXTURES, bad)
    (bad / "cars.yaml").write_text("- id: a\n  x: [unclosed\n")
    result = CliRunner().invoke(main, ["--data-path", str(bad), "serve"])
    assert result.exit_code != 0
    assert "Cannot load data" in result.output and "cars.yaml" in result.output
