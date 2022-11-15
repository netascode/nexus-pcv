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


class NAE:
    def __init__(
        self,
        hostname_ip: str,
        username: str,
        password: str,
        domain: str,
        timeout: int,
    ):
        self.hostname_ip = hostname_ip
        self.api_url = "https://{}/nae/api/v1".format(hostname_ip)
        self.username = username
        self.password = password
        self.domain = domain
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = False
        self.authenticated = False
        self.assurance_group_uuid = ""

    def _login(self) -> Optional[requests.Response]:
        """Helper function to authenticate and populate headers"""
        url = "{}/whoami".format(self.api_url)
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error("Whoami failed: {}".format(resp.json()))
            return resp
        if "X-NAE-LOGIN-OTP" not in resp.headers:
            logger.error(
                "X-NAE-LOGIN-OTP header missing in whoami response: {}".format(
                    resp.json()
                )
            )
            return resp

        headers = {}
        headers["X-NAE-LOGIN-OTP"] = resp.headers.get("X-NAE-LOGIN-OTP")
        headers["Cookie"] = resp.headers.get("Set-Cookie")
        auth_payload = {
            "username": self.username,
            "password": self.password,
            "domain": self.domain,
        }
        url = "{}/login".format(self.api_url)
        resp = self.session.post(url, headers=headers, json=auth_payload)
        if resp.status_code != 200:
            logger.error("Login failed: {}".format(resp.json()))
            return resp
        if "X-NAE-CSRF-TOKEN" not in resp.headers:
            logger.error(
                "X-NAE-CSRF-TOKEN header missing in login response: {}".format(
                    resp.json()
                )
            )
            return resp

        self.session.headers["X-NAE-CSRF-TOKEN"] = str(
            resp.headers.get("X-NAE-CSRF-TOKEN")
        )
        self.session.headers["Cookie"] = str(resp.headers.get("Set-Cookie"))
        self.authenticated = True
        return None

    def get_assurance_group_uuid(
        self, name: str
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Get assurance group ID by its name"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        url = "{}/config-services/assured-networks/aci-fabric/".format(self.api_url)
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error("Get assurance group failed: {}".format(resp.json()))
            return resp, None

        try:
            ags = json.loads(resp.content)["value"]["data"]
            for ag in ags:
                if ag["unique_name"] == name:
                    self.assurance_group_uuid = ag.get("uuid")
                    return None, ag.get("uuid")
        except KeyError:
            pass
        logger.error("UUID could not be found: {}".format(resp.json()))
        return resp, None

    def get_last_epoch_id(
        self, name: str
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Get last epoch ID of assurance group"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        err, uuid = self.get_assurance_group_uuid(name)
        if err is not None:
            return err, None

        url = "{}/event-services/assured-networks/{}/epochs?$sort=-collectionTimestamp".format(
            self.api_url, uuid
        )
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error("Get epoch id failed: {}".format(resp.json()))
            return resp, None

        try:
            epochs = json.loads(resp.content)["value"]["data"]
            epoch_id = epochs[0]["epoch_id"]
            return None, epoch_id
        except KeyError:
            pass
        logger.error("Epoch ID could not be found: {}".format(resp.json()))
        return resp, None

    def start_pcv(
        self, name: str, ag_name: str, json_data: str
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Start pre-change validation and return job ID"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        err, epoch_id = self.get_last_epoch_id(ag_name)
        if err is not None:
            return err, None

        payload = {}
        payload["name"] = name
        payload["fabric_uuid"] = self.assurance_group_uuid
        payload["base_epoch_id"] = str(epoch_id)
        payload["stop_analysis"] = str(True)
        payload["allow_unsupported_object_modification"] = "true"
        payload["uploaded_file_name"] = "tmp.json"

        files = [
            ("data", ("blob", json.dumps(payload), "application/json")),
            ("file", ("tmp.json", json_data, "application/json")),
        ]

        url = "{}/config-services/prechange-analysis/file-changes".format(self.api_url)
        resp = self.session.post(url, files=files)
        if resp.status_code != 200:
            logger.error("Start pre-change analysis failed: {}".format(resp.json()))
            return resp, None

        try:
            job_id = json.loads(resp.content)["value"]["data"]["job_id"]
            logger.info("Pre-change analysis started. Job ID: {}".format(job_id))
            return None, job_id
        except KeyError:
            pass
        logger.error("Job ID could not be found: {}".format(resp.json()))
        return resp, None

    def wait_pcv(
        self, job_id: str
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Wair for pre-change validation to complete and return epoch job ID"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        status = None
        start_time = datetime.now()
        while True:
            url = "{}/config-services/prechange-analysis/{}".format(
                self.api_url, job_id
            )
            resp = self.session.get(url)
            if resp.status_code != 200:
                logger.error(
                    "Get pre-change analysis status failed: {}".format(resp.json())
                )
                return resp, None
            try:
                status = json.loads(resp.content)["value"]["data"]["analysis_status"]
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
            epoch_job_id = json.loads(resp.content)["value"]["data"][
                "epoch_delta_job_id"
            ]
            logger.info(
                "Pre-change analysis completed. Epoch job ID: {}".format(epoch_job_id)
            )
            return None, epoch_job_id
        except KeyError:
            pass
        logger.error("Epoch job ID could not be found: {}".format(resp.json()))
        return resp, None

    def get_pcv_results(
        self, epoch_job_id: str, suppress_events: str
    ) -> Tuple[Optional[requests.Response], Optional[List[Any]]]:
        """Retrieve pre-change validation results"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        suppress_events_list = suppress_events.split(",")

        url = "{}/epoch-delta-services/assured-networks/{}/job/{}/health/view/aggregate-table?category=ADC,CHANGE_ANALYSIS,TENANT_ENDPOINT,TENANT_FORWARDING,TENANT_SECURITY,RESOURCE_UTILIZATION,SYSTEM,COMPLIANCE&epoch_status=EPOCH2_ONLY&severity=EVENT_SEVERITY_CRITICAL,EVENT_SEVERITY_MAJOR,EVENT_SEVERITY_MINOR,EVENT_SEVERITY_WARNING,EVENT_SEVERITY_INFO".format(
            self.api_url, self.assurance_group_uuid, epoch_job_id
        )
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error("Get PCV results failed: {}".format(resp.json()))
            return resp, None

        event_list = []
        try:
            for event in json.loads(resp.content)["value"]["data"]:
                if int(event["count"]) > 0:
                    if (
                        str(event["epoch2_details"]["severity"])
                        == "EVENT_SEVERITY_INFO"
                        or str(event["epoch2_details"]["mnemonic"])
                        in suppress_events_list
                    ):
                        continue
                    event_list.append(
                        {
                            "Category": event["category"].title(),
                            "Count": event["count"],
                            "Description": event["epoch2_details"]["description"],
                            "Severity": event["epoch2_details"]["severity"][
                                15:
                            ].title(),
                        }
                    )
        except KeyError:
            logger.error("Could not find events: {}".format(resp.json()))
            return resp, None
        if event_list:
            logger.error(
                "The following events have been raised:\n{}".format(
                    yaml.dump(event_list)
                )
            )
        return None, event_list

    def get_pcv_url(
        self, job_id: str
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Get URL pointing to pre-change validation results"""
        if not self.authenticated:
            err = self._login()
            if err is not None:
                return err, None

        url = "{}/config-services/prechange-analysis/{}".format(self.api_url, job_id)
        resp = self.session.get(url)
        if resp.status_code != 200:
            logger.error("Get PCV url failed: {}".format(resp.json()))
            return resp, None
        try:
            response = json.loads(resp.content)["value"]["data"]
            pcv_url = "https://{}/nae/epoch-delta-analysis/result/health?analysis_id={}&type=PCV_EPOCH_DELTA_ANALYSIS&fabric_id={}&epoch={}#top".format(
                self.hostname_ip,
                response["epoch_delta_job_id"],
                response["fabric_uuid"],
                response["pre_change_epoch_uuid"],
            )
            return None, pcv_url
        except KeyError:
            pass
        logger.error("PCV url parameters could not be found: {}".format(resp.json()))
        return resp, None
