from argparse import Namespace
from subprocess import run

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac.opkg import opkg_helper as opkg

from nilrt_snac import logger


class _GraphicalConfig(_BaseConfig):
    """The graphical configuration for SNAC is to deconfigure the X11, embedded UI, and other components that are only useful when using the graphical UI."""

    def __init__(self):
        super().__init__("graphical")

    def configure(self, args: Namespace) -> None:
        print("Deconfiguring the graphical UI...")
        if not args.dry_run:
            logger.debug("Disabling the embedded UI...")
            run(
                ["nirtcfg", "--set", "section=systemsettings,token=ui.enabled,value=False"],
                check=True,
            )

        opkg.remove("packagegroup-ni-graphical", autoremove=True)
        opkg.remove("packagegroup-core-x11", autoremove=True)

    def verify(self, args: Namespace) -> bool:
        print("Verifying Graphical configuration...")
        valid = True
        for check_package in [
            "packagegroup-ni-graphical",
            "packagegroup-core-x11",
            "packagegroup-ni-xfce",
            "sysconfig-settings-ui",
        ]:
            if opkg.is_installed(check_package):
                valid = False
                logger.error(f"Found forbidden package installed: {check_package}")

        return valid
