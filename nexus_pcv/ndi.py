# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

from datetime import datetime
import json
import logging
import time
from typing import Any, List, Optional, Tuple

import requests
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
        self.api_url = "https://{}/sedgeapi/v1/cisco-nir/api/api/telemetry/v2".format(
            hostname_ip
        )
        self.username = username
        self.password = password
        if domain == "Local":
            self.domain = "local"
        else:
            self.domain = domain
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = False
        self.authenticated = False
        self.site_uuid = ""

    def _login(self) -> Optional[requests.Response]:
        """Helper function to authenticate and populate headers"""
        auth_payload = {
            "userName": self.username,
            "userPasswd": self.password,
            "domain": self.domain,
        }
        url = "https://{}/login".format(self.hostname_ip)
        resp = self.session.post(url, json=auth_payload)
        if resp.status_code != 200:
            logger.error("Login failed: {}".format(resp.json()))
            return resp
        self.authenticated = True
        return None

    def get_last_epoch_id(
        self, name: str, site: str
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Get last epoch ID of assurance group"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        url = "{}/events/insightsGroup/{}/fabric/{}/epochs?$size=1&$status=FINISHED&$epochType=ONLINE".format(
            self.api_url, name, site
        )
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error("Get epoch id failed: {}".format(resp.json()))
            return resp, None

        try:
            epochs = json.loads(resp.content)["value"]["data"]
            epoch_id = epochs[0]["epochId"]
            self.site_uuid = epochs[0]["fabricId"]
            return None, epoch_id
        except KeyError:
            pass
        logger.error("Epoch ID could not be found: {}".format(resp.json()))
        return resp, None

    def start_pcv(
        self, name: str, group: str, site: str, json_data: str
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
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

        url = (
            "{}/config/insightsGroup/{}/fabric/{}/prechangeAnalysis/fileChanges".format(
                self.api_url, group, site
            )
        )
        resp = self.session.post(url, files=files)
        if resp.status_code != 200:
            logger.error("Start pre-change analysis failed: {}".format(resp.json()))
            return resp, None

        try:
            job_id = json.loads(resp.content)["value"]["data"]["jobId"]
            logger.info("Pre-change analysis started. Job ID: {}".format(job_id))
            return None, job_id
        except KeyError:
            pass
        logger.error("Job ID could not be found: {}".format(resp.json()))
        return resp, None

    def wait_pcv(
        self, group: str, site: str, job_id: str
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Wair for pre-change validation to complete and return epoch job ID"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        status = None
        start_time = datetime.now()
        while True:
            url = "{}/config/insightsGroup/{}/fabric/{}/prechangeAnalysis/{}".format(
                self.api_url, group, site, job_id
            )
            resp = self.session.get(url)
            if resp.status_code != 200:
                logger.error(
                    "Get pre-change analysis status failed: {}".format(resp.json())
                )
                return resp, None
            try:
                status = json.loads(resp.content)["value"]["data"]["analysisStatus"]
                if status == "COMPLETED":
                    break
            except KeyError:
                logger.error("Status could not be found: {}".format(resp.json()))
            delta_minutes = (datetime.now() - start_time).total_seconds() / 60
            if delta_minutes > self.timeout:
                break
            logger.info("Waiting for pre-change analysis to complete ...")
            time.sleep(10)

        try:
            epoch_job_id = json.loads(resp.content)["value"]["data"]["epochDeltaJobId"]
            logger.info(
                "Pre-change analysis completed. Epoch job ID: {}".format(epoch_job_id)
            )
            return None, epoch_job_id
        except KeyError:
            pass
        logger.error("Epoch job ID could not be found: {}".format(resp.json()))
        return resp, None

    def get_pcv_results(
        self, group: str, site: str, epoch_job_id: str, suppress_events: str
    ) -> Tuple[Optional[requests.Response], Optional[List[Any]]]:
        """Retrieve pre-change validation results"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        suppress_events_list = suppress_events.split(",")

        url = "{}/epochDelta/insightsGroup/{}/fabric/{}/job/{}/health/view/aggregateTable?epochStatus=EPOCH2_ONLY".format(
            self.api_url, group, site, epoch_job_id
        )
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error("Get PCV results failed: {}".format(resp.json()))
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
            logger.error("Could not find events: {}".format(resp.json()))
            return resp, None
        if event_list:
            logger.error(
                "The following anomalies have been raised:\n{}".format(
                    yaml.dump(event_list)
                )
            )
        return None, event_list

    def get_pcv_url(self) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Get URL pointing to pre-change validation results"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        url = "https://{}/appcenter/cisco/nexus-insights/ui/#/changeManagement/preChangeAnalysis".format(
            self.hostname_ip
        )

        return None, url
