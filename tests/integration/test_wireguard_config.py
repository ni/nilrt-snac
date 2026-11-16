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
WGLV0_CONF = """\
[Interface]
Address = 172.16.1.1/24
ListenPort = 51820
Saveconfig = false
PostUp = wg set %i private-key /etc/wireguard/wglv0.privatekey
"""


@pytest.fixture
def fake_root(tmp_path):
    """Redirect every config file path used by _WireguardConfig under tmp_path."""
    (tmp_path / "etc" / "wireguard").mkdir(parents=True)
    (tmp_path / "etc" / "ifplugd").mkdir(parents=True)

    def rooted(cls):
        return lambda path: cls(tmp_path / pathlib.Path(path).relative_to("/"))

    def fake_run(argv, *args, **kwargs):
        if argv[1] == "genkey":
            return subprocess.CompletedProcess(argv, 0, stdout=b"genkey\n")
        return subprocess.CompletedProcess(argv, 0, stdout=f"pub({kwargs['input']})\n")

    config = _wireguard_config._WireguardConfig()
    with (
        patch.object(
            _wireguard_config, "_ConfigFile", side_effect=rooted(_wireguard_config._ConfigFile)
        ),
        patch.object(
            _wireguard_config,
            "EqualsDelimitedConfigFile",
            side_effect=rooted(_wireguard_config.EqualsDelimitedConfigFile),
        ),
        patch.object(_wireguard_config, "run_with_logging"),
        patch.object(_wireguard_config.subprocess, "run", side_effect=fake_run) as run,
        patch.object(config._opkg_helper, "install"),
    ):
        yield config, tmp_path / "etc" / "ifplugd" / "ifplugd.conf", run


def _configure(config):
    config.configure(argparse.Namespace(dry_run=False))


def test_configure_adds_one_ifplugd_block_across_runs(fake_root):
    config, ifplugd_conf, _ = fake_root
    ifplugd_conf.write_text(IFPLUGD_CONF)

    _configure(config)
    first = ifplugd_conf.read_text()
    _configure(config)
    _configure(config)

    assert first.count(MANAGED_LINE) == 1
    assert first.startswith(IFPLUGD_CONF)
    assert ifplugd_conf.read_text() == first


def test_configure_collapses_duplicate_ifplugd_blocks(fake_root):
    config, ifplugd_conf, _ = fake_root
    block = _wireguard_config._IFPLUGD_BLOCK
    ifplugd_conf.write_text(IFPLUGD_CONF + block * 3)

    _configure(config)

    assert ifplugd_conf.read_text() == IFPLUGD_CONF + block


def test_configure_respects_unmanaged_ifplugd_assignment(fake_root):
    config, ifplugd_conf, _ = fake_root
    custom = IFPLUGD_CONF + 'ARGS_wglv0="$ARGS --no-auto -q"\n'
    ifplugd_conf.write_text(custom)

    _configure(config)

    assert ifplugd_conf.read_text() == custom


def test_configure_generates_keypair(fake_root):
    config, ifplugd_conf, run = fake_root
    wg_dir = ifplugd_conf.parent.parent / "wireguard"
    (wg_dir / "wglv0.conf").write_text(WGLV0_CONF)

    _configure(config)

    assert (wg_dir / "wglv0.privatekey").read_text() == "genkey"
    assert (wg_dir / "wglv0.publickey").read_text() == "pub(genkey)"
    assert (wg_dir / "wglv0.conf").read_text() == WGLV0_CONF


def test_configure_writes_inline_private_key_to_key_files(fake_root):
    config, ifplugd_conf, run = fake_root
    wg_dir = ifplugd_conf.parent.parent / "wireguard"
    inline_key = "aGVsbG8gd29ybGQgdGhpcyBpcyBhIHRlc3Qga2V5IQ="
    conf = WGLV0_CONF.replace("[Interface]\n", f"[Interface]\nPrivateKey = {inline_key}\n")
    (wg_dir / "wglv0.conf").write_text(conf)

    _configure(config)

    assert (wg_dir / "wglv0.privatekey").read_text() == inline_key
    assert (wg_dir / "wglv0.publickey").read_text() == f"pub({inline_key})"
    assert ["wg", "genkey"] not in [c.args[0] for c in run.call_args_list]
    assert (wg_dir / "wglv0.conf").read_text() == conf


def test_configure_keeps_existing_key_files(fake_root):
    config, ifplugd_conf, run = fake_root
    wg_dir = ifplugd_conf.parent.parent / "wireguard"
    (wg_dir / "wglv0.conf").write_text(WGLV0_CONF)
    (wg_dir / "wglv0.privatekey").write_text("oldkey")
    (wg_dir / "wglv0.publickey").write_text("oldpub")

    _configure(config)

    assert (wg_dir / "wglv0.privatekey").read_text() == "oldkey"
    assert (wg_dir / "wglv0.publickey").read_text() == "oldpub"
    run.assert_not_called()
