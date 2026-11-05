"""Tests for package installation logging and dry-run behavior."""

import logging
from unittest.mock import patch

import pytest

from nilrt_snac import opkg


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("force_reinstall", [True, False])
def test_install_logs_requested_operation(caplog, dry_run, force_reinstall):
    helper = opkg.opkg_helper
    caplog.set_level(logging.INFO, logger="nilrt_snac")

    with (
        patch.object(helper, "_dry_run", dry_run, create=True),
        patch.object(helper, "_installed_packages", []),
        patch.object(opkg, "run_with_logging") as package_command,
    ):
        helper.install("test-package", force_reinstall=force_reinstall)

        assert caplog.messages == ["Installing IPK: test-package"]
        assert helper.is_installed("test-package")
        if dry_run:
            package_command.assert_not_called()
        else:
            command = ["opkg", "install"]
            if force_reinstall:
                command.append("--force-reinstall")
            package_command.assert_called_once_with(
                *command, "test-package", check=True
            )

        helper.install("test-package", force_reinstall=force_reinstall)
        assert caplog.messages == ["Installing IPK: test-package"]
        assert package_command.call_count == (0 if dry_run else 1)
