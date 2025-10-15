"""Tests for automatic logging functionality in nilrt-snac.

These tests verify that configure and verify commands properly generate
logs with correct permissions, content, and behavior.
"""

import os
import re
import grp
import stat
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from .fixtures import nilrt_snac_cli


LOG_DIR = Path("/var/log/nilrt-snac")
LOG_PERMISSIONS = 0o640
DIR_PERMISSIONS = 0o750


def _get_latest_log_file(command: str) -> Path:
    """Get the most recently created log file for a command.

    Args:
        command: The command name (configure or verify)

    Returns:
        Path to the latest log file
    """
    log_files = list(LOG_DIR.glob(f"{command}-*.log"))
    if not log_files:
        pytest.fail(f"No log files found for command: {command}")
    return max(log_files, key=lambda p: p.stat().st_mtime)


def _check_log_permissions(log_path: Path) -> None:
    """Verify log file has correct permissions and group ownership.

    Args:
        log_path: Path to the log file to check
    """
    # Check file permissions
    file_stat = log_path.stat()
    actual_mode = stat.S_IMODE(file_stat.st_mode)
    assert (
        actual_mode == LOG_PERMISSIONS
    ), f"Log file permissions are {oct(actual_mode)}, expected {oct(LOG_PERMISSIONS)}"

    # Check group ownership is 'adm' (if the group exists)
    try:
        adm_gid = grp.getgrnam("adm").gr_gid
        assert (
            file_stat.st_gid == adm_gid
        ), f"Log file group is GID {file_stat.st_gid}, expected 'adm' (GID {adm_gid})"
    except KeyError:
        # 'adm' group doesn't exist on this system, skip group check
        pass


def _check_log_header(log_content: str, command: str) -> None:
    """Verify log file contains proper header with metadata.

    Args:
        log_content: Content of the log file
        command: The command that was executed
    """
    # Check for header separator
    assert "=" * 80 in log_content, "Log file missing header separator"

    # Check for command in header
    assert f"NILRT SNAC {command.upper()} LOG" in log_content, f"Log header missing command title"

    # Check for required metadata fields
    required_fields = [
        "Timestamp:",
        "Command:",
        "User:",
        "Hostname:",
        "Python:",
        "Platform:",
    ]
    for field in required_fields:
        assert field in log_content, f"Log header missing field: {field}"


def _check_log_footer(log_content: str) -> None:
    """Verify log file contains proper footer.

    Args:
        log_content: Content of the log file
    """
    # Check for footer separator
    lines = log_content.split("\n")
    footer_found = False
    for i, line in enumerate(lines):
        if "Execution completed at:" in line:
            footer_found = True
            # Check that footer has proper structure
            assert "=" * 80 in lines[i - 1], "Footer missing top separator"
            assert "Exit code:" in lines[i + 1], "Footer missing exit code"
            break

    assert footer_found, "Log file missing footer"


@pytest.mark.skipif(
    os.geteuid() != 0, reason="This test requires root privileges to create logs in /var/log"
)
def test_verify_creates_log(nilrt_snac_cli):
    """Test that 'verify' command creates a log file."""
    # Run verify command
    proc = nilrt_snac_cli.run(["verify"])

    # Check that log location was printed
    assert "Log saved to:" in proc.stdout, "verify command did not print log location"

    # Extract log path from output
    match = re.search(r"Log saved to: (.+)", proc.stdout)
    assert match, "Could not parse log path from output"
    log_path = Path(match.group(1).strip())

    # Verify log file exists
    assert log_path.exists(), f"Log file does not exist: {log_path}"

    # Verify log file is in correct directory
    assert log_path.parent == LOG_DIR, f"Log file in wrong directory: {log_path.parent}"

    # Verify filename format
    assert re.match(
        r"verify-\d{8}-\d{6}\.log", log_path.name
    ), f"Log filename has incorrect format: {log_path.name}"


@pytest.mark.skipif(os.geteuid() != 0, reason="This test requires root privileges")
def test_verify_log_permissions(nilrt_snac_cli):
    """Test that log files have correct permissions."""
    # Run verify command
    proc = nilrt_snac_cli.run(["verify"])

    # Get the log file
    log_path = _get_latest_log_file("verify")

    # Check permissions
    _check_log_permissions(log_path)


@pytest.mark.skipif(os.geteuid() != 0, reason="This test requires root privileges")
def test_verify_log_content(nilrt_snac_cli):
    """Test that log files contain expected content."""
    # Run verify command with verbose flag to get more output
    proc = nilrt_snac_cli.run(["verify", "-v"])

    # Get the log file
    log_path = _get_latest_log_file("verify")

    # Read log content
    with open(log_path, "r") as f:
        log_content = f.read()

    # Check header
    _check_log_header(log_content, "verify")

    # Check that actual output is in the log
    assert "Validating SNAC mode" in log_content, "Log file missing expected command output"

    # Check footer
    _check_log_footer(log_content)


@pytest.mark.skipif(os.geteuid() != 0, reason="This test requires root privileges")
def test_verify_no_log_flag(nilrt_snac_cli):
    """Test that --no-log flag suppresses log creation."""
    # Count existing log files
    initial_logs = list(LOG_DIR.glob("verify-*.log")) if LOG_DIR.exists() else []
    initial_count = len(initial_logs)

    # Run verify with --no-log
    proc = nilrt_snac_cli.run(["verify", "--no-log"])

    # Check that log location was NOT printed
    assert "Log saved to:" not in proc.stdout, "verify --no-log should not print log location"

    # Verify no new log files were created
    final_logs = list(LOG_DIR.glob("verify-*.log")) if LOG_DIR.exists() else []
    final_count = len(final_logs)

    assert (
        final_count == initial_count
    ), f"verify --no-log created log files: {final_count - initial_count} new files"


