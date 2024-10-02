import argparse
import textwrap

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile

from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper


class _PWQualityConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring Password quality...")
        config_file = _ConfigFile("/etc/pam.d/common-password")
        dry_run: bool = args.dry_run
        self._opkg_helper.install("libpwquality")

        if not config_file.contains("remember=5"):
            config_file.update(r"(password.*pam_unix.so.*)", r"\1 remember=5")
        if not config_file.contains("password.*requisite.*pam_pwquality.so.*retry=3"):
            config_file.update(
                r"(.*here are the per-package modules.*)",
                textwrap.dedent(
                    r"""
                    # check for password complexity
                    password	requisite	pam_pwquality.so retry=3
                    \1"""
                )
            )

        config_file.save(dry_run)

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying Password quality...")
        config_file = _ConfigFile("/etc/pam.d/common-password")
        valid = True
        if not self._opkg_helper.is_installed("libpwquality"):
            valid = False
            logger.error("MISSING: libpwquality not installed")
        if not config_file.contains("remember=5"):
            valid = False
            logger.error("MISSING: 'remember=5' for pam_unix.so configuration")
        if not config_file.contains("password.*requisite.*pam_pwquality.so.*retry=3"):
            valid = False
            logger.error("MISSING: entry to add quality check")
        return valid
