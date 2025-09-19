import argparse

from nilrt_snac._configs._base_config import _BaseConfig

from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper


class _SysAPIConfig(_BaseConfig):
    def __init__(self):
        super().__init__("sysapi")
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring SysAPI...")
        self._opkg_helper.install("ni-sysapi-sshcli")

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying SysAPI configuration...")
        valid = True
        if not self._opkg_helper.is_installed("ni-sysapi-sshcli"):
            valid = False
            logger.error("MISSING: ni-sysapi-sshcli not installed")
        return valid
