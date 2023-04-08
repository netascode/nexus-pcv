# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

from enum import Enum
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3
import yaml

from .apic import ApicObject
from .const import RN_PREFIX_CLASSNAME_MAPPINGS
from .nae import NAE
from .ndi import NDI

logger = logging.getLogger(__name__)


class PCV:
    class Platform(Enum):
        NDI = 1
        NAE = 2

    def __init__(
        self,
        hostname_ip: str,
        username: str,
        password: str,
        domain: str,
        timeout: int,
        platform: Platform,
    ):
        self.platform = platform
        if platform is self.Platform.NDI:
            self.ndi = NDI(hostname_ip, username, password, domain, timeout)
        elif platform is self.Platform.NAE:
            self.nae = NAE(hostname_ip, username, password, domain, timeout)
        self.root = ApicObject("root", {}, [], None)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _resolve_tf_classnames(self, root: ApicObject, tf_plan: Any) -> None:
        """Helper function to resolve missing class names and key attributes using the Terraform plan"""
        if root.cl is None:
            dn = root["dn"]
            for change in tf_plan.get("resource_changes", []):
                section = (
                    "after" if change["change"].get("after") is not None else "before"
                )
                plan_dn = change["change"].get(section, {}).get("dn")
                if dn == plan_dn:
                    logger.debug(
                        "Resolving classname from Terraform plan for '{}'".format(dn)
                    )
                    root.cl = change["change"].get(section, {}).get("class_name")
                    name = (
                        change["change"].get(section, {}).get("content", {}).get("name")
                    )
                    if name:
                        logger.debug(
                            "Resolving name attribute from Terraform plan for '{}'".format(
                                dn
                            )
                        )
                        root.attributes["name"] = name

        for child in root.children:
            self._resolve_tf_classnames(child, tf_plan)

    def _resolve_static_classnames(self, root: ApicObject) -> None:
        """Helper function to resolve missing class names and key attributes using static mappings"""
        parts = str(root["dn"]).split("/")[-1].split("-", 1)
        prefix = parts[0]
        name = parts[1] if len(parts) > 1 else None
        if prefix in RN_PREFIX_CLASSNAME_MAPPINGS:
            mapping = RN_PREFIX_CLASSNAME_MAPPINGS[prefix]
            if root.cl is None:
                logger.debug(
                    "Statically resolving classname for '{}'".format(root["dn"])
                )
                root.cl = mapping.get("class")
            if root.cl == mapping.get("class"):
                for key in mapping.get("keys", []):
                    key_attribute = key.get("attribute")
                    key_regex = key.get("regex")
                    if (
                        key_attribute is not None
                        and key_regex is not None
                        and name is not None
                    ):
                        regex = re.compile(key_regex)
                        mo = regex.search(name)
                        if mo is not None and key_attribute not in root.attributes:
                            logger.debug(
                                "Statically adding key attribute '{}' for '{}'".format(
                                    key_attribute, root["dn"]
                                )
                            )
                            root.attributes[key_attribute] = mo.group()
        for child in root.children:
            self._resolve_static_classnames(child)

    def _check_classes(self, root: ApicObject) -> None:
        """Helper function to verify if all objects have classnames"""
        if root.cl is None:
            logger.error("Missing classname for '{}'".format(root["dn"]))
        for child in root.children:
            self._check_classes(child)

    def _load_json_objects(
        self, json_dict: Dict[Any, Any], parent: Optional[ApicObject] = None
    ) -> Optional[ApicObject]:
        """Helper function to load JSON objects into object tree"""
        new_obj = None
        for k, v in json_dict.items():
            new_obj = ApicObject(k, v.get("attributes"), [], parent)
            if parent:
                parent.children.append(new_obj)
            for child in v.get("children", []):
                self._load_json_objects(child, new_obj)
        return new_obj

    def load_json_files(self, filenames: List[str]) -> None:
        """Load objects from JSON files into object tree"""
        for filename in filenames:
            try:
                with open(filename, "r") as file:
                    inv = json.loads(file.read())
                    if "imdata" in inv:
                        for item in inv["imdata"]:
                            obj = self._load_json_objects(item)
                            self.root.insert(obj)
                    else:
                        obj = self._load_json_objects(inv)
                        self.root.insert(obj)
            except:  # noqa E722
                logger.error("Failed to load JSON file: {}".format(filename))
        self._resolve_static_classnames(self.root)
        self._check_classes(self.root)

    def load_tf_plan(self, filename: str) -> None:
        """Load changed objects from Terraform plan into object tree"""
        tf_plan = None
        with open(filename) as file:
            tf_plan = json.load(file)

        for change in tf_plan.get("resource_changes", []):
            if change.get("type") == "aci_rest_managed":
                action = change["change"].get("actions", [])
                if "create" in action or "update" in action or "delete" in action:
                    if "delete" in action:
                        classname = change["change"].get("before", {}).get("class_name")
                        attributes = {}
                        attributes = change["change"].get("before", {}).get("content")
                        attributes["status"] = "deleted"
                        attributes["dn"] = change["change"].get("before", {}).get("dn")
                    else:
                        classname = change["change"].get("after", {}).get("class_name")
                        attributes = change["change"].get("after", {}).get("content")
                        attributes["dn"] = change["change"].get("after", {}).get("dn")
                    attributes = {k: v for (k, v) in attributes.items() if v != ""}
                    obj = ApicObject(classname, attributes, [], None)
                    self.root.insert(obj)

        self._resolve_static_classnames(self.root)
        self._resolve_tf_classnames(self.root, tf_plan)
        self._check_classes(self.root)

    def _write_pcv_events(self, events: List[Any], file: str) -> None:
        with open(file, "w") as fh:
            fh.write(yaml.dump(events, default_flow_style=False))

    def _write_pcv_url(self, url: str, file: str) -> None:
        with open(file, "w") as fh:
            fh.write(url)

    def ndi_pcv(
        self,
        name: str,
        group: str,
        site: str,
        suppress_events: str,
        file_summary: str,
        file_url: str,
    ) -> Tuple[Optional[requests.Response], Optional[List[Any]], Optional[str]]:
        """Trigger an NDI pre-change validation"""
        if not len(self.root.children):
            logger.info("No updates planned. No need to trigger a pre-change analysis.")
            return None, None, None
        logger.debug("Proposed change (JSON): {}".format(self.root[0]))
        err, job_id = self.ndi.start_pcv(name, group, site, str(self.root[0]))
        if err is not None:
            return err, None, None
        err, epoch_job_id = self.ndi.wait_pcv(group, site, str(job_id))
        if err is not None:
            return err, None, None
        err, events = self.ndi.get_pcv_results(
            group, site, str(epoch_job_id), suppress_events
        )
        if err is not None:
            return err, None, None
        err, url = self.ndi.get_pcv_url()
        if err is not None:
            return err, None, None
        if file_summary and events:
            self._write_pcv_events(events, file_summary)
        if file_url and url is not None:
            self._write_pcv_url(url, file_url)
        return None, events, url

    def nae_pcv(
        self,
        name: str,
        group: str,
        suppress_events: str,
        file_summary: str,
        file_url: str,
    ) -> Tuple[Optional[requests.Response], Optional[List[Any]], Optional[str]]:
        """Trigger an NAE pre-change validation"""
        if not len(self.root.children):
            logger.info("No updates planned. No need to trigger a pre-change analysis.")
            return None, None, None
        logger.debug("Proposed change (JSON): {}".format(self.root[0]))
        err, job_id = self.nae.start_pcv(name, group, str(self.root[0]))
        if err is not None:
            return err, None, None
        err, epoch_job_id = self.nae.wait_pcv(str(job_id))
        if err is not None:
            return err, None, None
        err, events = self.nae.get_pcv_results(str(epoch_job_id), suppress_events)
        if err is not None:
            return err, None, None
        err, url = self.nae.get_pcv_url(str(job_id))
        if err is not None:
            return err, None, None
        if file_summary and events:
            self._write_pcv_events(events, file_summary)
        if file_url and url is not None:
            self._write_pcv_url(url, file_url)
        return None, events, url
