"""Automatic logging functionality for nilrt-snac operations.

This module provides transparent capture of stdout/stderr to log files
for configure and verify operations, maintaining full console output while
creating audit logs with proper permissions.
"""

import os
import sys
import grp
import logging
import datetime
import platform
from pathlib import Path
from typing import Optional, TextIO, List
from contextlib import contextmanager

from nilrt_snac import logger, SNACError, Errors

LOG_DIR = Path("/var/log/nilrt-snac")
LOG_PERMISSIONS = 0o640  # owner: rw, group: r, others: none
LOG_GROUP = "adm"
DIR_PERMISSIONS = 0o750  # owner: rwx, group: rx, others: none


class _TeeStream:
    """A stream that writes to multiple outputs simultaneously.

    This allows us to capture output to a log file while maintaining
    normal console output behavior.
    """

    def __init__(self, original_stream: TextIO, log_file: TextIO):
        """Initialize the tee stream.

        Args:
            original_stream: The original stdout or stderr stream
            log_file: The log file to duplicate output to
        """
        self.original_stream = original_stream
        self.log_file = log_file
        self._encoding = original_stream.encoding
        self._errors = original_stream.errors

    def write(self, data: str) -> int:
        """Write data to both streams.

        Args:
            data: The string data to write

        Returns:
            Number of characters written
        """
        # Write to console first for immediate feedback
        written = self.original_stream.write(data)
        self.original_stream.flush()

        # Then write to log file, but catch errors to avoid disrupting execution
        try:
            self.log_file.write(data)
            self.log_file.flush()
        except Exception as e:
            # If logging fails mid-execution, warn but don't crash
            self.original_stream.write(f"\n[WARNING] Failed to write to log file: {e}\n")

        return written

    def flush(self):
        """Flush both streams."""
        self.original_stream.flush()
        try:
            self.log_file.flush()
        except Exception:
            pass  # Ignore flush errors

    def isatty(self) -> bool:
        """Check if the original stream is a TTY."""
        return self.original_stream.isatty()

    @property
    def encoding(self):
        """Return the encoding of the original stream."""
        return self._encoding

    @property
    def errors(self):
        """Return the error handling mode of the original stream."""
        return self._errors


def _create_log_directory() -> None:
    """Create the log directory with proper permissions.

    Raises:
        SNACError: If directory creation fails
    """
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Set directory permissions
        os.chmod(LOG_DIR, DIR_PERMISSIONS)

        # Set group ownership to 'adm' if it exists
        try:
            adm_gid = grp.getgrnam(LOG_GROUP).gr_gid
            os.chown(LOG_DIR, -1, adm_gid)  # -1 means don't change owner
        except KeyError:
            logger.warning(f"Group '{LOG_GROUP}' not found. Log directory will use default group.")

    except PermissionError as e:
        raise SNACError(
            f"Permission denied creating log directory {LOG_DIR}: {e}", Errors.EX_BAD_ENVIRONMENT
        )
    except OSError as e:
        raise SNACError(f"Failed to create log directory {LOG_DIR}: {e}", Errors.EX_BAD_ENVIRONMENT)


