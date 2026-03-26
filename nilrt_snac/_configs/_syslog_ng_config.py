import argparse

from nilrt_snac import logger
from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile
from nilrt_snac._common import _check_owner, _cmd
from nilrt_snac.opkg import opkg_helper


class _SyslogConfig(_BaseConfig):
    def __init__(self):
        super().__init__("syslog")
        self._opkg_helper = opkg_helper
        self.syslog_conf_path = "/etc/syslog-ng/syslog-ng.conf"
        self.logrotate_conf_path = "/etc/logrotate.conf"
        self.logrotate_dmesg_conf_path = "/etc/logrotate-dmesg.conf"
        self.logrotate_su_directive = "su root adm"

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring syslog-ng...")
        dry_run: bool = args.dry_run

        # Check if syslog-ng is already installed
        if not self._opkg_helper.is_installed("syslog-ng"):
            self._opkg_helper.install("syslog-ng")

        logrotate_conf = _ConfigFile(self.logrotate_conf_path)
        if logrotate_conf.exists() and not logrotate_conf.contains(self.logrotate_su_directive):
            logger.debug("Adding 'su root adm' directive to logrotate.conf...")
            logrotate_conf.update(
                r"(include\s+/etc/logrotate\.d)",
                f"{self.logrotate_su_directive}\n\n\\g<1>",
            )
            logrotate_conf.save(dry_run)

        logrotate_dmesg_conf = _ConfigFile(self.logrotate_dmesg_conf_path)
        if logrotate_dmesg_conf.exists() and not logrotate_dmesg_conf.contains(self.logrotate_su_directive):
            logger.debug("Adding 'su root adm' directive to logrotate-dmesg.conf...")
            logrotate_dmesg_conf.update(
                r"(\n/var/log/dmesg)",
                f"\n\n{self.logrotate_su_directive}\n\n\\g<1>",
            )
            logrotate_dmesg_conf.save(dry_run)

        if not dry_run:
            # Enable persistent storage
            logger.debug("Enabling persistent log storage...")
            _cmd(
                "nirtcfg",
                "--set",
                "section=SystemSettings,token=PersistentLogs.enabled,value=True",
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

        # Check that logrotate is configured to use root:adm for rotation
        logrotate_conf = _ConfigFile(self.logrotate_conf_path)
        if not logrotate_conf.exists():
            logger.error(f"MISSING: {self.logrotate_conf_path} not found.")
            valid = False
        elif not logrotate_conf.contains(self.logrotate_su_directive):
            logger.error(
                f"MISSING: '{self.logrotate_su_directive}' directive not found in "
                f"{self.logrotate_conf_path}. Logrotate will skip /var/log files "
                "due to insecure parent directory permissions (root:adm)."
            )
            valid = False

        logrotate_dmesg_conf = _ConfigFile(self.logrotate_dmesg_conf_path)
        if not logrotate_dmesg_conf.exists():
            logger.error(f"MISSING: {self.logrotate_dmesg_conf_path} not found.")
            valid = False
        elif not logrotate_dmesg_conf.contains(self.logrotate_su_directive):
            logger.error(
                f"MISSING: '{self.logrotate_su_directive}' directive not found in "
                f"{self.logrotate_dmesg_conf_path}. Logrotate will skip /var/log/dmesg "
                "due to insecure parent directory permissions (root:adm)."
            )
            valid = False

        return valid
