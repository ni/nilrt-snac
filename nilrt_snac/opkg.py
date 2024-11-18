"""Class to help with managing opkg install/uninstall."""

import subprocess
from typing import List

from nilrt_snac import logger
from nilrt_snac._common import get_distro

OPKG_SNAC_CONF = "/etc/opkg/snac.conf"


class OpkgHelper:  # noqa: D101 - Missing docstring in public class (auto-generated noqa)
    def __init__(self) -> None:  # noqa: D107 - Missing docstring in __init__ (auto-generated noqa)
        self._installed_packages: List[str] = []
        # This runs before the prereqs are checked
        if get_distro() != "nilrt":
            logger.warning("Not running on nilrt, can't get list of installed packages.")
            return

        packages = self._run(["list-installed"])

        for line in packages.split("\n"):
            pkg = line.split(" - ")
            if len(pkg) > 1:
                self._installed_packages.append(pkg[0])

    def _run(  # noqa: D102 - Missing docstring in public method (auto-generated noqa)
        self, command: List[str]
    ) -> str:
        result = subprocess.run(["opkg"] + command, stdout=subprocess.PIPE)

        if result.returncode != 0:
            raise RuntimeError(
                f"Command 'opkg {' '.join(command)}' failed with return code {result.returncode}"
            )

        return result.stdout.decode()

    def set_dry_run(  # noqa: D102 - Missing docstring in public method (auto-generated noqa)
        self, dry_run: bool
    ) -> None:
        self._dry_run = dry_run

    def install(  # noqa: D102 - Missing docstring in public method (auto-generated noqa)
        self, package: str, force_reinstall: bool = False
    ) -> None:
        if not self.is_installed(package):
            cmd = ["opkg", "install"]
            if force_reinstall:
                cmd.append("--force-reinstall")
            cmd.append(package)
            if not self._dry_run:
                subprocess.run(cmd, check=True)
            self._installed_packages.append(package)
        else:
            logger.debug(f"{package} already installed")

    def remove(
        self,
        package: str,
        autoremove: bool = False,
        ignore_installed = False,
        force_essential: bool = False,
        force_depends: bool = False,
    ) -> None:
        """Remove (de-install) packages from the system."""

        logger.info(f"Removing IPK: {package}")

        # Bail out if the package is not installed.
        if not ignore_installed and not self.is_installed(package):
            logger.debug(f"{package} already uninstalled")
            return

        cmd = ["opkg", "remove"]

        if autoremove:
            cmd.append("--autoremove")
        if force_essential:
            cmd.append("--force-removal-of-essential-packages")
        if force_depends:
            cmd.append("--force-depends")

        cmd.append(package)
        if not self._dry_run:
            subprocess.run(cmd, check=(not ignore_installed))
        if not ignore_installed:
            self._installed_packages.remove(package)
            

    def is_installed(  # noqa: D102 - Missing docstring in public method (auto-generated noqa)
        self, package: str
    ) -> bool:
        return package in self._installed_packages

    def update(  # noqa: D102 - Missing docstring in public method (auto-generated noqa)
        self,
    ) -> None:
        self._run(["update"])


opkg_helper = OpkgHelper()
