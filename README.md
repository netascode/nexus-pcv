[![Tests](https://github.com/netascode/nexus-pcv/actions/workflows/test.yml/badge.svg)](https://github.com/netascode/nexus-pcv/actions/workflows/test.yml)
![Python Support](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-informational "Python Support: 3.10, 3.11, 3.12, 3.13")

# nexus-pcv

A modern CLI tool to perform a pre-change validation on Nexus Dashboard Insights. It can either work with provided JSON file(s) or a `terraform plan` output from a [Network as Code](https://netascode.cisco.com) project. It waits for the analysis to complete and evaluates the results.

```
$ nexus-pcv --help
Usage: nexus-pcv [OPTIONS]                                                     
                                                                                
 A CLI tool to perform a pre-change validation on Nexus Dashboard Insights.     
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --hostname-ip      -i      TEXT     ND hostname or IP.                    │
│                                        [env var: PCV_HOSTNAME_IP]            │
│                                        [required]                            │
│ *  --username         -u      TEXT     ND username. [env var: PCV_USERNAME]  │
│                                        [required]                            │
│ *  --password         -p      TEXT     ND password. [env var: PCV_PASSWORD]  │
│                                        [required]                            │
│ *  --site             -s      TEXT     NDI site or fabric name.              │
│                                        [env var: PCV_SITE]                   │
│                                        [required]                            │
│ *  --name             -n      TEXT     NDI pre-change validation name.       │
│                                        [env var: PCV_NAME]                   │
│                                        [required]                            │
│    --domain           -d      TEXT     ND login domain.                      │
│                                        [env var: PCV_DOMAIN]                 │
│                                        [default: local]                      │
│    --group            -g      TEXT     NDI insights group name.              │
│                                        [env var: PCV_GROUP]                  │
│                                        [default: default]                    │
│    --timeout                  INTEGER  NDI pre-change validation timeout in  │
│                                        minutes.                              │
│                                        [env var: PCV_TIMEOUT]                │
│                                        [default: 15]                         │
│    --suppress-events          TEXT     NDI comma-separated list of events to │
│                                        suppress.                             │
│                                        [env var: PCV_SUPPRESS_EVENTS]        │
│                                        [default:                             │
│                                        APP_EPG_NOT_DEPLOYED,APP_EPG_HAS_NO_… │
│    --file             -f      FILE     NDI proposed change JSON file.        │
│                                        [env var: PCV_FILE]                   │
│    --nac-tf-plan      -t      FILE     NDI proposed change Terraform plan    │
│                                        output.                               │
│                                        [env var: PCV_NAC_TF_PLAN]            │
│    --output-summary   -o      FILE     NDI summary of new events/anomalies   │
│                                        written to a file.                    │
│                                        [env var: PCV_OUTPUT_SUMMARY]         │
│    --output-url       -r      FILE     NDI link (URL) to pre-change          │
│                                        validation results written to a file. │
│                                        [env var: PCV_OUTPUT_URL]             │
│    --verbosity        -v      TEXT     Either CRITICAL, ERROR, WARNING, INFO │
│                                        or DEBUG.                             │
│                                        [default: WARNING]                    │
│    --version                           Show the version and exit.            │
│    --help                              Show this message and exit.           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Installation

Python 3.10+ is required to install `nexus-pcv`. Don't have Python 3.10 or later? See [Python 3 Installation & Setup Guide](https://realpython.com/installing-python/).

`nexus-pcv` can be installed using `pip`:

```
pip install nexus-pcv
```

or using [uv](https://docs.astral.sh/uv/):

```
uv tool install nexus-pcv
```

## CI/CD Integration

The tool can easily be integrated with CI/CD workflows. Arguments can either be provided via command line or environment variables. The tool will exit with a non-zero exit code in case of an error or non-suppressed events being discovered during the pre-change analysis. The `--output-summary` and `--output-url` arguments can be used to write a summary and/or a link (URL) to a file, which can then be embedded into notifications (e.g., Webex).

## *Network as Code* Integration

*Network as Code* for ACI allows users to instantiate network fabrics in minutes using an easy to use, opinionated data model. More information about *Network as Code* can be found [here](https://netascode.cisco.com). A planned change can be validated before applying it to a production environment by running a `terraform plan` operation first and then providing the output to `nexus-pcv` to trigger a pre-change validation.

```
export PCV_HOSTNAME_IP=10.1.1.1
export PCV_USERNAME=admin
export PCV_PASSWORD=Cisco123
export PCV_GROUP=LAB
export PCV_SITE=LAB1
terraform plan -out=plan.tfplan
terraform show -json plan.tfplan > plan.json
nexus-pcv --name "PCV1" --nac-tf-plan plan.json
```
