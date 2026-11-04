"""Tests for firewalld configuration behavior."""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from nilrt_snac._configs import _firewall_config


def test_configure_allows_ni_rpc_server():
    config = _firewall_config._FirewallConfig()
    calls = []

    def offlinecmd(*args):
        calls.append(args)

    with (
        patch.object(config._opkg_helper, "install"),
        patch.object(_firewall_config, "_offlinecmd", side_effect=offlinecmd),
        patch.object(_firewall_config, "_cmd"),
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

    service_definition = (
        Path(__file__).resolve().parents[2] / "src/firewalld/services/ni-rpc-server.xml"
    )
    service = ET.parse(service_definition).getroot()
    assert service.find("./port").attrib == {"protocol": "tcp", "port": "43973"}
