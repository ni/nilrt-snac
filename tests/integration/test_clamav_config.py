"""Test ClamAV configuration verification."""

import argparse
import tempfile
import pathlib
from unittest.mock import Mock, patch
import pytest

from nilrt_snac._configs._clamav_config import _ClamAVConfig


class TestClamAVConfig:
    """Test cases for ClamAV configuration verification."""

    def test_configure_not_installed(self):
        """Test configure method when ClamAV is not installed."""
        config = _ClamAVConfig()
        
        # Mock opkg_helper to return False for all packages
        with patch.object(config._opkg_helper, 'is_installed', return_value=False):
            args = argparse.Namespace(dry_run=False)
            
            # This should not raise an exception
            config.configure(args)

    def test_verify_not_installed(self):
        """Test verify method when ClamAV is not installed - should pass."""
        config = _ClamAVConfig()
        
        # Mock opkg_helper to return False for all packages
        with patch.object(config._opkg_helper, 'is_installed', return_value=False):
            args = argparse.Namespace()
            result = config.verify(args)
            
            assert result is True

    def test_verify_installed_missing_config_files(self):
        """Test verify method when ClamAV is installed but config files are missing."""
        config = _ClamAVConfig()
        
        # Mock opkg_helper to return True for one ClamAV package
        with patch.object(config._opkg_helper, 'is_installed') as mock_installed:
            mock_installed.side_effect = lambda pkg: pkg == "clamav"
            
            args = argparse.Namespace()
            result = config.verify(args)
            
            # Should fail because config files don't exist
            assert result is False

    def test_verify_installed_with_valid_config(self):
        """Test verify method when ClamAV is installed with valid configuration."""
        config = _ClamAVConfig()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temporary config files and database directory
            clamd_config = pathlib.Path(tmpdir) / "clamd.conf"
            freshclam_config = pathlib.Path(tmpdir) / "freshclam.conf"
            virus_db_dir = pathlib.Path(tmpdir) / "db"
            virus_db_dir.mkdir()
            
            # Create non-empty config files
            clamd_config.write_text("# ClamAV daemon config\nLogFile /var/log/clamav/clamd.log\n")
            freshclam_config.write_text("# FreshClam config\nUpdateLogFile /var/log/clamav/freshclam.log\n")
            
            # Create a signature file
            signature_file = virus_db_dir / "main.cvd"
            signature_file.write_bytes(b"fake signature data")
            
            # Update config paths to use temporary files
            config.clamd_config_path = str(clamd_config)
            config.freshclam_config_path = str(freshclam_config)
            config.virus_db_path = str(virus_db_dir)
            
            # Mock opkg_helper to return True for one ClamAV package
            with patch.object(config._opkg_helper, 'is_installed') as mock_installed:
                mock_installed.side_effect = lambda pkg: pkg == "clamav"
                
                args = argparse.Namespace()
                result = config.verify(args)
                
                # Should pass because all required files exist and are not empty
                assert result is True

    def test_verify_installed_empty_config_files(self):
        """Test verify method when ClamAV config files exist but are empty."""
        config = _ClamAVConfig()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temporary empty config files
            clamd_config = pathlib.Path(tmpdir) / "clamd.conf"
            freshclam_config = pathlib.Path(tmpdir) / "freshclam.conf"
            virus_db_dir = pathlib.Path(tmpdir) / "db"
            virus_db_dir.mkdir()
            
            # Create empty config files
            clamd_config.write_text("")
            freshclam_config.write_text("")
            
            # Create a signature file
            signature_file = virus_db_dir / "main.cvd"
            signature_file.write_bytes(b"fake signature data")
            
            # Update config paths to use temporary files
            config.clamd_config_path = str(clamd_config)
            config.freshclam_config_path = str(freshclam_config)
            config.virus_db_path = str(virus_db_dir)
            
            # Mock opkg_helper to return True for one ClamAV package
            with patch.object(config._opkg_helper, 'is_installed') as mock_installed:
                mock_installed.side_effect = lambda pkg: pkg == "clamav"
                
                args = argparse.Namespace()
                result = config.verify(args)
                
                # Should fail because config files are empty
                assert result is False

    def test_verify_installed_no_signatures(self):
        """Test verify method when ClamAV is installed but no signature files exist."""
        config = _ClamAVConfig()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temporary config files and database directory
            clamd_config = pathlib.Path(tmpdir) / "clamd.conf"
            freshclam_config = pathlib.Path(tmpdir) / "freshclam.conf"
            virus_db_dir = pathlib.Path(tmpdir) / "db"
            virus_db_dir.mkdir()
            
            # Create non-empty config files
            clamd_config.write_text("# ClamAV daemon config\nLogFile /var/log/clamav/clamd.log\n")
            freshclam_config.write_text("# FreshClam config\nUpdateLogFile /var/log/clamav/freshclam.log\n")
            
            # Don't create any signature files
            
            # Update config paths to use temporary files
            config.clamd_config_path = str(clamd_config)
            config.freshclam_config_path = str(freshclam_config)
            config.virus_db_path = str(virus_db_dir)
            
            # Mock opkg_helper to return True for one ClamAV package
            with patch.object(config._opkg_helper, 'is_installed') as mock_installed:
                mock_installed.side_effect = lambda pkg: pkg == "clamav"
                
                args = argparse.Namespace()
                result = config.verify(args)
                
                # Should fail because no signature files exist
                assert result is False