import argparse
import subprocess
import re
from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile
from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper

def _cmd(*args: str):
    "Syntactic sugar for running shell commands."
    subprocess.run(args, check=True)

def is_valid_email(email: str) -> bool:
    "Validates an email address."
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None

def _check_service_status(service: str) -> bool:
    "Verifies if a service is active."
    status = subprocess.getoutput(f"systemctl is-active {service}")
    if status == "active":
        return True
    logger.error(f"ERROR: {service} is not active.")
    return False

def _check_audit_rule(rule: str) -> bool:
    "Verifies if an audit rule is present."
    rules = subprocess.getoutput("auditctl -l")
    if rule in rules:
        return True
    logger.error(f"ERROR: Audit rule {rule} is not present.")
    return False

class _AuditdConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring auditd...")
        auditd_config_file = _ConfigFile("/etc/audit/auditd.conf")
        log_path = '/var/log'

        dry_run: bool = args.dry_run
        if dry_run:
            return

        # Check if auditd is already installed
        if not self._opkg_helper.is_installed("auditd"):
            self._opkg_helper.install("auditd")

        # Enable and start auditd service
        _cmd("update-rc.d", "auditd", "defaults")
        _cmd("service", "auditd", "start")

        # Prompt for email if not provided
        audit_email = args.audit_email
        if not audit_email:
            audit_email = auditd_config_file.get("action_mail_acct")
        while not is_valid_email(audit_email):
            audit_email = input("Please enter your audit email address: ")

        # Set the action_mail_acct attribute in auditd.conf
        _cmd("sed", "-i", f"/^action_mail_acct/ c\\action_mail_acct = {audit_email}", "/etc/audit/auditd.conf")

        # Change the group ownership of the log files and directories to 'adm'
        _cmd('sudo', 'chown', '-R', 'root:adm', log_path)
        print("Changed group ownership to 'adm'.")

        # Set the appropriate permissions to allow only root and the 'adm' group to write
        _cmd('sudo', 'chmod', '-R', '770', log_path)
        print("Set permissions to 770.")

        # Ensure new log files created by the system inherit these permissions
        _cmd('sudo', 'setfacl', '-d', '-m', 'g:adm:rwx', log_path)
        _cmd('sudo', 'setfacl', '-d', '-m', 'o::0', log_path)
        print("Set default ACLs for new files and directories.")

        # Change the group ownership of the auditd.conf file to 'sudo'
        _cmd('sudo', 'chown', 'root:sudo', '/etc/audit/auditd.conf')
        print("Changed group ownership to 'sudo'.")

        # Set the appropriate permissions to allow only root and the 'sudo' group to read and write
        _cmd('sudo', 'chmod', '660', '/etc/audit/auditd.conf')
        print("Set permissions to 660.")
    




    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying auditd configuration...")
        valid: bool = True

        # Check if auditd service is running
        valid = valid and _check_service_status("auditd")

        return valid