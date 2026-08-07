# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

import logging

import httpx

from .base import NDBackend
from .legacy import LegacyNDI
from .nd4 import ND4

logger = logging.getLogger(__name__)


def detect_major_version(hostname_ip: str) -> int | None:
    """Read the ND major version from the unauthenticated /version.json endpoint.

    Returns None when the endpoint is missing or unparseable, which is the
    expected outcome on older releases that predate it.
    """
    url = f"https://{hostname_ip}/version.json"
    with httpx.Client(verify=False) as client:  # nosec B501
        # SSL verification disabled in Client() constructor
        resp = client.get(url)
    if resp.status_code != 200:
        logger.warning(
            f"Could not read {url} (HTTP {resp.status_code}), "
            "assuming a pre-4.0 Nexus Dashboard."
        )
        return None
    try:
        major = int(resp.json()["major"])
    except (ValueError, KeyError, TypeError):
        logger.warning(
            f"Unexpected payload from {url}, assuming a pre-4.0 Nexus Dashboard."
        )
        return None
    return major


def create_backend(
    hostname_ip: str,
    username: str,
    password: str,
    domain: str,
    timeout: int,
    force_version: int | None = None,
) -> NDBackend:
    """Pick the backend matching the target Nexus Dashboard release.

    ``force_version`` bypasses detection and is intended as a field escape
    hatch when a release reports a version we do not expect.
    """
    major = (
        force_version
        if force_version is not None
        else detect_major_version(hostname_ip)
    )
    if major is not None and major >= 4:
        logger.info(f"Detected Nexus Dashboard {major}.x, using the ND 4.x backend.")
        return ND4(hostname_ip, username, password, domain, timeout)
    logger.info(
        f"Detected Nexus Dashboard {major if major is not None else 'pre-4.0'}, "
        "using the legacy NDI backend."
    )
    return LegacyNDI(hostname_ip, username, password, domain, timeout)
