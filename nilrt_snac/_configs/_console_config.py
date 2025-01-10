import argparse
import subprocess

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac.opkg import opkg_helper as opkg

from nilrt_snac import logger


class _ConsoleConfig(_BaseConfig):
    def __init__(self):
        pass  # Nothing to do for now

    def configure(self, args: argparse.Namespace) -> None:
        print("Deconfiguring console access...")

        if not args.dry_run:
            subprocess.run(
                ["nirtcfg", "--set", "section=systemsettings,token=consoleout.enabled,value=False"],
                check=True,
            )
        else:
            print("Dry run: would have run nirtcfg --set section=systemsettings,token=consoleout.enabled,value=False")
        opkg.remove("sysconfig-settings-console", force_depends=True)

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying console access configuration...")
        valid = True
        if not args.dry_run:
            result = subprocess.run(
                ["nirtcfg", "--get", "section=systemsettings,token=consoleout.enabled"],
                check=True,
                stdout=subprocess.PIPE,
            )
            if result.stdout.decode().strip() != "False":
                valid = False
                logger.error("FOUND: console access not diabled")
        else:
            print("Dry run: would have run nirtcfg --get section=systemsettings,token=consoleout.enabled")
        if opkg.is_installed("sysconfig-settings-console"):
            valid = False
            logger.error("FOUND: sysconfig-settings-console still installed.")
        return valid