@pytest.mark.skipif(os.geteuid() != 0, reason="This test requires root privileges")
def test_configure_dry_run_creates_log(nilrt_snac_cli):
    """Test that configure --dry-run creates a log file."""
    # Run configure in dry-run mode with -y to avoid interactive prompt
    proc = nilrt_snac_cli.run(["configure", "--dry-run", "-y"])

    # Check that log location was printed
    assert "Log saved to:" in proc.stdout, "configure --dry-run did not print log location"

    # Extract and verify log path
    match = re.search(r"Log saved to: (.+)", proc.stdout)
    assert match, "Could not parse log path from output"
    log_path = Path(match.group(1).strip())

    # Verify log file exists
    assert log_path.exists(), f"Log file does not exist: {log_path}"

    # Verify filename format
    assert re.match(
        r"configure-\d{8}-\d{6}\.log", log_path.name
    ), f"Log filename has incorrect format: {log_path.name}"


@pytest.mark.skipif(os.geteuid() != 0, reason="This test requires root privileges")
def test_log_directory_permissions(nilrt_snac_cli):
    """Test that log directory has correct permissions."""
    # Run a command to ensure directory exists
    proc = nilrt_snac_cli.run(["verify"])

    # Check directory exists
    assert LOG_DIR.exists(), f"Log directory does not exist: {LOG_DIR}"

    # Check directory permissions
    dir_stat = LOG_DIR.stat()
    actual_mode = stat.S_IMODE(dir_stat.st_mode)
    assert (
        actual_mode == DIR_PERMISSIONS
    ), f"Log directory permissions are {oct(actual_mode)}, expected {oct(DIR_PERMISSIONS)}"

    # Check group ownership is 'adm' (if the group exists)
    try:
        adm_gid = grp.getgrnam("adm").gr_gid
        assert (
            dir_stat.st_gid == adm_gid
        ), f"Log directory group is GID {dir_stat.st_gid}, expected 'adm' (GID {adm_gid})"
    except KeyError:
        # 'adm' group doesn't exist on this system, skip group check
        pass


@pytest.mark.skipif(os.geteuid() != 0, reason="This test requires root privileges")
def test_log_captures_stderr(nilrt_snac_cli):
    """Test that log captures stderr output (warnings, errors)."""
    # Run verify command (it outputs warnings to stderr)
    proc = nilrt_snac_cli.run(["verify"])

    # Get the log file
    log_path = _get_latest_log_file("verify")

    # Read log content
    with open(log_path, "r") as f:
        log_content = f.read()

    # The verify command should have some logging output
    # Check that log metadata is present (this comes from logger which uses stderr)
    assert (
        "Verifying" in log_content or "Validating" in log_content
    ), "Log file does not capture expected output"


@pytest.mark.skipif(os.geteuid() != 0, reason="This test requires root privileges")
def test_multiple_logs_unique_filenames(nilrt_snac_cli):
    """Test that multiple runs create separate log files with unique names."""
    # Run verify twice in quick succession
    proc1 = nilrt_snac_cli.run(["verify"])
    proc2 = nilrt_snac_cli.run(["verify"])

    # Extract log paths
    match1 = re.search(r"Log saved to: (.+)", proc1.stdout)
    match2 = re.search(r"Log saved to: (.+)", proc2.stdout)

    assert match1 and match2, "Could not parse log paths"

    log_path1 = Path(match1.group(1).strip())
    log_path2 = Path(match2.group(1).strip())

    # Verify both files exist
    assert log_path1.exists(), f"First log file does not exist: {log_path1}"
    assert log_path2.exists(), f"Second log file does not exist: {log_path2}"

    # Verify they are different files
    assert log_path1 != log_path2, "Two successive runs created the same log file"


@pytest.mark.skipif(os.geteuid() != 0, reason="This test requires root privileges")
def test_log_captures_python_logger_output(nilrt_snac_cli):
    """Test that log captures Python logging module output (logger.info, logger.warning, etc)."""
    # Run verify command with verbose flag to trigger debug logging
    proc = nilrt_snac_cli.run(["verify", "-v"])

    # Get the log file
    log_path = _get_latest_log_file("verify")

    # Read log content
    with open(log_path, "r") as f:
        log_content = f.read()

    # Check for logger output with the specific format used by nilrt-snac
    # Format is: "(relativeCreated) LEVEL name.function: message"
    # Look for patterns that indicate logger output is captured

    # Should contain logger messages with the timestamp format
    assert re.search(
        r"\(\s*\d+\)\s+(INFO|DEBUG|WARNING|ERROR)", log_content
    ), "Log file does not contain formatted logger output with timestamps"

    # Specifically check for known logger output from the verify command
    # These are messages that come from logger.info() calls in the config modules
    logger_patterns = [
        r"(INFO|DEBUG).*nilrt_snac",  # Logger name should appear
        r"Verifying",  # Common verification message
    ]

    for pattern in logger_patterns:
        assert re.search(
            pattern, log_content
        ), f"Log file missing expected logger pattern: {pattern}"
