"""Tests for WireGuard configuration behavior."""

import argparse
import pathlib
import subprocess
from unittest.mock import patch

import pytest

from nilrt_snac._configs import _wireguard_config

IFPLUGD_CONF = """\
INTERFACES=auto
ARGS="-fI -u0 -d0 -a -m auto -M -l"
ARGS_wlan0="-fI -u0 -d0 -a -m iff -M -l"
"""
MANAGED_LINE = 'ARGS_wglv0="$ARGS --no-auto"'


@pytest.fixture
def fake_root(tmp_path):
    """Redirect every _ConfigFile path used by _WireguardConfig under tmp_path."""
    (tmp_path / "etc" / "wireguard").mkdir(parents=True)
    (tmp_path / "etc" / "ifplugd").mkdir(parents=True)
    real_config_file = _wireguard_config._ConfigFile

    def rooted_config_file(path):
        return real_config_file(tmp_path / pathlib.Path(path).relative_to("/"))

    def fake_run(argv, *args, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=b"key" if argv[1] == "genkey" else "pub")

    config = _wireguard_config._WireguardConfig()
    with (
        patch.object(_wireguard_config, "_ConfigFile", side_effect=rooted_config_file),
        patch.object(_wireguard_config, "run_with_logging"),
        patch.object(_wireguard_config.subprocess, "run", side_effect=fake_run),
        patch.object(config._opkg_helper, "install"),
    ):
        yield config, tmp_path / "etc" / "ifplugd" / "ifplugd.conf"


def _configure(config):
    config.configure(argparse.Namespace(dry_run=False))


def test_configure_adds_one_ifplugd_block_across_runs(fake_root):
    config, ifplugd_conf = fake_root
    ifplugd_conf.write_text(IFPLUGD_CONF)

    _configure(config)
    first = ifplugd_conf.read_text()
    _configure(config)
    _configure(config)

    assert first.count(MANAGED_LINE) == 1
    assert first.startswith(IFPLUGD_CONF)
    assert ifplugd_conf.read_text() == first


def test_configure_collapses_duplicate_ifplugd_blocks(fake_root):
    config, ifplugd_conf = fake_root
    block = _wireguard_config._IFPLUGD_BLOCK
    ifplugd_conf.write_text(IFPLUGD_CONF + block * 3)

    _configure(config)

    assert ifplugd_conf.read_text() == IFPLUGD_CONF + block


def test_configure_respects_unmanaged_ifplugd_assignment(fake_root):
    config, ifplugd_conf = fake_root
    custom = IFPLUGD_CONF + 'ARGS_wglv0="$ARGS --no-auto -q"\n'
    ifplugd_conf.write_text(custom)

    _configure(config)

    assert ifplugd_conf.read_text() == custom
