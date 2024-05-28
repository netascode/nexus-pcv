# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

from typing import Any, List, Mapping, Tuple

import click


class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args: Any, **kwargs: Any):
        self.mutually_exclusive = set(kwargs.pop("mutually_exclusive", []))
        help = kwargs.get("help", "")
        if self.mutually_exclusive:
            ex_str = ", ".join(self.mutually_exclusive)
            kwargs["help"] = help + (
                " NOTE: This argument is mutually exclusive with "
                " arguments: [" + ex_str + "]."
            )
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(
        self, ctx: click.Context, opts: Mapping[str, Any], args: List[str]
    ) -> Tuple[Any, List[str]]:
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                "Illegal usage: `{}` is mutually exclusive with "
                "arguments `{}`.".format(self.name, ", ".join(self.mutually_exclusive))
            )

        return super(MutuallyExclusiveOption, self).handle_parse_result(ctx, opts, args)


hostname_ip = click.option(
    "-i",
    "--hostname-ip",
    type=str,
    envvar="PCV_HOSTNAME_IP",
    help="ND hostname or IP (required, env: PCV_HOSTNAME_IP).",
    required=True,
)

username = click.option(
    "-u",
    "--username",
    type=str,
    envvar="PCV_USERNAME",
    help="ND username (required, env: PCV_USERNAME).",
    required=True,
)

password = click.option(
    "-p",
    "--password",
    type=str,
    envvar="PCV_PASSWORD",
    help="ND password (required, env: PCV_PASSWORD).",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    required=True,
)

domain = click.option(
    "-d",
    "--domain",
    type=str,
    default="local",
    envvar="PCV_DOMAIN",
    help="ND login domain (optional, default: 'local', env: PCV_DOMAIN).",
    required=False,
)

group = click.option(
    "-g",
    "--group",
    type=str,
    default="default",
    envvar="PCV_GROUP",
    help="NDI insights group name (optional, default: 'default', env: PCV_GROUP).",
    required=False,
)

site = click.option(
    "-s",
    "--site",
    type=str,
    envvar="PCV_SITE",
    help="NDI site or fabric name (required, env: PCV_SITE).",
    required=True,
)

name = click.option(
    "-n",
    "--name",
    type=str,
    envvar="PCV_NAME",
    help="NDI pre-change validation name (required, env: PCV_NAME).",
    required=True,
)

timeout = click.option(
    "--timeout",
    type=int,
    default=15,
    envvar="PCV_TIMEOUT",
    help="NDI pre-change validation timeout in minutes (optional, default: 15, env: PCV_TIMEOUT).",
    required=False,
)

suppress_events = click.option(
    "--suppress-events",
    type=str,
    envvar="PCV_SUPPRESS_EVENTS",
    default="APP_EPG_NOT_DEPLOYED,APP_EPG_HAS_NO_CONTRACT_IN_ENFORCED_VRF",
    help="NDI comma-separated list of events to suppress (optional, default: 'APP_EPG_NOT_DEPLOYED,APP_EPG_HAS_NO_CONTRACT_IN_ENFORCED_VRF', env: PCV_SUPPRESS_EVENTS).",
    required=False,
)


file = click.option(
    "-f",
    "--file",
    cls=MutuallyExclusiveOption,
    type=click.Path(exists=True, dir_okay=False, file_okay=True),
    multiple=True,
    envvar="PCV_FILE",
    help="NDI proposed change JSON file (optional, env: PCV_FILE).",
    required=False,
)

nac_tf_plan = click.option(
    "-t",
    "--nac-tf-plan",
    cls=MutuallyExclusiveOption,
    type=click.Path(exists=True, dir_okay=False, file_okay=True),
    envvar="PCV_NAC_TF_PLAN",
    help="NDI proposed change Terraform plan output (optional, env: PCV_NAC_TF_PLAN).",
    required=False,
)

output_summary = click.option(
    "-o",
    "--output-summary",
    type=click.Path(exists=False, dir_okay=False, file_okay=True),
    envvar="PCV_OUTPUT_SUMMARY",
    help="NDI summary of new events/anomalies written to a file (optional, env: PCV_OUTPUT_SUMMARY).",
    required=False,
)

output_url = click.option(
    "-r",
    "--output-url",
    type=click.Path(exists=False, dir_okay=False, file_okay=True),
    envvar="PCV_OUTPUT_URL",
    help="NDI link (URL) to pre-change validation results written to a file (optional, env: PCV_OUTPUT_URL).",
    required=False,
)