def _generate_log_filename(command: str) -> str:
    """Generate a timestamped log filename.

    Args:
        command: The command name (configure or verify)

    Returns:
        Filename string like 'configure-20251015-143022.log'
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{command}-{timestamp}.log"


def _write_log_header(log_file: TextIO, command: str, args: List[str]) -> None:
    """Write a structured header to the log file.

    Args:
        log_file: The log file handle
        command: The command being executed
        args: Command line arguments
    """
    header = [
        "=" * 80,
        f"NILRT SNAC {command.upper()} LOG",
        "=" * 80,
        f"Timestamp: {datetime.datetime.now().isoformat()}",
        f"Command: nilrt-snac {' '.join(args)}",
        f"User: {os.environ.get('USER', 'unknown')} (UID: {os.getuid()})",
        f"Hostname: {platform.node()}",
        f"Python: {sys.version.split()[0]}",
        f"Platform: {platform.platform()}",
        "=" * 80,
        "",
    ]
    log_file.write("\n".join(header))
    log_file.flush()


def _write_log_footer(log_file: TextIO, return_code: int) -> None:
    """Write a structured footer to the log file.

    Args:
        log_file: The log file handle
        return_code: The exit code of the operation
    """
    footer = [
        "",
        "=" * 80,
        f"Execution completed at: {datetime.datetime.now().isoformat()}",
        f"Exit code: {return_code}",
        "=" * 80,
    ]
    log_file.write("\n".join(footer))
    log_file.flush()


@contextmanager
def logging_context(command: str, args: List[str], enabled: bool = True):
    """Context manager that captures all output to a log file.

    This context manager replaces stdout and stderr with tee streams that
    write to both the console and a log file. It then redirects all logging
    handlers to use the new stderr stream, ensuring proper interleaving of
    print() and logger.*() output.

    Args:
        command: The command being executed (configure or verify)
        args: Command line arguments for the log header
        enabled: Whether logging is enabled (can be disabled via --no-log)

    Yields:
        Path to the log file, or None if logging is disabled

    Example:
        with logging_context('configure', sys.argv[1:]) as log_path:
            # Your code here
            pass
        # Log path is printed automatically
    """
    if not enabled:
        yield None
        return

    # Create log directory (this will fail fast if there are permission issues)
    _create_log_directory()

    # Generate log file path
    log_filename = _generate_log_filename(command)
    log_path = LOG_DIR / log_filename

    # Store original streams and handlers
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_file: Optional[TextIO] = None
    original_handler_streams: List[tuple] = []  # List of (handler, original_stream) tuples

    try:
        # Open log file with proper permissions
        # We use os.open with specific mode, then wrap with TextIO
        fd = os.open(
            log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, LOG_PERMISSIONS  # Fail if exists
        )
        log_file = os.fdopen(fd, "w", encoding="utf-8")

        # Set group ownership
        try:
            adm_gid = grp.getgrnam(LOG_GROUP).gr_gid
            os.fchown(fd, -1, adm_gid)
        except KeyError:
            logger.warning(f"Group '{LOG_GROUP}' not found. Log file will use default group.")

        # Write header
        _write_log_header(log_file, command, args)

        # Replace stdout and stderr with tee streams
        # This captures all print() and subprocess output
        sys.stdout = _TeeStream(original_stdout, log_file)
        sys.stderr = _TeeStream(original_stderr, log_file)

        # Redirect all existing logging handlers to use the new stderr stream
        # This ensures logger output is interleaved with print() output
        for handler in logging.root.handlers[:]:  # [:] creates a copy to iterate safely
            if isinstance(handler, logging.StreamHandler):
                # Save the original stream so we can restore it later
                original_handler_streams.append((handler, handler.stream))
                # Redirect handler to the new tee'd stderr
                handler.stream = sys.stderr

        # Yield the log path to the caller
        yield log_path

    except FileExistsError:
        # This should be rare, but handle the case where the file already exists
        raise SNACError(
            f"Log file {log_path} already exists. This may indicate a clock issue or rapid re-execution.",
            Errors.EX_ERROR,
        )
    except PermissionError as e:
        raise SNACError(
            f"Permission denied creating log file {log_path}: {e}", Errors.EX_BAD_ENVIRONMENT
        )
    except OSError as e:
        raise SNACError(f"Failed to create log file {log_path}: {e}", Errors.EX_BAD_ENVIRONMENT)
    finally:
        # Restore original streams for all logging handlers
        for handler, original_stream in original_handler_streams:
            try:
                handler.stream = original_stream
            except Exception:
                pass  # Ignore errors during restoration

        # Restore original stdout and stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        # Close log file if it was opened
        if log_file is not None:
            try:
                # Write footer if we got this far
                _write_log_footer(log_file, 0)  # We don't know the real return code here
                log_file.close()
            except Exception:
                pass  # Ignore errors during cleanup

        # Restore original streams (even in case of errors)
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        # Close log file if it was opened
        if log_file is not None:
            try:
                # Write footer if we got this far
                _write_log_footer(log_file, 0)  # We don't know the real return code here
                log_file.close()
            except Exception:
                pass  # Ignore errors during cleanup


def print_log_location(log_path: Optional[Path]) -> None:
    """Print the location of the log file to the user.

    Args:
        log_path: Path to the log file, or None if logging was disabled
    """
    if log_path is not None:
        print(f"\nLog saved to: {log_path}")
