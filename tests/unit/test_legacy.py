# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

"""Characterization tests for the legacy NDI backend, so the ND 4.x refactor
provably leaves ND 2.x/3.x behaviour alone."""

import httpx
import pytest

from nexus_pcv.nd.base import PcvContext
from nexus_pcv.nd.legacy import LegacyNDI

from .helpers import HOST, Handler, json_response, mock_client

pytestmark = pytest.mark.unit

EPOCH_JOB_ID = "EPOCH-DELTA-ANALYSIS-00000000-0000-0000-0000-000000000000"

AGGREGATE_TABLE = {
    "entries": [
        {
            "category": "forwarding",
            "count": 12,
            "anomalyStr": "Some forwarding anomaly",
            "severity": "major",
            "mnemonicTitle": "SOME_FORWARDING_ISSUE",
        },
        {
            "category": "configuration",
            "count": 3,
            "anomalyStr": "An informational note",
            "severity": "info",
            "mnemonicTitle": "SOMETHING_INFORMATIONAL",
        },
        {
            "category": "configuration",
            "count": 4,
            "anomalyStr": "A suppressed anomaly",
            "severity": "warning",
            "mnemonicTitle": "APP_EPG_NOT_DEPLOYED",
        },
        {
            "category": "configuration",
            "count": 0,
            "anomalyStr": "A zero-count anomaly",
            "severity": "major",
            "mnemonicTitle": "ZERO_COUNT",
        },
    ]
}


def make_backend(handler: Handler, timeout: int = 15) -> LegacyNDI:
    backend = LegacyNDI(HOST, "user", "pass", "local", timeout)  # nosec B106
    backend.session = mock_client(handler)
    backend.authenticated = True
    return backend


def test_get_pcv_results_filters_info_suppressed_and_zero_counts() -> None:
    backend = make_backend(lambda request: json_response(AGGREGATE_TABLE))
    ctx = PcvContext(result_id=EPOCH_JOB_ID, fabric_name="FABRIC1")

    err, events = backend.get_pcv_results(
        "default", "FABRIC1", ctx, "APP_EPG_NOT_DEPLOYED"
    )

    assert err is None
    assert events == [
        {
            "Category": "Forwarding",
            "Count": 12,
            "Description": "Some forwarding anomaly",
            "Severity": "major",
        }
    ]


def test_get_pcv_results_queries_the_epoch2_only_view() -> None:
    """epochStatus was never renamed; EPOCH2_ONLY is still correct on legacy"""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return json_response(AGGREGATE_TABLE)

    backend = make_backend(handler)
    backend.get_pcv_results(
        "default", "FABRIC1", PcvContext(result_id=EPOCH_JOB_ID), ""
    )

    assert "epochStatus=EPOCH2_ONLY" in seen[0]
    assert f"/job/{EPOCH_JOB_ID}/health/view/aggregateTable" in seen[0]


def test_wait_pcv_returns_the_epoch_delta_job_id() -> None:
    payload = {
        "value": {
            "data": {
                "analysisStatus": "COMPLETED",
                "epochDeltaJobId": EPOCH_JOB_ID,
            }
        }
    }
    backend = make_backend(lambda request: json_response(payload))

    err, ctx = backend.wait_pcv("default", "FABRIC1", "job-1")

    assert err is None
    assert ctx is not None
    assert ctx.result_id == EPOCH_JOB_ID


def test_wait_pcv_returns_error_on_timeout() -> None:
    """Previously the loop broke out and read the job ID anyway, so a timeout
    could be reported as a successful analysis."""
    payload = {"value": {"data": {"analysisStatus": "RUNNING"}}}
    backend = make_backend(lambda request: json_response(payload), timeout=0)

    err, ctx = backend.wait_pcv("default", "FABRIC1", "job-1")

    assert err is not None
    assert ctx is None


def test_get_pcv_url_keeps_the_appcenter_route() -> None:
    backend = make_backend(lambda request: json_response({}))

    err, url = backend.get_pcv_url("FABRIC1", "job-1")

    assert err is None
    assert url == (
        f"https://{HOST}/appcenter/cisco/nexus-insights/ui/"
        "#/changeManagement/preChangeAnalysis"
    )
