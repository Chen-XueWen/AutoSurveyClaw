"""Tests for CLI setup helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from surveyclaw import cli


def test_install_opencode_uses_which_resolved_npm_path():
    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch(
        "surveyclaw.cli.shutil.which",
        return_value=r"C:\Program Files\nodejs\npm.cmd",
    ), patch("surveyclaw.cli.subprocess.run", return_value=mock_result) as run_mock:
        assert cli._install_opencode() is True

    run_mock.assert_called_once()
    assert run_mock.call_args.args[0][0] == r"C:\Program Files\nodejs\npm.cmd"


def test_install_opencode_returns_false_when_npm_missing():
    with patch("surveyclaw.cli.shutil.which", return_value=None):
        assert cli._install_opencode() is False


def test_is_opencode_installed_uses_which_resolved_path():
    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch(
        "surveyclaw.cli.shutil.which",
        return_value=r"C:\Users\tester\AppData\Roaming\npm\opencode.cmd",
    ), patch("surveyclaw.cli.subprocess.run", return_value=mock_result) as run_mock:
        assert cli._is_opencode_installed() is True

    run_mock.assert_called_once()
    assert run_mock.call_args.args[0][0].endswith("opencode.cmd")
