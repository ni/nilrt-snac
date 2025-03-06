import argparse

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile

from nilrt_snac import logger


class _SshConfig(_BaseConfig):
    def __init__(self):
        pass  # Nothing to do for now

    def configure(self, args: argparse.Namespace) -> None:
        pass  # Nothing to do for now

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying ssh configuration...")
        sshd_config_file = _ConfigFile("/etc/ssh/sshd_config")
        tmout_config_file = _ConfigFile("/etc/profile.d/tmout.sh")
        valid = True
        if not sshd_config_file.exists():
            valid = False
            logger.error(f"MISSING: {sshd_config_file.path} not found")
        elif not sshd_config_file.contains_exact("ClientAliveInterval 15"):
            valid = False
            logger.error("MISSING: expected ClientAliveInterval value")
        elif not sshd_config_file.contains_exact("ClientAliveCountMax 4"):
            valid = False
            logger.error("MISSING: expected ClientAliveCountMax value")
        if not tmout_config_file.exists():
            valid = False
            logger.error(f"MISSING: {tmout_config_file.path} not found")
        elif not tmout_config_file.contains_exact("TMOUT=600"):
            valid = False
            logger.error("MISSING: expected TMOUT value")
        return valid
