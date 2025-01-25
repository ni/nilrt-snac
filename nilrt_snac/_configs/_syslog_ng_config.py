import argparse
import subprocess
import os
from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile
from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper

def _cmd(*args: str):
    "Syntactic sugar for running shell commands."
    subprocess.run(args, check=True)


class _SyslogConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring syslog-ng...")
        dry_run: bool = args.dry_run
        if dry_run:
            return

        # Check if syslog-ng is already installed
        if not self._opkg_helper.is_installed("syslog-ng"):
            self._opkg_helper.install("syslog-ng")

        #Enable persistent storage
        _cmd('nirtcfg', '--set', 'section=SystemSettings,token=PersistentLogs.enabled,value="True"')

      

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying syslog-ng configuration...")
        valid: bool = True

        # Generate a test log entry
        test_message = "Test log entry for verification"
        _cmd("logger", test_message)


        # Check for the test log entry in /var/log/messages
        if valid:
            result_command = f'grep "{test_message}" /var/log/messages'
            result = subprocess.run(
                result_command,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            last_entry = result.stdout.strip().split('\n')[-1]
            if test_message not in last_entry:
                logger.error(f"ERROR: Test log entry not found.")
                valid = False
        
      

        return valid