import grp
import os
import pathlib
import stat

from nilrt_snac._logging import run_with_logging


def _check_group_ownership(path: str, group: str) -> bool:
    "Checks if the group ownership of a file or directory matches the specified group."
    stat_info = os.stat(path)
    gid = stat_info.st_gid
    group_info = grp.getgrgid(gid)

    return group_info.gr_name == group


def _check_owner(path: str, owner: str) -> bool:
    "Checks if the owner of a file or directory matches the specified owner."
    stat_info = os.stat(path)
    uid = stat_info.st_uid
    owner_info = grp.getgrgid(uid)
    return owner_info.gr_name == owner


def _check_permissions(path: str, expected_mode: int) -> bool:
    "Checks if the permissions of a file or directory match the expected mode."
    stat_info = os.stat(path)
    return stat.S_IMODE(stat_info.st_mode) == expected_mode


def _cmd(*args: str):
    "Syntactic sugar for running shell commands with proper logging."
    run_with_logging(*args, check=True)


def get_distro():
    try:
        os_release = pathlib.Path("/etc/os-release")
        if os_release.exists():
            with open(os_release, "r") as f:
                for line in f:
                    if line.startswith("ID="):
                        return line.split("=")[1].strip()
    except NameError:
        return None
