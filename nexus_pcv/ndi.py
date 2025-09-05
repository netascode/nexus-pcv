# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import json
import logging
import time
from datetime import datetime
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)


class NDI:
    def __init__(
        self,
        hostname_ip: str,
        username: str,
        password: str,
        domain: str,
        timeout: int,
    ):
        self.hostname_ip = hostname_ip
        self.api_url = (
            f"https://{hostname_ip}/sedgeapi/v1/cisco-nir/api/api/telemetry/v2"
        )
        self.username = username
        self.password = password
        self.domain = domain
        self.timeout = timeout
        self.session = httpx.Client(verify=False)  # nosec B501
        # SSL verification disabled in Client() constructor
        self.authenticated = False
        self.site_uuid = ""

    def _login(self) -> httpx.Response | None:
        """Helper function to authenticate and populate headers"""
        auth_payload = {
            "userName": self.username,
            "userPasswd": self.password,
            "domain": self.domain,
        }
        url = f"https://{self.hostname_ip}/login"
        resp = self.session.post(url, json=auth_payload)
        if resp.status_code != 200:
            logger.error(f"Login failed: {resp.json()}")
            return resp
        self.authenticated = True
        return None

    def get_last_epoch_id(
        self, name: str, site: str
    ) -> tuple[httpx.Response | None, str | None]:
        """Get last epoch ID of assurance group"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        url = f"{self.api_url}/events/insightsGroup/{name}/fabric/{site}/epochs?$size=1&$status=FINISHED&$epochType=ONLINE"
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error(f"Get epoch id failed: {resp.json()}")
            return resp, None

        try:
            epochs = json.loads(resp.content)["value"]["data"]
            epoch_id = epochs[0]["epochId"]
            self.site_uuid = epochs[0]["fabricId"]
            return None, epoch_id
        except KeyError:
            pass
        logger.error(f"Epoch ID could not be found: {resp.json()}")
        return resp, None

    def start_pcv(
        self, name: str, group: str, site: str, json_data: str
    ) -> tuple[httpx.Response | None, str | None]:
        """Start pre-change validation and return job ID"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        err, epoch_id = self.get_last_epoch_id(group, site)
        if err is not None:
            return err, None

        payload = {}
        payload["name"] = name
        payload["fabricUuid"] = self.site_uuid
        payload["baseEpochId"] = str(epoch_id)
        payload["allowUnsupportedObjectModification"] = "true"
        payload["uploadedFileName"] = "tmp.json"
        payload["assuranceEntityName"] = site

        files = [
            ("data", ("blob", json.dumps(payload), "application/json")),
            ("file", ("tmp.json", json_data, "application/json")),
        ]

        url = f"{self.api_url}/config/insightsGroup/{group}/fabric/{site}/prechangeAnalysis/fileChanges"
        resp = self.session.post(url, files=files)
        if resp.status_code != 200:
            logger.error(f"Start pre-change analysis failed: {resp.json()}")
            return resp, None

        try:
            job_id = json.loads(resp.content)["value"]["data"]["jobId"]
            logger.info(f"Pre-change analysis started. Job ID: {job_id}")
            return None, job_id
        except KeyError:
            pass
        logger.error(f"Job ID could not be found: {resp.json()}")
        return resp, None

    def wait_pcv(
        self, group: str, site: str, job_id: str
    ) -> tuple[httpx.Response | None, str | None]:
        """Wair for pre-change validation to complete and return epoch job ID"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        status = None
        start_time = datetime.now()
        while True:
            url = f"{self.api_url}/config/insightsGroup/{group}/fabric/{site}/prechangeAnalysis/{job_id}"
            resp = self.session.get(url)
            if resp.status_code != 200:
                logger.error(f"Get pre-change analysis status failed: {resp.json()}")
                return resp, None
            try:
                status = json.loads(resp.content)["value"]["data"]["analysisStatus"]
                if status == "COMPLETED":
                    break
            except KeyError:
                logger.error(f"Status could not be found: {resp.json()}")
            delta_minutes = (datetime.now() - start_time).total_seconds() / 60
            if delta_minutes > self.timeout:
                break
            logger.info("Waiting for pre-change analysis to complete ...")
            time.sleep(10)

        try:
            epoch_job_id = json.loads(resp.content)["value"]["data"]["epochDeltaJobId"]
            logger.info(f"Pre-change analysis completed. Epoch job ID: {epoch_job_id}")
            return None, epoch_job_id
        except KeyError:
            pass
        logger.error(f"Epoch job ID could not be found: {resp.json()}")
        return resp, None

    def get_pcv_results(
        self, group: str, site: str, epoch_job_id: str, suppress_events: str
    ) -> tuple[httpx.Response | None, list[Any] | None]:
        """Retrieve pre-change validation results"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        suppress_events_list = suppress_events.split(",")

        url = f"{self.api_url}/epochDelta/insightsGroup/{group}/fabric/{site}/job/{epoch_job_id}/health/view/aggregateTable?epochStatus=EPOCH2_ONLY"
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error(f"Get PCV results failed: {resp.json()}")
            return resp, None

        event_list = []
        try:
            for event in json.loads(resp.content)["entries"]:
                if int(event["count"]) > 0:
                    if (
                        str(event.get("severity")) == "info"
                        or str(event.get("mnemonicTitle")) in suppress_events_list
                    ):
                        continue
                    event_list.append(
                        {
                            "Category": event.get("category").title(),
                            "Count": event.get("count"),
                            "Description": event.get("anomalyStr"),
                            "Severity": event.get("severity"),
                        }
                    )
        except KeyError:
            logger.error(f"Could not find events: {resp.json()}")
            return resp, None
        if event_list:
            logger.error(
                f"The following anomalies have been raised:\n{yaml.dump(event_list)}"
            )
        return None, event_list

    def get_pcv_url(self) -> tuple[httpx.Response | None, str | None]:
        """Get URL pointing to pre-change validation results"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        url = f"https://{self.hostname_ip}/appcenter/cisco/nexus-insights/ui/#/changeManagement/preChangeAnalysis"

        return None, url
