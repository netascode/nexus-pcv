# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import logging
import sys
from typing import List, Optional
from pathlib import Path

import typer

import nexus_pcv
from nexus_pcv.pcv import PCV
from . import options

logger = logging.getLogger(__name__)

app = typer.Typer(
    help="A CLI tool to perform a pre-change validation on Nexus Dashboard Insights.",
    add_completion=False,
)


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


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"nexus-pcv version {nexus_pcv.__version__}")
        raise typer.Exit()


@app.command()
def main(
    hostname_ip: str = options.hostname_ip,
    username: str = options.username,
    password: str = options.password,
    site: str = options.site,
    name: str = options.name,
    domain: str = options.domain,
    group: str = options.group,
    timeout: int = options.timeout,
    suppress_events: str = options.suppress_events,
    file: Optional[List[Path]] = options.file,
    nac_tf_plan: Optional[Path] = options.nac_tf_plan,
    output_summary: Optional[Path] = options.output_summary,
    output_url: Optional[Path] = options.output_url,
    verbosity: str = options.verbosity,
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """A CLI tool to perform a pre-change validation on Nexus Dashboard Insights."""
    configure_logging(verbosity)

    try:
        pcv = PCV(hostname_ip, username, password, domain, timeout)

        # Load files if provided
        if file:
            pcv.load_json_files([str(f) for f in file])
        if nac_tf_plan:
            pcv.load_tf_plan(str(nac_tf_plan))

        # Run the pre-change validation
        pcv.ndi_pcv(
            name,
            group,
            site,
            suppress_events,
            str(output_summary) if output_summary else "",
            str(output_url) if output_url else "",
        )

    except Exception as e:
        logger.error(f"Error during execution: {e}")
        raise typer.Exit(code=1)
