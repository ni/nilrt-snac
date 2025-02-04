import argparse
import grp
import os
import re
import stat
import subprocess
from typing import List

from nilrt_snac import logger
from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import EqualsDelimitedConfigFile, _ConfigFile
from nilrt_snac.opkg import opkg_helper

def _cmd(*args: str):
    "Syntactic sugar for running shell commands."
    subprocess.run(args, check=True)

def ensure_proper_groups(groups: List[str]) -> None:
    "Ensures the specified groups exist on the system."
    for group in groups:
        try:
            grp.getgrnam(group)
        except KeyError:
            _cmd("groupadd", group)
            logger.info(f"Group {group} created.")

def is_valid_email(email: str) -> bool:
    "Validates an email address."
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None

def _check_group_ownership(path: str, group: str) -> bool:
    "Checks if the group ownership of a file or directory matches the specified group."    
    stat_info = os.stat(path)
    gid = stat_info.st_gid
    group_info = grp.getgrgid(gid)
    
    return group_info.gr_name == group

def _check_permissions(path: str, expected_mode: int) -> bool:
    "Checks if the permissions of a file or directory match the expected mode."
    stat_info = os.stat(path)
    return stat.S_IMODE(stat_info.st_mode) == expected_mode

def _check_owner(path: str, owner: str) -> bool:
    "Checks if the owner of a file or directory matches the specified owner."
    stat_info = os.stat(path)
    uid = stat_info.st_uid
    owner_info = grp.getgrgid(uid)
    return owner_info.gr_name == owner



class _AuditdConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper
        self.log_path = os.path.realpath('/var/log')
        self.audit_config_path = '/etc/audit/auditd.conf'

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring auditd...")
        auditd_config_file = EqualsDelimitedConfigFile(self.audit_config_path)

        dry_run: bool = args.dry_run
        if dry_run:
            return

        # Check if auditd is already installed
        if not self._opkg_helper.is_installed("auditd"):
            self._opkg_helper.install("auditd")
        
        #Ensure proper groups exist
        groups_required = ["adm", "sudo"]
        ensure_proper_groups(groups_required)

        # Prompt for email if not provided
        audit_email = args.audit_email
        if not audit_email:
            audit_email = auditd_config_file.get("action_mail_acct")
        if not is_valid_email(audit_email):
            audit_email = input("Please enter your audit email address (optional): ")
        if is_valid_email(audit_email):
            auditd_config_file.update(r'^action_mail_acct\s*=.*$', f'action_mail_acct = {audit_email}')
            
            # Install recommended SMTP package dependency
            if not self._opkg_helper.is_installed("msmtp"):
                self._opkg_helper.install("msmtp")

                # Create template msmtp configuration file
                msmtp_config_path = "/etc/msmtprc"
                msmtp_config = """
                account default
                host smtp.yourisp.com
                port 587
                auth on
                user your_email@domain.com
                password your_password
                from your_email@domain.com
                tls on
                tls_trust_file /etc/ssl/certs/ca-certificates.crt
                logfile /var/log/msmtp.log
                """

                if not os.path.exists(msmtp_config_path):
                    with open(msmtp_config_path, "w") as file:
                        file.write(msmtp_config)
                    
                    # Set the appropriate permissions
                    msmtp_config_file = _ConfigFile(msmtp_config_path)
                    msmtp_config_file.chown("root", "sudo")
                    msmtp_config_file.chmod(0o660)
                    msmtp_config_file.save(dry_run)

                    print('Please add your SMTP server credentials to the msmtp configuration file at /etc/msmtprc')
                
                #Create symbolic link in order to override sendmail default location
                sendmail_default_location = '/usr/sbin/sendmail'
                msmtp_location = '/usr/bin/msmtp'
                if not os.path.islink(sendmail_default_location):
                    if os.path.exists(sendmail_default_location):
                        os.rmdir(sendmail_default_location)
                    
                    os.symlink(msmtp_location, sendmail_default_location)
                



        # Change the group ownership of the auditd.conf file to 'sudo'
        auditd_config_file.chown("root", "sudo")

        # Set the appropriate permissions to allow only root and the 'sudo' group to read/write
        auditd_config_file.chmod(0o660)
        auditd_config_file.save(dry_run)

        # Enable and start auditd service
        _cmd("update-rc.d", "auditd", "defaults")
        _cmd("service", "auditd", "start")

        # Change the group ownership of the log files and directories to 'adm'
        _cmd('chown', '-R', 'root:adm', self.log_path)

        # Set the appropriate permissions to allow only root and the 'adm' group to write/read
        _cmd('chmod', '-R', '770', self.log_path)

        # Ensure new log files created by the system inherit these permissions
        _cmd('setfacl', '-d', '-m', 'g:adm:rwx', self.log_path)
        _cmd('setfacl', '-d', '-m', 'o::0', self.log_path)
    


    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying auditd configuration...")
        valid: bool = True

        # Check if auditd is installed
        valid = valid and self._opkg_helper.is_installed("auditd")

        # Check if auditd config
        auditd_config_file = EqualsDelimitedConfigFile(self.audit_config_path)
        if not auditd_config_file.exists():
            valid = False
            logger.error(f"MISSING: {auditd_config_file.path} not found")
        elif not is_valid_email(auditd_config_file.get("action_mail_acct")):
            valid = False
            logger.error("MISSING: expected action_mail_acct value")

        # Check group ownership and permissions of auditd.conf
        if not _check_group_ownership(self.audit_config_path, "sudo"):
            logger.error(f"ERROR: {self.audit_config_path} is not owned by the 'sudo' group.")
            valid = False
        if not _check_permissions(self.audit_config_path, 0o660):
            logger.error(f"ERROR: {self.audit_config_path} does not have 660 permissions.")
            valid = False
        if not _check_owner(self.audit_config_path, "root"):
            logger.error(f"ERROR: {self.audit_config_path} is not owned by 'root'.")
            valid = False

        # Check group ownership and permissions of /var/log
        if not _check_group_ownership(self.log_path, "adm"):
            logger.error(f"ERROR: {self.log_path} is not owned by the 'adm' group.")
            valid = False
        if not _check_permissions(self.log_path, 0o770):
            logger.error(f"ERROR: {self.log_path} does not have 770 permissions.")
            valid = False
        if not _check_owner(self.log_path, "root"):
            logger.error(f"ERROR: {self.log_path} is not owned by 'root'.")
            valid = False

        return valid