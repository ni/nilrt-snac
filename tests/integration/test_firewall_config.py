"""Tests for firewalld configuration behavior."""

import argparse
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from nilrt_snac._configs import _firewall_config


def test_configure_allows_ni_rpc_server():
    config = _firewall_config._FirewallConfig()
    calls = []
    system_calls = []

    def offlinecmd(*args):
        calls.append(args)

    def run_with_logging(*args, **kwargs):
        system_calls.append((args, kwargs))

    with (
        patch.object(config._opkg_helper, "install"),
        patch.object(_firewall_config, "_offlinecmd", side_effect=offlinecmd),
        patch.object(_firewall_config, "_cmd"),
        patch.object(_firewall_config, "run_with_logging", side_effect=run_with_logging),
        patch.object(
            _firewall_config.subprocess,
            "run",
            side_effect=[
                subprocess.TimeoutExpired(["firewall-cmd", "--state"], timeout=2),
                subprocess.CompletedProcess(
                    ["firewall-cmd", "--state"], 0, stdout="running"
                ),
            ],
        ),
    ):
        config.configure(argparse.Namespace(dry_run=False))

    assert (
        "--policy=work-in",
        "--add-service=ni-labview-realtime",
        "--add-service=ni-labview-viserver",
        "--add-service=ni-logos-xt",
        "--add-service=ni-mxs",
        "--add-service=ni-rpc-server",
        "--add-service=ni-service-locator",
    ) in calls
    assert not any("--add-rich-rule=" in arg for call in calls for arg in call)
    assert (
        ("nirtcfg", "--set", "section=SystemSettings,token=firewall.enabled,value=True"),
        {"check": True},
    ) in system_calls
    assert (("/etc/init.d/firewalld", "start"), {"check": True}) in system_calls

    service_definition = (
        Path(__file__).resolve().parents[2] / "src/firewalld/services/ni-rpc-server.xml"
    )
    service = ET.parse(service_definition).getroot()
    assert service.find("./port").attrib == {"protocol": "tcp", "port": "43973"}
