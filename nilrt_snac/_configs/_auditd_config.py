import argparse
import grp
import os
import re
import socket
import stat
import subprocess
from typing import List

from nilrt_snac import logger
from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import EqualsDelimitedConfigFile, _ConfigFile
from nilrt_snac.opkg import opkg_helper

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

def format_email_template_text(audit_email: str) -> str:
    return f"""
    #!/usr/bin/perl
    use strict;
    use warnings;
    use Net::SMTP;

    # Configuration
    my $smtp_server = 'smtp.yourisp.com';
    my $smtp_user = 'your_email@domain.com';
    my $smtp_pass = 'your_password';
    my $from = 'your_email@domain.com';
    my $to = '{audit_email}';
    my $subject = 'Audit Alert';
    my $body = "A critical audit event has been triggered: $ARGV[0]";

    # Create SMTP object
    my $smtp = Net::SMTP->new($smtp_server, Timeout => 60)
        or die "Could not connect to SMTP server: $!";

    # Authenticate
    $smtp->auth($smtp_user, $smtp_pass)
        or die "SMTP authentication failed: $!";

    # Send email
    $smtp->mail($from)
        or die "Error setting sender: $!";
    $smtp->to($to)
        or die "Error setting recipient: $!";
    $smtp->data()
        or die "Error starting data: $!";
    $smtp->datasend("To: $to\\n");
    $smtp->datasend("From: $from\\n");
    $smtp->datasend("Subject: $subject\\n");
    $smtp->datasend("\\n");
    $smtp->datasend("$body\\n");
    $smtp->dataend()
        or die "Error ending data: $!";
    $smtp->quit;
    """

def is_valid_email(email: str) -> bool:
    "Validates an email address."
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+$'
    return re.match(email_regex, email) is not None



class _AuditdConfig(_BaseConfig):
    def __init__(self):
        self._opkg_helper = opkg_helper
        self.log_path = os.path.realpath('/var/log')
        self.audit_config_path = '/etc/audit/auditd.conf'

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring auditd...")
        auditd_config_file = EqualsDelimitedConfigFile(self.audit_config_path)
        dry_run: bool = args.dry_run

        # Check if auditd is already installed
        if not self._opkg_helper.is_installed("auditd"):
            self._opkg_helper.install("auditd")
        
        #Ensure proper groups exist
        groups_required = ["adm", "sudo"]
        ensure_proper_groups(groups_required)

        # Prompt for email if not provided
        audit_email = args.audit_email
        unattended_bypass = args.yes
        if not audit_email:
            audit_email = auditd_config_file.get("action_mail_acct")
        if not is_valid_email(audit_email) and not unattended_bypass:
            audit_email = input("Please enter your audit email address: ")
        else:
            # Use local default e-mail
            audit_email = f"root@{socket.gethostname()}"

        if is_valid_email(audit_email):
            auditd_config_file.update(r'^action_mail_acct\s*=.*$', f'action_mail_acct = {audit_email}')
            
            # Install recommended SMTP package dependency
            if not self._opkg_helper.is_installed("perl-module-net-smtp"):
                self._opkg_helper.install("perl-module-net-smtp")
           
            # Install auditd plugin package to allow for watch scripts to be used
            if not self._opkg_helper.is_installed("audispd-plugins"):
                self._opkg_helper.install("audispd-plugins")
            
            # Create template audit rule script to send email alerts
            audit_rule_script_path = '/etc/audit/audit_email_alert.pl'
            if not os.path.exists(audit_rule_script_path):
                audit_rule_script = format_email_template_text(audit_email)
                
                with open(audit_rule_script_path, "w") as file:
                    file.write(audit_rule_script)
                
                # Set the appropriate permissions
                _cmd("chown", "root:sudo", audit_rule_script_path)
                _cmd("chmod", "700", audit_rule_script_path)
            
            audit_email_conf_path = '/etc/audit/plugins.d/audit_email_alert.conf'
            if not os.path.exists(audit_email_conf_path):
                audit_email_config = """
                active = yes
                direction = out
                path = {audit_rule_script_path}
                type = always
                """.format(audit_rule_script_path=audit_rule_script_path)

                with open(audit_email_conf_path, "w") as file:
                    file.write(audit_email_config)
                
                # Set the appropriate permissions
                audit_email_file = _ConfigFile(audit_email_conf_path)
                audit_email_file.chown("root", "sudo")
                audit_email_file.chmod(0o600)
                audit_email_file.save(dry_run)


        # Set the appropriate permissions to allow only root and the 'sudo' group to read/write
        auditd_config_file.chown("root", "sudo")
        auditd_config_file.chmod(0o660)
        auditd_config_file.save(dry_run)

        # Enable and start auditd service
        if not os.path.exists("/etc/rc2.d/S20auditd"):
            _cmd("update-rc.d", "auditd", "defaults")
        _cmd("service", "auditd", "restart")

        # Set the appropriate permissions to allow only root and the 'adm' group to write/read
        _cmd('chown', '-R', 'root:adm', self.log_path)
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