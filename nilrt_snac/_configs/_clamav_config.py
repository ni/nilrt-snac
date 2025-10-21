import argparse
import os
import pathlib

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile

from nilrt_snac import logger
from nilrt_snac.opkg import opkg_helper


class _ClamAVConfig(_BaseConfig):
    """ClamAV configuration handler."""

    def __init__(self):
        super().__init__("clamav")
        self.clamd_config_path = "/etc/clamav/clamd.conf"
        self.freshclam_config_path = "/etc/clamav/freshclam.conf"
        self.virus_db_path = "/var/lib/clamav/"
        self.package_names = ["clamav", "clamav-daemon", "clamav-freshclam"]
        self._opkg_helper = opkg_helper

    def configure(self, args: argparse.Namespace) -> None:
        """Configure ClamAV installation and setup."""
        # Check if any ClamAV package is installed
        installed_packages = [pkg for pkg in self.package_names if self._opkg_helper.is_installed(pkg)]
        
        if not installed_packages:
            print("Installing ClamAV packages...")
            self._install_clamav_packages()
            # Fix any DNS issues caused by ClamAV installation
            self._fix_dns_configuration()
        else:
            print(f"ClamAV packages already installed: {', '.join(installed_packages)}")
        
        # Configure ClamAV after installation
        self._configure_clamav_files()
        self._create_wrapper_script()
        
        print("\n" + "="*60)
        print("CLAMAV INSTALLATION COMPLETED")
        print("="*60)
        print("* ClamAV packages installed")
        print("* Configuration files created")
        print("* Manual-only operation configured")
        print("* Wrapper script created: /usr/local/bin/clamav-scan")
        print()
        print(" VIRUS SIGNATURES NOT INSTALLED")
        print("ClamAV requires virus signature databases to function.")
        print()
        print("TO INSTALL VIRUS SIGNATURES, CHOOSE ONE METHOD:")
        print()
        print("1. ONLINE METHOD (if network available):")
        print("   sudo freshclam")
        print()
        print("2. OFFLINE METHOD (using IPK packages):")
        print("   - Download clamav-db-*.ipk from your package source")
        print("   - Copy to target system")
        print("   - Install: sudo opkg install clamav-db-*.ipk")
        print()
        print("3. MANUAL FILE COPY:")
        print("   - Copy *.cvd and *.cld files to /var/lib/clamav/")
        print("   - Set ownership: sudo chown clamav:clamav /var/lib/clamav/*")
        print()
        print("USAGE AFTER SIGNATURE INSTALLATION:")
        print("- To scan: sudo clamav-scan")
        print("- To update signatures: sudo freshclam")
        print("- To verify installation: nilrt-snac verify clamav")
        print("="*60)

    def verify(self, args: argparse.Namespace) -> bool:
        """Verify ClamAV configuration if any ClamAV package is installed."""
        # Check if any ClamAV package is installed
        installed_packages = [pkg for pkg in self.package_names if self._opkg_helper.is_installed(pkg)]
        
        if installed_packages:
            print("Verifying clamav configuration...")
            valid = True

            # Check clamd configuration file
            clamd_config = _ConfigFile(self.clamd_config_path)
            if not clamd_config.exists():
                logger.error(f"ClamAV daemon config file missing: {self.clamd_config_path}")
                valid = False
            elif pathlib.Path(self.clamd_config_path).stat().st_size == 0:
                logger.error(f"ClamAV daemon config file is empty: {self.clamd_config_path}")
                valid = False

            # Check freshclam configuration file
            freshclam_config = _ConfigFile(self.freshclam_config_path)
            if not freshclam_config.exists():
                logger.error(f"ClamAV freshclam config file missing: {self.freshclam_config_path}")
                valid = False
            elif pathlib.Path(self.freshclam_config_path).stat().st_size == 0:
                logger.error(f"ClamAV freshclam config file is empty: {self.freshclam_config_path}")
                valid = False

            # Check virus database directory and warn about missing signatures
            virus_db_dir = pathlib.Path(self.virus_db_path)
            if not virus_db_dir.exists():
                logger.warning(f"ClamAV virus database directory missing: {self.virus_db_path}")
                logger.warning("ClamAV requires virus signatures to function properly.")
                self._show_signature_installation_instructions()
            else:
                # Check for signature files (typically .cvd or .cld files)
                signature_files = list(virus_db_dir.glob("*.cvd")) + list(virus_db_dir.glob("*.cld"))
                if not signature_files:
                    logger.warning(f"No ClamAV signature files found in {self.virus_db_path}")
                    logger.warning("ClamAV requires virus signatures to function properly.")
                    self._show_signature_installation_instructions()
                else:
                    # Check that at least one signature file is not empty
                    valid_signatures = [f for f in signature_files if f.stat().st_size > 0]
                    if not valid_signatures:
                        logger.warning("All ClamAV signature files are empty or invalid")
                        logger.warning("ClamAV requires valid virus signatures to function properly.")
                        self._show_signature_installation_instructions()
                    else:
                        logger.info(f"ClamAV signatures found: {len(valid_signatures)} files")

            if valid:
                logger.info(f"ClamAV verification passed. Found packages: {', '.join(installed_packages)}")

            return valid
        else:
            print("ClamAV is not installed; skipping verification.")
            return True

    def _install_clamav_packages(self) -> None:
        """Install ClamAV packages using opkg."""
        try:
            # Backup DNS configuration before installation
            self._backup_dns_configuration()
            
            # Update package list first
            print("Updating package list...")
            self._opkg_helper.update()
            
            # Install core ClamAV packages
            for package in self.package_names:
                if not self._opkg_helper.is_installed(package):
                    try:
                        print(f"Installing {package}...")
                        self._opkg_helper.install(package)
                        logger.info(f"Successfully installed {package}")
                    except Exception as e:
                        logger.warning(f"Failed to install {package}: {e}")
                        # Continue with other packages even if one fails
                        continue
        except Exception as e:
            logger.error(f"Failed to install ClamAV packages: {e}")
            raise

    def _configure_clamav_files(self) -> None:
        """Configure ClamAV configuration files."""
        # Ensure directories exist
        os.makedirs("/etc/clamav", exist_ok=True)
        os.makedirs("/var/lib/clamav", exist_ok=True)
        
        # Set proper ownership and permissions for directories
        try:
            import pwd
            import grp
            clamav_uid = pwd.getpwnam("clamav").pw_uid
            clamav_gid = grp.getgrnam("clamav").gr_gid
            
            # Set ownership and make directories writable
            os.chown("/var/lib/clamav", clamav_uid, clamav_gid)
            os.chmod("/var/lib/clamav", 0o755)
            
            # Create freshclam log file with proper ownership
            freshclam_log = "/var/lib/clamav/freshclam.log"
            if not os.path.exists(freshclam_log):
                with open(freshclam_log, 'w') as f:
                    f.write("# ClamAV freshclam log file\n")
                os.chown(freshclam_log, clamav_uid, clamav_gid)
                os.chmod(freshclam_log, 0o644)
                
        except (KeyError, OSError) as e:
            logger.warning(f"Could not set clamav ownership: {e}")
            # As fallback, make directories world-writable for manual operation
            try:
                os.chmod("/var/lib/clamav", 0o777)
                logger.info("Set /var/lib/clamav to world-writable as fallback")
            except Exception:
                pass
        
        # Configure freshclam.conf if it doesn't exist or is minimal
        self._setup_freshclam_config()
        
        # Configure clamd.conf if it doesn't exist or is minimal
        self._setup_clamd_config()
        
        # Disable automatic daemon startup
        self._disable_automatic_services()

    def _setup_freshclam_config(self) -> None:
        """Setup freshclam configuration file."""
        freshclam_config_content = """# Freshclam configuration for NILRT (Manual mode)
DatabaseDirectory /var/lib/clamav
UpdateLogFile /var/lib/clamav/freshclam.log
LogVerbose yes
LogSyslog no
LogFacility LOG_LOCAL6
DatabaseOwner clamav
DNSDatabaseInfo current.cvd.clamav.net
DatabaseMirror db.local.clamav.net
DatabaseMirror database.clamav.net
MaxAttempts 5
ScriptedUpdates yes
CompressLocalDatabase no
Bytecode yes
NotifyClamd /etc/clamav/clamd.conf
# MANUAL MODE: Automatic updates disabled - signatures must be updated manually
# To enable automatic updates, uncomment the line below and set desired frequency
# Checks 24
TestDatabases yes
"""
        
        try:
            with open(self.freshclam_config_path, 'w') as f:
                f.write(freshclam_config_content)
            os.chmod(self.freshclam_config_path, 0o644)
            logger.info(f"Created freshclam configuration: {self.freshclam_config_path}")
        except Exception as e:
            logger.error(f"Failed to create freshclam config: {e}")

    def _setup_clamd_config(self) -> None:
        """Setup clamd configuration file."""
        clamd_config_content = """# ClamAV daemon configuration for NILRT
LogFile /var/lib/clamav/clamd.log
LogTime yes
LogFileUnlock yes
LogVerbose yes
LogSyslog yes
LogFacility LOG_LOCAL6
PidFile /var/run/clamav/clamd.pid
DatabaseDirectory /var/lib/clamav
LocalSocket /var/run/clamav/clamd.ctl
LocalSocketGroup clamav
LocalSocketMode 666
User clamav
AllowSupplementaryGroups yes
TemporaryDirectory /tmp
ScanMail yes
ScanArchive yes
ArchiveBlockEncrypted no
MaxDirectoryRecursion 15
FollowDirectorySymlinks no
FollowFileSymlinks no
ReadTimeout 180
MaxThreads 12
MaxConnectionQueueLength 15
StreamMaxLength 25M
MaxFiles 10000
MaxRecursion 16
MaxFileSize 25M
MaxScanSize 100M
OnAccessMaxFileSize 5M
AllowAllMatchScan yes
ForceToDisk no
DisableCertCheck no
DisableCache no
MaxScanTime 120000
MaxZipTypeRcg 1M
MaxPartitions 50
MaxIconsPE 100
PCREMatchLimit 10000
PCRERecMatchLimit 5000
PCREMaxFileSize 25M
ScanXMLDOCS yes
ScanHWP3 yes
MaxEmbeddedPE 10M
MaxHTMLNormalize 10M
MaxHTMLNoTags 2M
MaxScriptNormalize 5M
MaxZipAdvertising 25M
AlertBrokenExecutables no
AlertBrokenMedia no
AlertEncrypted no
AlertEncryptedArchive no
AlertEncryptedDoc no
AlertMacros no
AlertOLE2Macros no
AlertPhishingSSLMismatch no
AlertPhishingCloak no
AlertPartitionIntersection no
PreludeEnable no
PreludeAnalyzerName ClamAV
DetectPUA no
ExcludePUA NetTool
ExcludePUA PWTool
IncludePUA Spy
IncludePUA Scanner
IncludePUA Rootkit
HeuristicScanPrecedence no
StructuredDataDetection no
CommandReadTimeout 30
SendBufTimeout 200
MaxQueue 100
IdleTimeout 30
ExitOnOOM no
LeaveTemporaryFiles no
AlgorithmicDetection yes
ScanPE yes
ScanELF yes
ScanOLE2 yes
ScanPDF yes
ScanSWF yes
PhishingSignatures yes
PhishingScanURLs yes
PhishingAlwaysBlockSSLMismatch no
PhishingAlwaysBlockCloak no
PartitionIntersection no
DetectBrokenExecutables no
ScanPartialMessages no
HeuristicAlerts yes
StructuredMinCreditCardCount 3
StructuredMinSSNCount 3
StructuredSSNFormatNormal yes
StructuredSSNFormatStripped yes
ScanHTML yes
MaxRecHWP3 16
"""
        
        try:
            with open(self.clamd_config_path, 'w') as f:
                f.write(clamd_config_content)
            os.chmod(self.clamd_config_path, 0o644)
            logger.info(f"Created clamd configuration: {self.clamd_config_path}")
        except Exception as e:
            logger.error(f"Failed to create clamd config: {e}")



    def _disable_automatic_services(self) -> None:
        """Disable automatic ClamAV services to ensure manual-only operation."""
        try:
            import subprocess
            
            # Disable clamav-daemon service (if it exists)
            try:
                subprocess.run(['systemctl', 'disable', 'clamav-daemon'], 
                             capture_output=True, check=False)
                subprocess.run(['systemctl', 'stop', 'clamav-daemon'], 
                             capture_output=True, check=False)
                print("✓ ClamAV daemon service disabled")
            except Exception:
                pass  # Service might not exist or systemctl not available
            
            # Disable clamav-freshclam service (if it exists)  
            try:
                subprocess.run(['systemctl', 'disable', 'clamav-freshclam'], 
                             capture_output=True, check=False)
                subprocess.run(['systemctl', 'stop', 'clamav-freshclam'], 
                             capture_output=True, check=False)
                print("✓ ClamAV freshclam service disabled")
            except Exception:
                pass  # Service might not exist or systemctl not available
                
            # Also try with update-rc.d for SysV init systems
            try:
                subprocess.run(['update-rc.d', 'clamav-daemon', 'disable'], 
                             capture_output=True, check=False)
                subprocess.run(['update-rc.d', 'clamav-freshclam', 'disable'], 
                             capture_output=True, check=False)
            except Exception:
                pass  # update-rc.d might not be available
                
            print("ClamAV configured for manual operation only.")
            print("To start scanning manually, use: sudo clamav-scan")
            
        except Exception as e:
            logger.warning(f"Could not disable automatic services: {e}")

    def _backup_dns_configuration(self) -> None:
        """Backup DNS configuration before ClamAV installation."""
        resolv_conf_path = "/etc/resolv.conf"
        backup_path = "/etc/resolv.conf.nilrt-backup"
        
        try:
            if os.path.exists(resolv_conf_path) and not os.path.exists(backup_path):
                # If it's a regular file, backup the content
                if os.path.isfile(resolv_conf_path) and not os.path.islink(resolv_conf_path):
                    import shutil
                    shutil.copy2(resolv_conf_path, backup_path)
                    logger.info("Backed up existing /etc/resolv.conf")
                # If it's a working symlink, backup the target content
                elif os.path.islink(resolv_conf_path) and os.path.exists(resolv_conf_path):
                    with open(resolv_conf_path, 'r') as src, open(backup_path, 'w') as dst:
                        dst.write(src.read())
                    logger.info("Backed up DNS configuration from symlink target")
        except Exception as e:
            logger.warning(f"Could not backup DNS configuration: {e}")

    def _fix_dns_configuration(self) -> None:
        """Fix DNS configuration issues that ClamAV installation might cause."""
        resolv_conf_path = "/etc/resolv.conf"
        backup_path = "/etc/resolv.conf.nilrt-backup"
        
        try:
            # Check if resolv.conf is broken or missing
            needs_fix = False
            
            if not os.path.exists(resolv_conf_path):
                logger.warning("/etc/resolv.conf missing after ClamAV installation")
                needs_fix = True
            elif os.path.islink(resolv_conf_path) and not os.path.exists(resolv_conf_path):
                logger.warning("Found broken /etc/resolv.conf symlink after ClamAV installation")
                os.unlink(resolv_conf_path)
                needs_fix = True
            elif os.path.isfile(resolv_conf_path):
                # Check if file is empty or has no nameservers
                with open(resolv_conf_path, 'r') as f:
                    content = f.read()
                if not content.strip() or 'nameserver' not in content:
                    logger.warning("/etc/resolv.conf is empty or has no nameservers")
                    needs_fix = True
            
            if needs_fix:
                # Try to restore from backup first
                if os.path.exists(backup_path):
                    logger.info("Restoring DNS configuration from backup")
                    import shutil
                    shutil.copy2(backup_path, resolv_conf_path)
                else:
                    # Create a functional resolv.conf with reliable DNS servers
                    logger.info("Creating new DNS configuration")
                    with open(resolv_conf_path, 'w') as f:
                        f.write("# DNS configuration restored by nilrt-snac after ClamAV installation\n")
                        f.write("nameserver 8.8.8.8\n")
                        f.write("nameserver 8.8.4.4\n")
                        f.write("nameserver 1.1.1.1\n")
                
                # Set proper permissions
                os.chmod(resolv_conf_path, 0o644)
                logger.info("Fixed /etc/resolv.conf DNS configuration")
                
                # Test DNS resolution
                try:
                    import subprocess
                    result = subprocess.run(['nslookup', 'google.com'], 
                                          capture_output=True, timeout=5)
                    if result.returncode == 0:
                        logger.info("DNS resolution test passed")
                    else:
                        logger.warning("DNS resolution test failed, but configuration created")
                except Exception:
                    logger.info("DNS configuration created (resolution test unavailable)")
            else:
                logger.info("DNS configuration is working properly")
                
        except Exception as e:
            logger.warning(f"Could not fix DNS configuration: {e}")

    def _create_wrapper_script(self) -> None:
        """Create the ClamAV scan wrapper script."""
        wrapper_script_path = "/usr/local/bin/clamav-scan"
        os.makedirs("/usr/local/bin", exist_ok=True)
        wrapper_script_content = '''#!/bin/bash

# ClamAV Scan Wrapper Script for NILRT
# This script manages memory requirements and performs virus scanning

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root. Please use sudo."
  exit 1
fi

# Check total memory in KB and convert to MB
total_mem_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
total_mem_mb=$((total_mem_kb / 1024))
  
# Check if any swap is currently active
swap_active=$(swapon --show | wc -l)

# Create and enable swap file only if memory < 3GB and no swap is active
if [ "$total_mem_mb" -lt 3072 ] && [ "$swap_active" -eq 0 ]; then
  echo "System has ${total_mem_mb}MB memory. Creating temporary swap file for ClamAV..."
  fallocate -l 1G /temp_swapfile
  chmod 600 /temp_swapfile
  mkswap /temp_swapfile
  swapon /temp_swapfile
  swap_created=true
  echo "Temporary swap file created and activated."
else
  swap_created=false
  if [ "$total_mem_mb" -ge 3072 ]; then
    echo "System has sufficient memory (${total_mem_mb}MB) for ClamAV scan."
  else
    echo "Swap already active, proceeding with scan."
  fi
fi

# Note: Virus definitions are NOT automatically updated before scanning
# To update signatures manually, run: sudo freshclam
echo "Starting ClamAV scan with current virus definitions..."
echo "Note: To update signatures before scanning, run 'sudo freshclam' first"

# Run ClamAV scan with memory and performance optimizations
echo "Starting ClamAV virus scan..."
echo "This may take a while depending on the number of files..."

clamscan \\
  --recursive \\
  --infected \\
  --max-filesize=250M \\
  --max-scansize=250M \\
  --exclude-dir=^/sys/ \\
  --exclude-dir=^/proc/ \\
  --exclude-dir=^/dev/ \\
  --exclude-dir=^/tmp/ \\
  --exclude-dir=^/var/tmp/ \\
  --log=/var/lib/clamav/scan.log \\
  "$@"

scan_result=$?

# Clean up swap file if it was created
if [ "$swap_created" = true ]; then
  echo "Cleaning up temporary swap file..."
  swapoff /temp_swapfile
  rm /temp_swapfile
  echo "Temporary swap file removed."
fi

# Report results
case $scan_result in
  0)
    echo "Scan completed successfully. No viruses found."
    ;;
  1)
    echo "Scan completed. Viruses or suspicious files were found!"
    echo "Check /var/lib/clamav/scan.log for details."
    ;;
  *)
    echo "Scan completed with errors (exit code: $scan_result)."
    echo "Check /var/lib/clamav/scan.log for details."
    ;;
esac

exit $scan_result
'''
        
        try:
            with open(wrapper_script_path, 'w') as f:
                f.write(wrapper_script_content)
            os.chmod(wrapper_script_path, 0o755)
            logger.info(f"Created ClamAV wrapper script: {wrapper_script_path}")
        except Exception as e:
            logger.error(f"Failed to create wrapper script: {e}")

    def _show_signature_installation_instructions(self) -> None:
        """Display instructions for manual signature installation."""
        logger.info("To install virus signatures, choose one method:")
        logger.info("  1. Online: sudo freshclam")
        logger.info("  2. Offline: sudo opkg install clamav-db-*.ipk")
        logger.info("  3. Manual: copy *.cvd/*.cld files to /var/lib/clamav/")