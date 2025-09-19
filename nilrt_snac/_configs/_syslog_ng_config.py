import argparse

from nilrt_snac import logger
from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._common import _check_owner, _cmd
from nilrt_snac.opkg import opkg_helper


class _SyslogConfig(_BaseConfig):
    def __init__(self):
        super().__init__("syslog")
        self._opkg_helper = opkg_helper
        self.syslog_conf_path = "/etc/syslog-ng/syslog-ng.conf"

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring syslog-ng...")
        dry_run: bool = args.dry_run

        # Check if syslog-ng is already installed
        if not self._opkg_helper.is_installed("syslog-ng"):
            self._opkg_helper.install("syslog-ng")

        if not dry_run:
            # Enable persistent storage
            logger.debug("Enabling persistent log storage...")
            _cmd(
                "nirtcfg",
                "--set",
                'section=SystemSettings,token=PersistentLogs.enabled,value="True"',
            )

            # Restart syslog-ng service
            logger.debug("Restarting syslog-ng service...")
            _cmd("/etc/init.d/syslog", "restart")

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying syslog-ng configuration...")
        valid: bool = True

        # Check if syslog-ng is setup to log in /var/log
        if not self._opkg_helper.is_installed("syslog-ng"):
            logger.error("Required syslog-ng package is not installed.")
            valid = False

        # Check ownership of syslog.conf
        if not _check_owner(self.syslog_conf_path, "root"):
            logger.error(f"ERROR: {self.syslog_conf_path} is not owned by 'root'.")
            valid = False

        return valid
