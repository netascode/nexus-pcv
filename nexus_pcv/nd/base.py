# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PcvContext:
    """Everything needed to fetch results, gathered while polling the job.

    Legacy only populates ``result_id`` (the epoch delta job ID). ND 4.x fills
    the rest from the job detail response, which returns them all in one shot.
    """

    result_id: str
    fabric_name: str = ""
    start_date: str = ""
    end_date: str = ""


class NDBackend(ABC):
    """Common interface for the legacy NDI and ND 4.x pre-change APIs.

    Every method keeps the ``(err, value)`` tuple convention of the original
    NDI class: ``err`` is the offending response on failure and None on
    success, ``value`` is the payload on success and None on failure.
    """

    def __init__(
        self,
        hostname_ip: str,
        username: str,
        password: str,
        domain: str,
        timeout: int,
    ):
        self.hostname_ip = hostname_ip
        self.username = username
        self.password = password
        self.domain = domain
        self.timeout = timeout
        self.session = httpx.Client(verify=False)  # nosec B501
        # SSL verification disabled in Client() constructor
        self.authenticated = False

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

    def _ensure_login(self) -> httpx.Response | None:
        """Log in unless a previous call already did"""
        if not self.authenticated:
            return self._login()
        return None

    @staticmethod
    def _suppressed(
        severity: str | None, mnemonic: str | None, suppress_events: str
    ) -> bool:
        """Common filter: drop informational events and suppressed mnemonics"""
        if str(severity) == "info":
            return True
        return str(mnemonic) in suppress_events.split(",")

    @abstractmethod
    def start_pcv(
        self, name: str, group: str, site: str, json_data: str
    ) -> tuple[httpx.Response | None, str | None]:
        """Start a pre-change validation and return its job ID"""
        raise NotImplementedError

    @abstractmethod
    def wait_pcv(
        self, group: str, site: str, job_id: str
    ) -> tuple[httpx.Response | None, PcvContext | None]:
        """Wait for the validation to complete and return the results context"""
        raise NotImplementedError

    @abstractmethod
    def get_pcv_results(
        self, group: str, site: str, ctx: PcvContext, suppress_events: str
    ) -> tuple[httpx.Response | None, list[Any] | None]:
        """Retrieve the new anomalies raised by the proposed change"""
        raise NotImplementedError

    @abstractmethod
    def get_pcv_url(
        self, site: str, job_id: str, ctx: PcvContext | None = None
    ) -> tuple[httpx.Response | None, str | None]:
        """Return a UI link pointing at the validation results"""
        raise NotImplementedError
