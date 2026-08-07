# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

"""Shared helpers and scrubbed ND 4.2 payloads for the backend tests.

The payloads mirror what the lab returned for a real pre-change analysis,
with hostnames, fabric names and tenant names replaced.
"""

from collections.abc import Callable

import httpx

# A request handler suitable for httpx.MockTransport
Handler = Callable[[httpx.Request], httpx.Response]

FABRIC = "FABRIC1"
HOST = "nd.example.com"
JOB_ID = "aaaabbbbccccddddeeeeffff"
DELTA_JOB_ID = "EPOCH-DELTA-ANALYSIS-00000000-0000-0000-0000-000000000000"
START_DATE = "2026-08-06T05:29:33Z"
END_DATE = "2026-08-06T07:31:36.000Z"

# GET /api/v1/analyze/jobs/prechangeAnalysis/{jobId}
JOB_DETAIL = {
    "analysisStatus": "completed",
    "analysisTime": END_DATE,
    "baseSnapshotCollectionDate": START_DATE,
    "baseSnapshotId": "0e5604f9-00000000-0000-0000-0000-000000000000",
    "errorMessage": "",
    "fabricName": FABRIC,
    "jobId": JOB_ID,
    "name": "TEST-PCV",
    # Misspelling of "snapshot" from the ND API, preserved here for testing
    "spanshotDeltaJobId": DELTA_JOB_ID,
}

# GET /api/v1/analyze/deltaAnalysis/summary
DELTA_SUMMARY = {
    "anomalyCountBySeverity": [
        {"severity": "critical", "newCount": 0, "unchangedCount": 9},
        {"severity": "major", "newCount": 39, "unchangedCount": 24},
        {"severity": "warning", "newCount": 1, "unchangedCount": 23},
    ],
    "newAnomaliesCount": 40,
    "unchangedAnomaliesCount": 56,
    "clearedAnomaliesCount": 183,
}

# GET /api/v1/analyze/anomalies/groupedDetails?...&anomalySetParam=raisedAfterStartDate
GROUPED_NEW = {
    "anomalies": [
        {
            "anomalyDescription": "",
            "category": "configuration",
            "count": 36,
            "mnemonicTitle": "OVERLAPPING_EXTERNAL_SUBNETS_ACROSS_EXTERNAL_EPGS_IN_VRF",
            "severity": "major",
        },
        {
            "anomalyDescription": "",
            "category": "configuration",
            "count": 2,
            "mnemonicTitle": "OVERLAPPING_SUBNETS_ACROSS_STATIC_ROUTES_AND_BD_IN_VRF",
            "severity": "major",
        },
        {
            "anomalyDescription": "",
            "category": "configuration",
            "count": 1,
            "mnemonicTitle": (
                "OVERLAPPING_SUBNETS_ACROSS_STATIC_ROUTES_AND_EXTERNAL_INTERFACES_IN_VRF"
            ),
            "severity": "major",
        },
        {
            "anomalyDescription": "",
            "category": "configuration",
            "count": 1,
            "mnemonicTitle": "BRIDGE_DOMAIN_HAS_INVALID_VRF",
            "severity": "warning",
        },
    ],
    "meta": {"counts": {"remaining": 0, "total": 4}},
}


def mock_client(handler: Handler) -> httpx.Client:
    """An httpx client that answers from ``handler`` instead of the network"""
    return httpx.Client(transport=httpx.MockTransport(handler))


def json_response(payload: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload)
