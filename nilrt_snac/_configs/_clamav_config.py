import argparse
import os
import pathlib

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile

from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper


class _ClamAVConfig(_BaseConfig):
    """ClamAV configuration handler."""

    def __init__(self):
        super().__init__("clamav")
        self.clamd_config_path = "/etc/clamav/clamd.conf"
        self.freshclam_config_path = "/etc/clamav/freshclam.conf"
        self.virus_db_path = "/var/lib/clamav/"
        self.package_names = ["clamav", "clamav-daemon", "clamav-freshclam"]
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        """ClamAV must be installed manually by the user."""
        # Check if any ClamAV package is installed
        installed_packages = [pkg for pkg in self.package_names if self._opkg_helper.is_installed(pkg)]
        if not installed_packages:
            print("ClamAV configuration: Manual installation required")

    def verify(self, args: argparse.Namespace) -> bool:
        """Verify ClamAV configuration if any ClamAV package is installed."""
        # Check if any ClamAV package is installed
        installed_packages = [pkg for pkg in self.package_names if self._opkg_helper.is_installed(pkg)]
        
        if installed_packages:
            print("Verifying clamav configuration...")
            valid = True
            
            # Check DNS configuration (critical for freshclam)
            resolv_conf_path = "/var/run/resolv.conf"
            if not os.path.exists(resolv_conf_path) or os.path.getsize(resolv_conf_path) == 0:
                logger.error(f"DNS not configured: {resolv_conf_path} is empty or missing")
                logger.error("freshclam will fail without DNS. Configure network/DNS before running freshclam.")
                valid = False

            # Check clamd configuration file (only if daemon package is installed)
            if self._opkg_helper.is_installed("clamav-daemon"):
                clamd_config = _ConfigFile(self.clamd_config_path)
                if not clamd_config.exists():
                    logger.warning(f"ClamAV daemon config file missing: {self.clamd_config_path}")
                elif pathlib.Path(self.clamd_config_path).stat().st_size == 0:
                    logger.warning(f"ClamAV daemon config file is empty: {self.clamd_config_path}")

            # Check freshclam configuration file
            freshclam_config = _ConfigFile(self.freshclam_config_path)
            if not freshclam_config.exists():
                logger.error(f"ClamAV freshclam config file missing: {self.freshclam_config_path}")
                valid = False
            elif pathlib.Path(self.freshclam_config_path).stat().st_size == 0:
                logger.error(f"ClamAV freshclam config file is empty: {self.freshclam_config_path}")
                valid = False

            # Check virus database directory and that signatures have been downloaded
            virus_db_dir = pathlib.Path(self.virus_db_path)
            if not virus_db_dir.exists():
                logger.error(f"ClamAV virus database directory missing: {self.virus_db_path}")
                valid = False
            else:
                # Check for signature files (typically .cvd or .cld files)
                signature_files = list(virus_db_dir.glob("*.cvd")) + list(virus_db_dir.glob("*.cld"))
                if not signature_files:
                    logger.error(f"No ClamAV signature files found in {self.virus_db_path}")
                    logger.error("Run 'freshclam' to download virus signatures")
                    valid = False
                else:
                    # Check that at least one signature file is not empty
                    valid_signatures = [f for f in signature_files if f.stat().st_size > 0]
                    if not valid_signatures:
                        logger.error("All ClamAV signature files are empty")
                        logger.error("Run 'freshclam' to download virus signatures")
                        valid = False

            if valid:
                logger.info(f"ClamAV verification passed. Found packages: {', '.join(installed_packages)}")

            return valid
        else:
            print("ClamAV is not installed; skipping verification.")
            return True