# Automatic Logging Feature

## Overview

The `nilrt-snac` tool automatically logs all output from `configure` and `verify` operations to `/var/log/nilrt-snac/` for audit and troubleshooting purposes.

## Log Location

Logs are stored in `/var/log/nilrt-snac/` with timestamped filenames:
- `configure-YYYYMMDD-HHMMSS.log` - Configuration run logs
- `verify-YYYYMMDD-HHMMSS.log` - Verification run logs

Example: `configure-20251015-143022.log`

## Log Permissions

- **Directory permissions**: `0750` (rwxr-x---)
- **File permissions**: `0640` (rw-r-----)
- **Group ownership**: `adm` (if available)

Logs are only readable by:
- Root user (owner)
- Members of the `adm` group

## Log Content

Each log file contains:

### Header Section
- Timestamp of execution start
- Full command line used
- User and UID who executed the command
- Hostname
- Python version
- Platform information

### Body Section
- Complete stdout and stderr output
- All Python logging output (logger.debug, logger.info, logger.warning, logger.error)
- All subprocess output (e.g., from opkg commands)
- Interactive prompts and user responses
- Progress messages and warnings

### Footer Section
- Timestamp of execution completion
- Exit code

## Usage

### Normal Operation (Logging Enabled)

```bash
# Configure with automatic logging
sudo nilrt-snac configure

# Verify with automatic logging
sudo nilrt-snac verify
```

At the end of execution, the tool prints:
```
Log saved to: /var/log/nilrt-snac/configure-20251015-143022.log
```

### Suppress Logging

To disable automatic logging, use the `--no-log` flag:

```bash
# Configure without logging
sudo nilrt-snac configure --no-log

# Verify without logging
sudo nilrt-snac verify --no-log
```

### Dry Run Mode

Dry run mode still creates logs by default:

```bash
# Dry run with logging
sudo nilrt-snac configure --dry-run -y

# Dry run without logging
sudo nilrt-snac configure --dry-run -y --no-log
```

## Log Management

### Viewing Logs

```bash
# List all logs
ls -lh /var/log/nilrt-snac/

# View latest configure log
sudo less $(ls -t /var/log/nilrt-snac/configure-*.log | head -1)

# View latest verify log
sudo less $(ls -t /var/log/nilrt-snac/verify-*.log | head -1)

# Search for errors in logs
sudo grep -i error /var/log/nilrt-snac/*.log
```

### Retention

The tool does NOT automatically delete old logs. System administrators should:

1. Monitor log directory size:
   ```bash
   du -sh /var/log/nilrt-snac/
   ```

2. Manually delete old logs when needed:
   ```bash
   # Delete logs older than 90 days
   find /var/log/nilrt-snac/ -name "*.log" -mtime +90 -delete
   ```

3. Consider using `logrotate` for automatic rotation:
   ```bash
   # Example /etc/logrotate.d/nilrt-snac
   /var/log/nilrt-snac/*.log {
       weekly
       rotate 12
       compress
       missingok
       notifempty
       create 0640 root adm
   }
   ```

## Error Handling

### Log Directory Creation Fails

If the tool cannot create `/var/log/nilrt-snac/` (e.g., due to disk full or permissions), the entire operation fails immediately:

```
ERROR: Failed to create log directory /var/log/nilrt-snac: No space left on device
```

**Resolution**: Free up disk space or fix permissions before retrying.

### Log File Creation Fails

If the tool cannot create the log file (e.g., permissions issue), the operation fails:

```
ERROR: Permission denied creating log file /var/log/nilrt-snac/configure-20251015-143022.log
```

**Resolution**: Check directory permissions and available disk space.

### Mid-Execution Logging Failure

If logging fails during execution (rare), the operation continues with a warning:

```
[WARNING] Failed to write to log file: Disk quota exceeded
```

The operation continues to display output on the console. Partial logs may be saved.

## Security Considerations

1. **Sensitive Information**: Logs may contain sensitive system configuration details. Ensure proper access controls.

2. **Audit Trail**: Logs serve as an audit trail of SNAC configuration changes. Do not delete logs that may be needed for compliance.

3. **Group Access**: Members of the `adm` group can read logs. Review group membership regularly.

4. **Interactive Inputs**: User responses to interactive prompts (including the consent prompt) are logged for audit purposes.

## Testing

Run integration tests to verify logging functionality:

```bash
# Run logging tests (requires root)
sudo python3 -m pytest tests/integration/test_logging.py -v
```

## Troubleshooting

### No log file created

**Symptoms**: Command runs but no log file appears.

**Causes**:
1. `--no-log` flag was used
2. Not running `configure` or `verify` command
3. Log directory creation failed (check stderr for errors)

**Resolution**: 
- Remove `--no-log` flag if present
- Check for error messages
- Verify `/var/log` has write permissions

### Cannot read log file

**Symptoms**: Permission denied when trying to read log.

**Causes**:
1. Not running as root
2. Not in `adm` group

**Resolution**:
```bash
# Read as root
sudo cat /var/log/nilrt-snac/configure-*.log

# Or add user to adm group
sudo usermod -aG adm yourusername
# (logout and login for group change to take effect)
```

### Log directory fills up disk

**Symptoms**: Disk space warnings, operation failures.

**Resolution**:
```bash
# Check log directory size
du -sh /var/log/nilrt-snac/

# Delete old logs
sudo rm /var/log/nilrt-snac/configure-20240101-*.log
```

## Implementation Details

The logging system uses a unified stream approach:

1. **Stream Replacement**: Output streams (stdout/stderr) are replaced with custom `_TeeStream` objects that write to both console and log file simultaneously
2. **Logger Redirection**: All existing logging `StreamHandler` instances are redirected to use the new tee'd stderr stream

This ensures complete capture with proper interleaving:
- `print()` statements → written through _TeeStream
- Python `logger.*` calls → handlers redirected to _TeeStream
- Subprocess output → captured via _TeeStream
- All output maintains proper temporal ordering (interleaved correctly)
- Original console behavior is preserved (including interactivity)

Key files:
- `/d/nilrt-snac/nilrt_snac/_logging.py` - Logging implementation
- `/d/nilrt-snac/tests/integration/test_logging.py` - Test suite
