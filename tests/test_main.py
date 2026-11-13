from __future__ import annotations

import sys
from unittest.mock import MagicMock

import src.main as main_module


def test_main_routes_cli_without_importing_gui(capsys, monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "src.gui.app", raising=False)
    exit_code = main_module.main(["--version"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "py-ico" in captured.out
    assert "src.gui.app" not in sys.modules


def test_main_routes_to_gui_when_no_args(monkeypatch) -> None:
    fake_run_gui = MagicMock(return_value=0)
    fake_gui_app = MagicMock(run_gui=fake_run_gui)
    monkeypatch.setitem(sys.modules, "src.gui.app", fake_gui_app)

    exit_code = main_module.main([])
    assert exit_code == 0
    fake_run_gui.assert_called_once_with()
