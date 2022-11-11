[![Tests](https://github.com/netascode/nexus-pcv/actions/workflows/test.yml/badge.svg)](https://github.com/netascode/nexus-pcv/actions/workflows/test.yml)
![Python Support](https://img.shields.io/badge/python-3.7%20%7C%203.8%20%7C%203.9%20%7C%203.10-informational "Python Support: 3.7, 3.8, 3.9, 3.10")

# nexus-pcv

A CLI tool to perform a pre-change validation on Nexus Dashboard Insights or Network Assurance Engine. It can either work with provided JSON file(s) or a `terraform plan` output from a [Nexus as Code](https://cisco.com/go/nexusascode) project. It waits for the analysis to complete and evaluates the results.

```
$ nexus-pcv -h
Usage: nexus-pcv [OPTIONS]

  A CLI tool to perform a pre-change validation on Nexus Dashboard Insights or
  Network Assurance Engine.

Options:
  --version                   Show the version and exit.
  -v, --verbosity LVL         Either CRITICAL, ERROR, WARNING, INFO or DEBUG.
  -i, --hostname-ip TEXT      NAE/ND hostname or IP (required, env:
                              PCV_HOSTNAME_IP).
  -u, --username TEXT         NAE/ND username (required, env: PCV_USERNAME).
  -p, --password TEXT         NAE/ND password (required, env: PCV_PASSWORD).
  -d, --domain TEXT           NAE/ND login domain (optional, default: 'Local',
                              env: PCV_DOMAIN).
  -g, --group TEXT            NAE assurance group name or NDI insights group
                              name (required, env: PCV_GROUP).
  -s, --site TEXT             NDI site or fabric name (optional, only required
                              for NDI, env: PCV_SITE).
  -n, --name TEXT             NAE/NDI pre-change validation name (optional,
                              env: PCV_NAME).
  -s, --suppress-events TEXT  NAE/NDI comma-separated list of events to
                              suppress (optional, default: 'APP_EPG_NOT_DEPLOY
                              ED,APP_EPG_HAS_NO_CONTRACT_IN_ENFORCED_VRF',
                              env: PCV_SUPPRESS_EVENTS).
  -t, --timeout INTEGER       NAE/NDI pre-change validation timeout in minutes
                              (optional, default: 15, env: PCV_TIMEOUT).
  -f, --file FILE             NAE/NDI proposed change JSON file (optional,
                              env: PCV_FILE).
  -t, --nac-tf-plan FILE      NAE/NDI proposed change Terraform plan output
                              (optional, env: PCV_NAC_TF_PLAN).
  -o, --output-summary FILE   NAE/NDI summary of new events/anomalies written
                              to a file (optional, env: PCV_OUTPUT_SUMMARY).
  -r, --output-url FILE       NAE/NDI link (URL) to pre-change validation
                              results written to a file (optional, env:
                              PCV_OUTPUT_URL).
  -h, --help                  Show this message and exit.
```

## Installation

Python 3.7+ is required to install `nexus-pcv`. Don't have Python 3.7 or later? See [Python 3 Installation & Setup Guide](https://realpython.com/installing-python/).

`nexus-pcv` can be installed in a virtual environment using `pip`:

```
pip install nexus-pcv
```

## CI/CD Integration

The tool can easily be integrated with CI/CD workflows. Arguments can either be provided via command line or environment variables. The tool will exit with a non-zero exit code in case of an error or non-suppressed events being discovered during the pre-change analysis. The `--output-summary` and `--output-url` arguments can be used to write a summary and/or a link (URL) to a file, which can then be embedded into notifications (e.g., Webex).

## *Nexus as Code* Integration

*Nexus as Code* allows users to instantiate network fabrics in minutes using an easy to use, opinionated data model. More information about *Nexus as Code* can be found [here](https://cisco.com/go/nexusascode). A planned change can be validated before applying it to a production environment by running a `terraform plan` operation first and then providing the output to `nexus-pcv` to trigger a pre-change validation.

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
