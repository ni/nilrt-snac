import os
import pathlib
import subprocess

from nilrt_snac._common import get_distro
from nilrt_snac._logging import run_with_logging
from nilrt_snac.opkg import opkg_helper

from nilrt_snac import Errors, SNACError, logger

# Check that the effective UID of this bash script is root (UID 0)
def _check_euid_root():
    print("Checking EUID")
    if os.geteuid() != 0:
        raise SNACError("This script must be run as root.", Errors.EX_BAD_ENVIRONMENT)

# Check that the script isn't executing within a safemode context
def _check_runmode():
    safe_mode = pathlib.Path("/etc/natinst/safemode")
    if safe_mode.exists():
        raise SNACError("This script cannot be run in safe mode.", Errors.EX_BAD_ENVIRONMENT)


# Check that the script is running on NI LinuxRT
def _check_nilrt():
    if get_distro() != "nilrt":
        raise SNACError("This script must be run on a NILRT system.", Errors.EX_BAD_ENVIRONMENT)


def verify_prereqs():  # noqa: D103 - Missing docstring in public function (auto-generated noqa)
    _check_euid_root()
    _check_runmode()
    _check_nilrt()
