# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

"""Regression tests for the reported bug: anomalies existed on ND 4.2 but the
CLI exited 0 and wrote no summary."""

from typing import Any

import pytest
from typer.testing import CliRunner

from nexus_pcv.cli import main as cli_main

pytestmark = pytest.mark.unit

runner = CliRunner()

BASE_ARGS = [
    "-i",
    "nd.example.com",
    "-u",
    "user",
    "-p",
    "pass",
    "-s",
    "FABRIC1",
    "-n",
    "TEST-PCV",
]


class FakePCV:
    """Stands in for PCV so the CLI wiring can be tested without a fabric"""

    result: tuple[Any, Any, Any] = (None, None, None)
    raises: Exception | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def load_json_files(self, filenames: list[str]) -> None:
        pass

    def load_tf_plan(self, filename: str) -> None:
        pass

    def ndi_pcv(self, *args: Any, **kwargs: Any) -> tuple[Any, Any, Any]:
        if FakePCV.raises is not None:
            raise FakePCV.raises
        return FakePCV.result


@pytest.fixture(autouse=True)
def fake_pcv(monkeypatch: pytest.MonkeyPatch) -> type[FakePCV]:
    FakePCV.result = (None, None, None)
    FakePCV.raises = None
    monkeypatch.setattr(cli_main, "PCV", FakePCV)
    return FakePCV


def test_exits_nonzero_when_anomalies_are_raised(fake_pcv: type[FakePCV]) -> None:
    """The reported bug: this used to exit 0"""
    fake_pcv.result = (
        None,
        [{"Category": "Configuration", "Count": 39, "Severity": "major"}],
        "https://nd.example.com/analysis-hub",
    )

    result = runner.invoke(cli_main.app, BASE_ARGS)

    assert result.exit_code == 1


def test_exits_zero_on_a_clean_run(fake_pcv: type[FakePCV]) -> None:
    fake_pcv.result = (None, [], "https://nd.example.com/analysis-hub")

    result = runner.invoke(cli_main.app, BASE_ARGS)

    assert result.exit_code == 0


def test_exits_zero_when_no_changes_are_planned(fake_pcv: type[FakePCV]) -> None:
    fake_pcv.result = (None, None, None)

    result = runner.invoke(cli_main.app, BASE_ARGS)

    assert result.exit_code == 0


def test_exits_nonzero_when_the_backend_reports_an_error(
    fake_pcv: type[FakePCV],
) -> None:
    fake_pcv.result = (object(), None, None)

    result = runner.invoke(cli_main.app, BASE_ARGS)

    assert result.exit_code == 1


def test_exits_nonzero_on_unexpected_exception(fake_pcv: type[FakePCV]) -> None:
    fake_pcv.raises = RuntimeError("Inconsistent results from Nexus Dashboard")

    result = runner.invoke(cli_main.app, BASE_ARGS)

    assert result.exit_code == 1
