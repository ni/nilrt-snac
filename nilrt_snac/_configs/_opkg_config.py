import argparse
import pathlib
import subprocess
import textwrap

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile

from nilrt_snac import logger
from nilrt_snac.opkg import OPKG_SNAC_CONF, opkg_helper


class _OPKGConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring opkg...")
        snac_config_file = _ConfigFile(OPKG_SNAC_CONF)
        snac_config_file.chmod(0o644)
        dry_run: bool = args.dry_run

        if not snac_config_file.contains_exact("option autoremove 1"):
            snac_config_file.add(
                textwrap.dedent(
                    """
                    # NILRT SNAC configuration opkg runparts. Do not hand-edit.
                    option autoremove 1
                    """
                )
            )

        if pathlib.Path("/etc/opkg/NI-dist.conf").exists():
            logger.debug("Removing unsupported package feeds...")
            if not dry_run:
                subprocess.run(["rm", "-fv", "/etc/opkg/NI-dist.conf"], check=True)

        snac_config_file.save(dry_run)
        self._opkg_helper.update()

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying opkg configuration...")
        snac_config_file = _ConfigFile(OPKG_SNAC_CONF)
        valid = True
        if not snac_config_file.exists():
            valid = False
            logger.error(f"MISSING: {OPKG_SNAC_CONF} not found")
        elif not snac_config_file.contains_exact("option autoremove 1"):
            valid = False
            logger.error(f"MISSING: 'option autoremove 1' not found in {snac_config_file.path}")
        if pathlib.Path("/etc/opkg/NI-dist.conf").exists():
            valid = False
            logger.error("UNSUPPORTED: /etc/opkg/NI-dist.conf found")
        return valid
