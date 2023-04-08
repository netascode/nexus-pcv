# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import logging
import sys
from typing import List

import click
import errorhandler

import nexus_pcv
from nexus_pcv.pcv import PCV

from . import options

logger = logging.getLogger(__name__)

error_handler = errorhandler.ErrorHandler()


def configure_logging(level: str) -> None:
    if level == "DEBUG":
        lev = logging.DEBUG
    elif level == "INFO":
        lev = logging.INFO
    elif level == "WARNING":
        lev = logging.WARNING
    elif level == "ERROR":
        lev = logging.ERROR
    else:
        lev = logging.CRITICAL
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(lev)


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(nexus_pcv.__version__)
@click.option(
    "-v",
    "--verbosity",
    metavar="LVL",
    is_eager=True,
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]),
    help="Either CRITICAL, ERROR, WARNING, INFO or DEBUG.",
    default="WARNING",
)
@options.hostname_ip
@options.username
@options.password
@options.domain
@options.group
@options.site
@options.name
@options.suppress_events
@options.timeout
@options.file
@options.nac_tf_plan
@options.output_summary
@options.output_url
def main(
    verbosity: str,
    hostname_ip: str,
    username: str,
    password: str,
    domain: str,
    group: str,
    site: str,
    name: str,
    suppress_events: str,
    timeout: int,
    file: List[str],
    nac_tf_plan: str,
    output_summary: str,
    output_url: str,
) -> None:
    """A CLI tool to perform a pre-change validation on Nexus Dashboard Insights or Network Assurance Engine."""
    configure_logging(verbosity)

    platform = PCV.Platform.NDI if site else PCV.Platform.NAE
    pcv = PCV(hostname_ip, username, password, domain, timeout, platform)
    if file:
        pcv.load_json_files(file)
    if nac_tf_plan:
        pcv.load_tf_plan(nac_tf_plan)
    if error_handler.fired:
        exit()
    if platform is PCV.Platform.NDI:
        pcv.ndi_pcv(name, group, site, suppress_events, output_summary, output_url)
    else:
        pcv.nae_pcv(name, group, suppress_events, output_summary, output_url)
    exit()


def exit() -> None:
    if error_handler.fired:
        sys.exit(1)
    else:
        sys.exit(0)
