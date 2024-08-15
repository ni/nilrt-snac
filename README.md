# NILRT SNAC Configuration Tool

The NI LinuxRT Secured, Network-Attached Controller (SNAC) tool is a utility for admins to put a NILRT system into the SNAC configuration.

NOTICE: This tool is under-development and is very unsafe to run on a production system.


# Design

This tool...
* is not (yet) officially supported by NI.
* is only designed to work on NILRT versions 10.3 or later.
	* `grep 'ID=' /etc/os-release`
* only works in runmode. It will refuse to run from safemode.
* requires a network connection to the internet.
* requires access to the core NILRT package feeds.
* can only be run as root.
* has no external library dependencies.
* installs some open source projects at runtime which are not officially supported by NI.
	* wireguard-tools (from the debian package feeds)
	* USBGuard (from its canonical upstream GH repo)


# Installation

## Installation Dependencies

* `make`

## Installation From Source

On a deployed NILRT system, in runmode...

```bash
mkdir -p /usr/local/src
wget 'https://github.com/ni/nilrt-snac/archive/refs/heads/master.tar.gz' -O - | tar xzf - -C /usr/local/src
cd /usr/local/src/nilrt-snac*
make install sysconfdir=/etc  # prefix defaults to /usr/local
```

### Uninstallation

```bash
cd /usr/local/src/nilrt-snac
make uninstall sysconfdir=/etc
```

## Installation from the NILRT IPK Feeds

*WORK IN PROGRESS*


# Usage

## Runtime Dependencies

* `bash`
* `util-linux.logger`

## CLI

After installation, the tool should be available in your PATH.

```bash
nilrt-snac configure
```

After the script completes successfully, you will be instructed to reboot your system. Reboot into runmode and login using `root` with no password.
