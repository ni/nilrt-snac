import argparse
import subprocess

from nilrt_snac._configs._base_config import _BaseConfig

from nilrt_snac import logger, SNAC_DATA_DIR
from nilrt_snac.opkg import opkg_helper


class _NIAuthConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        print("Removing NIAuth...")
        dry_run: bool = args.dry_run
        self._opkg_helper.remove("ni-auth", force_essential=True, force_depends=True)
        self._opkg_helper.remove("niacctbase-sudo")
        if not self._opkg_helper.is_installed("nilrt-snac-conflicts"):
            self._opkg_helper.install(str(SNAC_DATA_DIR / "nilrt-snac-conflicts.ipk"))

        logger.debug("Removing root password")
        if not dry_run:
            subprocess.run(["passwd", "-d", "root"], check=True)
        else:
            print("Dry run: would have run passwd -d root")

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying NIAuth...")
        valid = True
        if self._opkg_helper.is_installed("ni-auth"):
            valid = False
            logger.error("FOUND: ni-auth installed")
        if self._opkg_helper.is_installed("niacctbase-sudo"):
            valid = False
            logger.error("FOUND: niacctbase-sudo installed")
        if not self._opkg_helper.is_installed("nilrt-snac-conflicts"):
            valid = False
            logger.error("MISSING: nilrt-snac-conflicts not installed")
        return valid
