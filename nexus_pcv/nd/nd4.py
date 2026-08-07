# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

import json
import logging
import time
from datetime import datetime
from typing import Any

import httpx
import yaml

from .base import NDBackend, PcvContext

logger = logging.getLogger(__name__)

# Page size for the anomaly query. The API caps a response at whatever it
# feels like, so we always follow meta.counts.remaining regardless.
_PAGE_SIZE = 1000

# The delta set holding anomalies introduced by the proposed change. The
# other valid values are fromStartDate, fromEndDate, clearedBeforeEndDate and
# betweenStartDateAndEndDate; the GUI uses the last one, which is the
# *unchanged* set and reports nothing about the change itself.
_NEW_ANOMALIES = "raisedAfterStartDate"


class ND4(NDBackend):
    """Pre-change validation against the native ND 4.x API.

    The legacy epoch delta views still answer on ND 4.2 but return an empty
    set, so results come from ``/api/v1/analyze`` instead. The upload itself
    still goes through the old endpoint, which continues to work and returns
    a job ID the new job API accepts.
    """

    def __init__(
        self,
        hostname_ip: str,
        username: str,
        password: str,
        domain: str,
        timeout: int,
    ):
        super().__init__(hostname_ip, username, password, domain, timeout)
        self.api_url = f"https://{hostname_ip}/api/v1/analyze"
        self.legacy_api_url = (
            f"https://{hostname_ip}/sedgeapi/v1/cisco-nir/api/api/telemetry/v2"
        )

    def start_pcv(
        self, name: str, group: str, site: str, json_data: str
    ) -> tuple[httpx.Response | None, str | None]:
        """Start pre-change validation and return job ID"""
        err = self._ensure_login()
        if err is not None:
            return err, None

        err, base_snapshot_id, fabric_uuid = self._get_last_snapshot(group, site)
        if err is not None:
            return err, None

        payload = {
            "name": name,
            "fabricUuid": fabric_uuid,
            "baseEpochId": str(base_snapshot_id),
            "allowUnsupportedObjectModification": "true",
            "uploadedFileName": "tmp.json",
            "assuranceEntityName": site,
        }
        files = [
            ("data", ("blob", json.dumps(payload), "application/json")),
            ("file", ("tmp.json", json_data, "application/json")),
        ]

        url = f"{self.legacy_api_url}/config/insightsGroup/{group}/fabric/{site}/prechangeAnalysis/fileChanges"
        resp = self.session.post(url, files=files)
        if resp.status_code != 200:
            logger.error(f"Start pre-change analysis failed: {resp.text}")
            return resp, None

        try:
            job_id = json.loads(resp.content)["value"]["data"]["jobId"]
        except (KeyError, ValueError):
            logger.error(f"Job ID could not be found: {resp.text}")
            return resp, None
        logger.info(f"Pre-change analysis started. Job ID: {job_id}")
        return None, str(job_id)

    def _get_last_snapshot(
        self, group: str, site: str
    ) -> tuple[httpx.Response | None, str | None, str | None]:
        """Get the latest finished snapshot to use as the analysis baseline"""
        url = f"{self.legacy_api_url}/events/insightsGroup/{group}/fabric/{site}/epochs?$size=1&$status=FINISHED&$epochType=ONLINE"
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error(f"Get snapshot id failed: {resp.text}")
            return resp, None, None
        try:
            snapshots = json.loads(resp.content)["value"]["data"]
            return None, str(snapshots[0]["epochId"]), str(snapshots[0]["fabricId"])
        except (KeyError, IndexError, ValueError):
            logger.error(f"Snapshot ID could not be found: {resp.text}")
            return resp, None, None

    def wait_pcv(
        self, group: str, site: str, job_id: str
    ) -> tuple[httpx.Response | None, PcvContext | None]:
        """Wait for the analysis to complete and collect the results context"""
        err = self._ensure_login()
        if err is not None:
            return err, None

        url = f"{self.api_url}/jobs/prechangeAnalysis/{job_id}"
        start_time = datetime.now()
        data: dict[str, Any] = {}
        while True:
            resp = self.session.get(url)
            if resp.status_code != 200:
                logger.error(f"Get pre-change analysis status failed: {resp.text}")
                return resp, None
            try:
                data = resp.json()
            except ValueError:
                logger.error(f"Could not parse analysis status: {resp.text}")
                return resp, None

            # ND 4.x lowercased the status that used to be "COMPLETED".
            status = str(data.get("analysisStatus", "")).lower()
            if status == "completed":
                break
            if status in ("failed", "error", "aborted"):
                logger.error(
                    "Pre-change analysis did not succeed "
                    f"(status: {status}): {data.get('errorMessage', '')}"
                )
                return resp, None

            delta_minutes = (datetime.now() - start_time).total_seconds() / 60
            if delta_minutes > self.timeout:
                logger.error(
                    f"Timeout of {self.timeout} minutes reached waiting for the "
                    f"pre-change analysis to complete (last status: {status})."
                )
                return resp, None
            logger.info("Waiting for pre-change analysis to complete ...")
            time.sleep(10)

        # Note: ND's misspelling of "snapshot" - match it exactly.
        delta_job_id = data.get("spanshotDeltaJobId")
        if not delta_job_id:
            logger.error(f"Delta job ID could not be found: {resp.text}")
            return resp, None

        ctx = PcvContext(
            result_id=str(delta_job_id),
            fabric_name=str(data.get("fabricName") or site),
            start_date=str(data.get("baseSnapshotCollectionDate", "")),
            end_date=str(data.get("analysisTime", "")),
        )
        logger.info(f"Pre-change analysis completed. Delta job ID: {ctx.result_id}")
        return None, ctx

    def get_pcv_results(
        self, group: str, site: str, ctx: PcvContext, suppress_events: str
    ) -> tuple[httpx.Response | None, list[Any] | None]:
        """Retrieve the anomalies the proposed change introduces"""
        err = self._ensure_login()
        if err is not None:
            return err, None

        err, anomalies = self._get_new_anomalies(ctx)
        if err is not None:
            return err, None
        assert anomalies is not None  # nosec B101 - guaranteed when err is None

        err, expected = self._get_new_anomaly_count(ctx)
        if err is not None:
            return err, None

        reported = sum(int(a.get("count", 0)) for a in anomalies)
        if expected is not None and reported != expected:
            # This exact mismatch - a well-formed but empty anomaly list next
            # to a non-zero delta count - is what made the tool silently pass
            # on ND 4.2. Never let it read as success again.
            raise RuntimeError(
                f"Inconsistent results from Nexus Dashboard: the delta summary "
                f"reports {expected} new anomalies but the anomaly query "
                f"returned {reported}. Refusing to report a possibly clean run."
            )

        event_list = []
        for anomaly in anomalies:
            if int(anomaly.get("count", 0)) <= 0:
                continue
            if self._suppressed(
                anomaly.get("severity"), anomaly.get("mnemonicTitle"), suppress_events
            ):
                continue
            event_list.append(
                {
                    "Category": str(anomaly.get("category", "")).title(),
                    "Count": anomaly.get("count"),
                    # anomalyDescription is populated on this query but comes
                    # back empty on some others, so keep the mnemonic as a
                    # fallback rather than emitting a blank description.
                    "Description": anomaly.get("anomalyDescription")
                    or anomaly.get("mnemonicTitle"),
                    "Severity": anomaly.get("severity"),
                }
            )
        if event_list:
            logger.error(
                f"The following anomalies have been raised:\n{yaml.dump(event_list)}"
            )
        return None, event_list

    def _get_new_anomalies(
        self, ctx: PcvContext
    ) -> tuple[httpx.Response | None, list[dict[str, Any]] | None]:
        """Page through the anomalies raised between the two snapshots"""
        url = f"{self.api_url}/anomalies/groupedDetails"
        anomalies: list[dict[str, Any]] = []
        offset = 0
        while True:
            params = {
                "fabricName": ctx.fabric_name,
                "startDate": ctx.start_date,
                "endDate": ctx.end_date,
                "analysisDate": ctx.end_date,
                "groupBy": "mnemonicTitle",
                "preChangeAnalysis": "true",
                "anomalySetParam": _NEW_ANOMALIES,
                "includeSystemAnomalies": "false",
                "fabricStatus": "online",
                "max": str(_PAGE_SIZE),
                "offset": str(offset),
            }
            resp = self.session.get(url, params=params)
            if resp.status_code != 200:
                logger.error(f"Get PCV results failed: {resp.text}")
                return resp, None
            try:
                data = resp.json()
                page = data.get("anomalies") or []
                remaining = int(data["meta"]["counts"]["remaining"])
            except (KeyError, ValueError, TypeError):
                logger.error(f"Could not find anomalies: {resp.text}")
                return resp, None

            anomalies.extend(page)
            if remaining <= 0 or not page:
                break
            offset += len(page)
        return None, anomalies

    def _get_new_anomaly_count(
        self, ctx: PcvContext
    ) -> tuple[httpx.Response | None, int | None]:
        """Authoritative count of new anomalies, used to cross-check the query"""
        url = f"{self.api_url}/deltaAnalysis/summary"
        params = {"jobId": ctx.result_id, "includeAcknowledged": "false"}
        resp = self.session.get(url, params=params)
        if resp.status_code != 200:
            logger.error(f"Get delta analysis summary failed: {resp.text}")
            return resp, None
        try:
            return None, int(resp.json()["newAnomaliesCount"])
        except (KeyError, ValueError, TypeError):
            logger.error(f"Could not find new anomaly count: {resp.text}")
            return resp, None

    def get_pcv_url(
        self, site: str, job_id: str, ctx: PcvContext | None = None
    ) -> tuple[httpx.Response | None, str | None]:
        """Get URL pointing to pre-change validation results"""
        fabric = ctx.fabric_name if ctx is not None and ctx.fabric_name else site
        url = (
            f"https://{self.hostname_ip}/analysis-hub/pre-change-analysis"
            f"/view/{fabric}/{job_id}"
        )
        return None, url
