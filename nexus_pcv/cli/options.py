# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

from pathlib import Path
from typing import Annotated

import typer

# Typer Option definitions for the CLI

hostname_ip = typer.Option(
    ...,
    "-i",
    "--hostname-ip",
    envvar="PCV_HOSTNAME_IP",
    help="ND hostname or IP.",
)

username = typer.Option(
    ...,
    "-u",
    "--username",
    envvar="PCV_USERNAME",
    help="ND username.",
)

password = typer.Option(
    ...,
    "-p",
    "--password",
    envvar="PCV_PASSWORD",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="ND password.",
)

site = typer.Option(
    ...,
    "-s",
    "--site",
    envvar="PCV_SITE",
    help="NDI site or fabric name.",
)

name = typer.Option(
    ...,
    "-n",
    "--name",
    envvar="PCV_NAME",
    help="NDI pre-change validation name.",
)

domain = typer.Option(
    "local",
    "-d",
    "--domain",
    envvar="PCV_DOMAIN",
    help="ND login domain.",
)

group = typer.Option(
    "default",
    "-g",
    "--group",
    envvar="PCV_GROUP",
    help="NDI insights group name.",
)

timeout = typer.Option(
    15,
    "--timeout",
    envvar="PCV_TIMEOUT",
    help="NDI pre-change validation timeout in minutes.",
)

suppress_events = typer.Option(
    "APP_EPG_NOT_DEPLOYED,APP_EPG_HAS_NO_CONTRACT_IN_ENFORCED_VRF",
    "--suppress-events",
    envvar="PCV_SUPPRESS_EVENTS",
    help="NDI comma-separated list of events to suppress.",
)

file = typer.Option(
    None,
    "-f",
    "--file",
    envvar="PCV_FILE",
    help="NDI proposed change JSON file.",
    exists=True,
    file_okay=True,
    dir_okay=False,
)

nac_tf_plan = typer.Option(
    None,
    "-t",
    "--nac-tf-plan",
    envvar="PCV_NAC_TF_PLAN",
    help="NDI proposed change Terraform plan output.",
    exists=True,
    file_okay=True,
    dir_okay=False,
)

output_summary = typer.Option(
    None,
    "-o",
    "--output-summary",
    envvar="PCV_OUTPUT_SUMMARY",
    help="NDI summary of new events/anomalies written to a file.",
    file_okay=True,
    dir_okay=False,
)

output_url = typer.Option(
    None,
    "-r",
    "--output-url",
    envvar="PCV_OUTPUT_URL",
    help="NDI link (URL) to pre-change validation results written to a file.",
    file_okay=True,
    dir_okay=False,
)

verbosity = typer.Option(
    "WARNING",
    "-v",
    "--verbosity",
    help="Either CRITICAL, ERROR, WARNING, INFO or DEBUG.",
)

# version option handled directly in main.py due to callback requirements

# Type annotations for function parameters

HostnameIp = Annotated[str, hostname_ip]
Username = Annotated[str, username]
Password = Annotated[str, password]
Site = Annotated[str, site]
Name = Annotated[str, name]
Domain = Annotated[str, domain]
Group = Annotated[str, group]
Timeout = Annotated[int, timeout]
SuppressEvents = Annotated[str, suppress_events]
File = Annotated[list[Path] | None, file]
NacTfPlan = Annotated[Path | None, nac_tf_plan]
OutputSummary = Annotated[Path | None, output_summary]
OutputUrl = Annotated[Path | None, output_url]
Verbosity = Annotated[str, verbosity]
# Version handled directly in main.py
