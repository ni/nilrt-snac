"""Helper class to read/write and update configuration files."""

import grp
import os
import pathlib
import pwd
import re
from typing import Union

from nilrt_snac import logger


class _ConfigFile:
    """Helper class to read/write and update configuration files."""

    def __init__(self, path: Union[pathlib.Path, str]) -> None:
        """Initialize the ConfigFile object.

        Args: path: The path to the configuration file.
        """
        if type(path) is str:
            path = pathlib.Path(path)

        self.path = path
        self._config = path.read_text() if path.exists() else ""
        self._mode = path.stat().st_mode if path.exists() else 0o600
        self._uid = path.stat().st_uid if path.exists() else None
        self._gid = path.stat().st_gid if path.exists() else None

    def save(self, dry_run: bool) -> None:
        """Save the configuration file."""
        if dry_run:
            print("dry-run: Not saved")
        else:
            self.path.write_text(self._config)
            self.path.chmod(self._mode)
            if self._uid is not None and self._gid is not None:
                os.chown(self.path, self._uid, self._gid)
        logger.debug(f"Contents of {self.path}:")
        logger.debug(self._config)

    def update(self, key: str, value: str) -> None:
        """Update the configuration file with the given key and value.

        Args:
            key: Search RE pattern to find the key.
            value: The value to replace the key with.

        Uses the re.sub() method to replace the key with the value.
        """
        self._config = re.sub(key, value, self._config, flags=re.MULTILINE)

    def add(self, value: str) -> None:
        """Add the value string to the config file.

        Args:
            value: String to add
        """
        self._config += value

    def exists(self) -> bool:
        return self.path.exists()

    def chmod(self, mode: int) -> None:
        self._mode = mode
    
    def chown(self, user: str, group: str) -> None:
        """Change the owner and group of the configuration file.

        Args:
            user: Username to set as the owner.
            group: Group name to set as the group.
        """
        self._uid = pwd.getpwnam(user).pw_uid
        self._gid = grp.getgrnam(group).gr_gid

    def contains(self, key: str) -> bool:
        """Check if the configuration file contains the given key.

        Args: key: RE pattern to search for in the configuration file.

        Returns: True if the key is found, False otherwise.
        """
        return bool(re.search(key, self._config))
    
    def contains_exact(self, key: str) -> bool:
        """Check if the configuration file contains a line with the exact given key.

        Args: key: RE pattern to search for in the configuration file.

        Returns: True if the key is found, False otherwise.
        """
      
        exact_pattern = re.compile(rf'^\s*{re.escape(key)}\s*$', re.MULTILINE)
        return bool(exact_pattern.search(self._config))
    
 
class EqualsDelimitedConfigFile(_ConfigFile):
    def get(self, key: str) -> str:
        """
        Return the value for the first line where the left side of '=' matches the key (ignoring whitespace).

        Args:
            key: The key to search for (left side of equals).

        Returns:
            The value (right side of equals) for the first matching line, or an empty string if not found.
        """
        for line in self._config.splitlines():
            parts = line.split("=", 1)
            if len(parts) > 1 and parts[0].replace(" ","").replace("\t","") == key:
                return parts[1].strip()
        return ""
