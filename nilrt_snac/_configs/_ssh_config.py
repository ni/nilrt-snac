import argparse

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile

from nilrt_snac import logger


class _SshConfig(_BaseConfig):
    def __init__(self):
        super().__init__("ssh")
        self.ssh_config_path = "/etc/ssh/sshd_config"
        self.tmout_config_path = "/etc/profile.d/tmout.sh"
        self.client_alive_interval = "ClientAliveInterval 15"
        self.client_alive_count_max = "ClientAliveCountMax 4"
        self.tmout = "TMOUT=600"

    def configure(self, args: argparse.Namespace) -> None:
        sshd_config_file = _ConfigFile(self.ssh_config_path)
        tmout_config_file = _ConfigFile(self.tmout_config_path)
        dry_run: bool = args.dry_run

        if not sshd_config_file.contains_exact(self.client_alive_interval):
            if sshd_config_file.contains("ClientAliveInterval"):
                sshd_config_file.update("ClientAliveInterval.*", self.client_alive_interval)
            else:
                sshd_config_file.add(self.client_alive_interval)

        if not sshd_config_file.contains_exact(self.client_alive_count_max):
            if sshd_config_file.contains("ClientAliveCountMax"):
                sshd_config_file.update("ClientAliveCountMax.*", self.client_alive_count_max)
            else:
                sshd_config_file.add(self.client_alive_count_max)
        sshd_config_file.save(dry_run)

        if not tmout_config_file.contains_exact(self.tmout):
            if tmout_config_file.contains("TMOUT"):
                tmout_config_file.update("TMOUT.*", self.tmout)
            else:
                tmout_config_file.add(self.tmout)
        tmout_config_file.save(dry_run)

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying ssh configuration...")
        sshd_config_file = _ConfigFile("/etc/ssh/sshd_config")
        tmout_config_file = _ConfigFile("/etc/profile.d/tmout.sh")
        valid = True
        if not sshd_config_file.exists():
            valid = False
            logger.error(f"MISSING: {sshd_config_file.path} not found")
        elif not sshd_config_file.contains_exact(self.client_alive_interval):
            valid = False
            logger.error("MISSING: expected ClientAliveInterval value")
        elif not sshd_config_file.contains_exact(self.client_alive_count_max):
            valid = False
            logger.error("MISSING: expected ClientAliveCountMax value")
        if not tmout_config_file.exists():
            valid = False
            logger.error(f"MISSING: {tmout_config_file.path} not found")
        elif not tmout_config_file.contains_exact(self.tmout):
            valid = False
            logger.error("MISSING: expected TMOUT value")
        return valid
