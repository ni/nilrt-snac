import argparse
import pathlib

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import EqualsDelimitedConfigFile

from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper


class _USBGuardConfig(_BaseConfig):
    """USBGuard configuration handler."""

    def __init__(self):
        self.config_file_path = "/etc/usbguard/usbguard-daemon.conf"
        self.package_name = "usbguard"
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        """USBGuard must be installed manually by the user."""
        if not self._opkg_helper.is_installed(self.package_name):
            print("USBGuard configuration: Manual installation required")

    def verify(self, args: argparse.Namespace) -> bool:
        """Verify USBGuard configuration if the package is installed."""
        if self._opkg_helper.is_installed(self.package_name):
            print("Verifying usbguard configuration...")
            conf_file = EqualsDelimitedConfigFile(self.config_file_path)
            if not conf_file.exists():
                logger.error(f"USBGuard config file missing: {self.config_file_path}")
                return False
            # We make sure we get the RuleFile that does not have a comment
            rule_file_path = conf_file.get("RuleFile")
            if rule_file_path == "":
                logger.error(f"USBGuard RuleFile not specified in {self.config_file_path}")
                return False
            rules_file = pathlib.Path(rule_file_path)
            if not rules_file.exists():
                logger.error(f"USBGuard rules file missing: {rules_file_path}")
                return False
            if rules_file.stat().st_size == 0:
                logger.error(f"USBGuard rules file is empty: {rules_file_path}")
                return False
            return True
        else:
            print("USBGuard is not installed; skipping verification.")
            return True

