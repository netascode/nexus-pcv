# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

from typing import Any

import httpx
import pytest

from nexus_pcv.nd.base import PcvContext
from nexus_pcv.nd.nd4 import ND4

from .helpers import (
    DELTA_JOB_ID,
    DELTA_SUMMARY,
    END_DATE,
    FABRIC,
    GROUPED_NEW,
    HOST,
    JOB_DETAIL,
    JOB_ID,
    START_DATE,
    Handler,
    json_response,
    mock_client,
)

pytestmark = pytest.mark.unit


def make_backend(handler: Handler, timeout: int = 15) -> ND4:
    backend = ND4(HOST, "user", "pass", "local", timeout)  # nosec B106
    backend.session = mock_client(handler)
    backend.authenticated = True
    return backend


def ctx() -> PcvContext:
    return PcvContext(
        result_id=DELTA_JOB_ID,
        fabric_name=FABRIC,
        start_date=START_DATE,
        end_date=END_DATE,
    )


def results_handler(
    grouped: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> Handler:
    """Answer the two calls get_pcv_results makes"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/anomalies/groupedDetails"):
            return json_response(grouped if grouped is not None else GROUPED_NEW)
        if request.url.path.endswith("/deltaAnalysis/summary"):
            return json_response(summary if summary is not None else DELTA_SUMMARY)
        raise AssertionError(f"unexpected request: {request.url}")

    return handler


def test_wait_pcv_accepts_lowercase_status_and_reads_context() -> None:
    """ND 4.x lowercased analysisStatus and misspells the delta job key"""
    backend = make_backend(lambda request: json_response(JOB_DETAIL))

    err, result = backend.wait_pcv("default", FABRIC, JOB_ID)

    assert err is None
    assert result is not None
    assert result.result_id == DELTA_JOB_ID
    assert result.fabric_name == FABRIC
    assert result.start_date == START_DATE
    assert result.end_date == END_DATE


def test_wait_pcv_reports_failed_analysis() -> None:
    payload = dict(JOB_DETAIL, analysisStatus="failed", errorMessage="upload rejected")
    backend = make_backend(lambda request: json_response(payload))

    err, result = backend.wait_pcv("default", FABRIC, JOB_ID)

    assert err is not None
    assert result is None


def test_wait_pcv_returns_error_on_timeout() -> None:
    """A timeout must not fall through and report the job as complete"""
    payload = dict(JOB_DETAIL, analysisStatus="running")
    backend = make_backend(lambda request: json_response(payload), timeout=0)

    err, result = backend.wait_pcv("default", FABRIC, JOB_ID)

    assert err is not None
    assert result is None


def test_get_pcv_results_queries_the_new_anomaly_set() -> None:
    """The delta set must be the new anomalies, not the GUI's unchanged set"""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/anomalies/groupedDetails"):
            seen.update(dict(request.url.params))
            return json_response(GROUPED_NEW)
        return json_response(DELTA_SUMMARY)

    backend = make_backend(handler)
    err, events = backend.get_pcv_results("default", FABRIC, ctx(), "")

    assert err is None
    assert seen["anomalySetParam"] == "raisedAfterStartDate"
    assert seen["fabricName"] == FABRIC
    assert seen["startDate"] == START_DATE
    assert seen["endDate"] == END_DATE
    assert events is not None and len(events) == 4


def test_get_pcv_results_matches_the_verified_lab_numbers() -> None:
    """Ground truth from job PCV-03: 40 new anomalies, 39 major + 1 warning"""
    backend = make_backend(results_handler())

    err, events = backend.get_pcv_results("default", FABRIC, ctx(), "")

    assert err is None
    assert events is not None
    assert sum(e["Count"] for e in events) == 40
    by_severity: dict[str, int] = {}
    for event in events:
        by_severity[event["Severity"]] = by_severity.get(event["Severity"], 0) + int(
            event["Count"]
        )
    assert by_severity == {"major": 39, "warning": 1}
    assert all(e["Category"] == "Configuration" for e in events)


def test_get_pcv_results_falls_back_to_mnemonic_for_description() -> None:
    """anomalyDescription comes back empty on 4.2"""
    backend = make_backend(results_handler())

    _, events = backend.get_pcv_results("default", FABRIC, ctx(), "")

    assert events is not None
    assert events[0]["Description"] == (
        "OVERLAPPING_EXTERNAL_SUBNETS_ACROSS_EXTERNAL_EPGS_IN_VRF"
    )


def test_get_pcv_results_suppresses_requested_mnemonics() -> None:
    grouped = {
        "anomalies": GROUPED_NEW["anomalies"],
        "meta": {"counts": {"remaining": 0, "total": 4}},
    }
    summary = dict(DELTA_SUMMARY, newAnomaliesCount=40)
    backend = make_backend(results_handler(grouped, summary))

    _, events = backend.get_pcv_results(
        "default",
        FABRIC,
        ctx(),
        "BRIDGE_DOMAIN_HAS_INVALID_VRF,APP_EPG_NOT_DEPLOYED",
    )

    assert events is not None
    mnemonics = [e["Description"] for e in events]
    assert "BRIDGE_DOMAIN_HAS_INVALID_VRF" not in mnemonics
    assert len(events) == 3


def test_get_pcv_results_drops_info_severity() -> None:
    grouped = {
        "anomalies": [
            {
                "category": "configuration",
                "count": 5,
                "mnemonicTitle": "SOMETHING_INFORMATIONAL",
                "severity": "info",
                "anomalyDescription": "",
            }
        ],
        "meta": {"counts": {"remaining": 0, "total": 1}},
    }
    summary = dict(DELTA_SUMMARY, newAnomaliesCount=5)
    backend = make_backend(results_handler(grouped, summary))

    err, events = backend.get_pcv_results("default", FABRIC, ctx(), "")

    assert err is None
    assert events == []


def test_get_pcv_results_clean_run_returns_no_events() -> None:
    grouped = {"anomalies": [], "meta": {"counts": {"remaining": 0, "total": 0}}}
    summary = dict(DELTA_SUMMARY, newAnomaliesCount=0)
    backend = make_backend(results_handler(grouped, summary))

    err, events = backend.get_pcv_results("default", FABRIC, ctx(), "")

    assert err is None
    assert events == []


def test_get_pcv_results_raises_when_counts_disagree() -> None:
    """The exact shape of the ND 4.2 bug: empty list, non-zero delta count"""
    grouped = {"anomalies": [], "meta": {"counts": {"remaining": 0, "total": 0}}}
    backend = make_backend(results_handler(grouped, DELTA_SUMMARY))

    with pytest.raises(RuntimeError, match="Inconsistent results"):
        backend.get_pcv_results("default", FABRIC, ctx(), "")


def test_get_pcv_results_follows_pagination() -> None:
    page_one = {
        "anomalies": [
            {
                "category": "configuration",
                "count": 30,
                "mnemonicTitle": "FIRST",
                "severity": "major",
                "anomalyDescription": "",
            }
        ],
        "meta": {"counts": {"remaining": 1, "total": 2}},
    }
    page_two = {
        "anomalies": [
            {
                "category": "configuration",
                "count": 10,
                "mnemonicTitle": "SECOND",
                "severity": "major",
                "anomalyDescription": "",
            }
        ],
        "meta": {"counts": {"remaining": 0, "total": 2}},
    }
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/anomalies/groupedDetails"):
            offset = request.url.params["offset"]
            offsets.append(offset)
            return json_response(page_one if offset == "0" else page_two)
        return json_response(DELTA_SUMMARY)

    backend = make_backend(handler)
    err, events = backend.get_pcv_results("default", FABRIC, ctx(), "")

    assert err is None
    assert offsets == ["0", "1"]
    assert events is not None and len(events) == 2
    assert sum(e["Count"] for e in events) == 40


def test_get_pcv_results_reports_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    backend = make_backend(handler)
    err, events = backend.get_pcv_results("default", FABRIC, ctx(), "")

    assert err is not None
    assert events is None


def test_get_pcv_url_uses_the_analysis_hub_route() -> None:
    """The old appcenter route 404s on ND 4.x"""
    backend = make_backend(lambda request: json_response({}))

    err, url = backend.get_pcv_url(FABRIC, JOB_ID, ctx())

    assert err is None
    assert url == (
        f"https://{HOST}/analysis-hub/pre-change-analysis/view/{FABRIC}/{JOB_ID}"
    )
