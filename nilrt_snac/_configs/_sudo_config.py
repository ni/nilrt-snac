import argparse
import textwrap

from nilrt_snac._configs._base_config import _BaseConfig
from nilrt_snac._configs._config_file import _ConfigFile

from nilrt_snac import logger


class _SudoConfig(_BaseConfig):
    def __init__(self):
        pass  # Nothing to do for now

    def configure(self, args: argparse.Namespace) -> None:
        print("Configuring sudo...")
        config_file = _ConfigFile("/etc/sudoers.d/snac")
        dry_run: bool = args.dry_run
        if not config_file.exists():
            config_file.add(
                textwrap.dedent(
                    """
                    # NILRT SNAC configuration sudoers. Do not hand-edit.
                    Defaults timestamp_timeout=0
                    """
                )
            )
        config_file.save(dry_run)

    def verify(self, args: argparse.Namespace) -> bool:
        print("Verifying sudo configuration...")
        config_file = _ConfigFile("/etc/sudoers.d/snac")
        valid = True
        if not config_file.exists():
            valid = False
            logger.error(f"MISSING: {config_file.path} not found")
        elif not config_file.contains_exact("Defaults timestamp_timeout=0"):
            valid = False
            logger.error("MISSING: immediate timestamp_timeout")
        return valid
