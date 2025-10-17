"""nilrt-snac entry points."""

import argparse
import logging
import sys
import configparser
from contextlib import nullcontext
from pathlib import Path
from typing import Dict, List, Optional

from nilrt_snac._pre_reqs import verify_prereqs
from nilrt_snac.opkg import opkg_helper
from nilrt_snac._configs import CONFIGS
from nilrt_snac import Errors, logger, SNACError, __version__
from nilrt_snac._logging import logging_context

PROG_NAME = "nilrt-snac"
VERSION_DESCRIPTION = f"""\
nilrt-snac {__version__}
Copyright (C) 2024 NI (Emerson Electric)
License MIT: MIT License <https://spdx.org/licenses/MIT.html>
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.
"""


def _get_enabled_modules(config_file_path: Path = Path("/etc/snac/snac.conf")) -> Dict[str, bool]:
    """Read the config file and return a dict of module enabled states. Strict validation and error reporting."""
    enabled_modules: Dict[str, bool] = {}
    valid_names = {c.name for c in CONFIGS}
    if config_file_path.exists():
        parser = configparser.ConfigParser()
        try:
            parser.read(str(config_file_path))
        except (configparser.MissingSectionHeaderError, configparser.ParsingError) as e:
            raise SNACError(f"Malformed config file: {config_file_path}", Errors.EX_USAGE)
        if not parser.has_section("modules"):
            logger.warning(
                f"Config file {config_file_path} missing [modules] section. All modules will be enabled."
            )
            return enabled_modules
        for name, value in parser.items("modules"):
            key = name.strip().lower()
            val = value.strip().lower()
            if key not in valid_names:
                raise SNACError(
                    f"Unknown module name '{key}' in config file: {config_file_path}. Valid names: {sorted(valid_names)}",
                    Errors.EX_USAGE,
                )
            if val not in ("enabled", "disabled"):
                raise SNACError(
                    f"Invalid value for module '{key}' in config file: '{value}'. Must be 'enabled' or 'disabled'.",
                    Errors.EX_USAGE,
                )
            enabled_modules[key] = val == "enabled"
    return enabled_modules


def _configure(args: argparse.Namespace) -> int:
    """Configure SNAC mode."""
    logger.warning("!! Running this tool will irreversibly alter the state of your system.    !!")
    logger.warning("!! If you are accessing your system using WiFi, you will lose connection. !!")

    if args.yes:
        consent = "y"
    else:
        consent = input("Do you want to continue with SNAC configuration? [y/N] ")

    if consent.lower() not in ["y", "yes"]:
        return Errors.EX_OK

    print("Configuring SNAC mode.")
    opkg_helper.update()

    # Read /etc/snac/snac.conf for module enable/disable
    enabled_modules = _get_enabled_modules()

    for config in CONFIGS:
        enabled = enabled_modules.get(config.name, True)
        if not enabled:
            logger.info(f"Skipping configuration for: {config.name} (disabled in config file)")
            continue
        config.configure(args)

    print("!! A reboot is now required to affect your system configuration. !!")
    print("!! Login with user 'root' and no password.                       !!")

    return Errors.EX_OK


def _verify(args: argparse.Namespace) -> int:
    """Configure SNAC mode."""
    print("Validating SNAC mode.")
    valid = True

    # Read /etc/snac/snac.conf for module enable/disable
    enabled_modules = _get_enabled_modules()

    for config in CONFIGS:
        enabled = enabled_modules.get(config.name, True)
        if not enabled:
            logger.info(f"Skipping verification for: {config.name} (disabled in config file)")
            continue
        new_valid = config.verify(args)
        valid = valid and new_valid

    if not valid:
        raise SNACError("SNAC mode is not configured correctly.", Errors.EX_CHECK_FAILURE)
    return Errors.EX_OK


def _parse_args(argv: List[str]) -> argparse.Namespace:
    """Top level entry point for the command line interface."""
    parser = argparse.ArgumentParser(
        description="Utility for enabling SNAC mode on NI Linux RT.",
        prog=PROG_NAME,
    )

    subparsers = parser.add_subparsers(help="Commands for SNAC mode.", dest="cmd")
    subparsers.required = False

    configure_parser = subparsers.add_parser("configure", help="Set SNAC mode")
    configure_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Consent to changes",
    )
    configure_parser.add_argument(
        "--audit-email",
        type=str,
        help="Email address for audit actions",
    )
    configure_parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable automatic logging to /var/log/nilrt-snac",
    )
    configure_parser.set_defaults(func=_configure)

    verify_parser = subparsers.add_parser("verify", help="Verify SNAC mode configured correctly")
    verify_parser.add_argument(
        "--log",
        action="store_true",
        help="Enable logging to /var/log/nilrt-snac (disabled by default for verify)",
    )
    verify_parser.set_defaults(func=_verify)

    debug_group = parser.add_argument_group("Debug")
    debug_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=0,
        help="Print debug information.  Can be repeated for more detailed output.",
    )
    debug_group.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        default=0,
        help="Print version.",
    )

    args = parser.parse_args(argv)

    return args


def main(  # noqa: D103 - Missing docstring in public function (auto-generated noqa)
    argv: Optional[List[str]] = None,
):
    if argv is None:
        argv = sys.argv
    args = _parse_args(argv[1:])

    log_level = logging.INFO
    if args.verbose:
        log_level = logging.DEBUG
    args.logging_level = log_level

    log_format = "(%(relativeCreated)5d) %(levelname)-5s %(name)s.%(funcName)s: %(message)s"
    logging.basicConfig(level=args.logging_level, format=log_format)

    logger.debug("Arguments: %s", args)
    opkg_helper.set_dry_run(args.dry_run)

    if args.version:
        print(VERSION_DESCRIPTION)
        return Errors.EX_OK

    if args.cmd is None:
        logger.error("Command required: {configure, verify}, see --help for more information.")
        return Errors.EX_USAGE

    # Determine if logging should be enabled based on command defaults
    # configure: logging enabled by default (disable with --no-log)
    # verify: logging disabled by default (enable with --log)
    if args.cmd == "configure":
        enable_logging = not args.no_log
    elif args.cmd == "verify":
        enable_logging = args.log
    else:
        enable_logging = False

    # Wrap execution in logging context if enabled
    cm = logging_context(args.cmd, argv[1:]) if enable_logging else nullcontext(None)
    ret_val = Errors.EX_OK
    with cm:
        try:
            if not args.dry_run:
                verify_prereqs()
            ret_val = args.func(args)
        except SNACError as e:
            logger.error(e)
            ret_val = e.return_code

    return ret_val


if __name__ == "__main__":
    sys.exit(main(sys.argv))
