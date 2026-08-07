# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

"""Tests for the orchestration in PCV.ndi_pcv, in particular the summary file
which used to be written only when anomalies existed."""

from pathlib import Path
from typing import Any

import httpx
import pytest

from nexus_pcv import pcv as pcv_module
from nexus_pcv.apic import ApicObject
from nexus_pcv.nd.base import PcvContext

pytestmark = pytest.mark.unit

EVENTS: list[Any] = [
    {
        "Category": "Configuration",
        "Count": 36,
        "Description": "Overlapping external subnets",
        "Severity": "major",
    }
]


class FakeBackend:
    """Stands in for a backend so the orchestration can be tested offline"""

    def __init__(self, events: list[Any] | None = None) -> None:
        self.events: list[Any] = events if events is not None else []
        self.calls: list[str] = []

    def start_pcv(
        self, name: str, group: str, site: str, json_data: str
    ) -> tuple[httpx.Response | None, str | None]:
        self.calls.append("start")
        return None, "job-1"

    def wait_pcv(
        self, group: str, site: str, job_id: str
    ) -> tuple[httpx.Response | None, PcvContext | None]:
        self.calls.append("wait")
        return None, PcvContext(result_id="delta-1", fabric_name=site)

    def get_pcv_results(
        self, group: str, site: str, ctx: PcvContext, suppress_events: str
    ) -> tuple[httpx.Response | None, list[Any] | None]:
        self.calls.append("results")
        return None, self.events

    def get_pcv_url(
        self, site: str, job_id: str, ctx: PcvContext | None = None
    ) -> tuple[httpx.Response | None, str | None]:
        self.calls.append("url")
        return None, "https://nd.example.com/analysis-hub/x"


def build_pcv(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> pcv_module.PCV:
    monkeypatch.setattr(pcv_module, "create_backend", lambda *a, **k: backend)
    return pcv_module.PCV("nd.example.com", "user", "pass", "local", 15)  # nosec B106


def add_change(pcv: pcv_module.PCV) -> None:
    """Give the object tree a child so a validation is actually triggered"""
    pcv.root.children.append(ApicObject("fvTenant", {"dn": "uni/tn-TEST"}, [], None))


def test_summary_is_written_when_anomalies_are_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary = tmp_path / "summary.txt"
    pcv = build_pcv(monkeypatch, FakeBackend(EVENTS))
    add_change(pcv)

    err, events, url = pcv.ndi_pcv("n", "default", "FABRIC1", "", str(summary), "")

    assert err is None
    assert events == EVENTS
    assert "Overlapping external subnets" in summary.read_text()


def test_summary_is_written_on_a_clean_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Previously no file was created, so CI could not tell clean from broken"""
    summary = tmp_path / "summary.txt"
    pcv = build_pcv(monkeypatch, FakeBackend([]))
    add_change(pcv)

    err, events, url = pcv.ndi_pcv("n", "default", "FABRIC1", "", str(summary), "")

    assert err is None
    assert events == []
    assert summary.exists()
    assert "No new anomalies" in summary.read_text()


def test_summary_is_written_when_no_changes_are_planned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary = tmp_path / "summary.txt"
    backend = FakeBackend([])
    pcv = build_pcv(monkeypatch, backend)

    err, events, url = pcv.ndi_pcv("n", "default", "FABRIC1", "", str(summary), "")

    assert (err, events, url) == (None, None, None)
    assert backend.calls == []
    assert "No new anomalies" in summary.read_text()


def test_no_changes_planned_logs_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """INFO was invisible at the default verbosity, so an empty plan looked
    exactly like a clean pass."""
    pcv = build_pcv(monkeypatch, FakeBackend([]))

    with caplog.at_level("WARNING"):
        pcv.ndi_pcv("n", "default", "FABRIC1", "", "", "")

    assert "No updates planned" in caplog.text


def test_url_file_is_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url_file = tmp_path / "url.txt"
    pcv = build_pcv(monkeypatch, FakeBackend([]))
    add_change(pcv)

    pcv.ndi_pcv("n", "default", "FABRIC1", "", "", str(url_file))

    assert url_file.read_text() == "https://nd.example.com/analysis-hub/x"
