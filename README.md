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
* installs some open source projects at runtime which are not officially supported by NI.
	* wireguard-tools (from the debian package feeds)
	* USBGuard (from its canonical upstream GH repo)


# Installation


## Installation from the NILRT IPK Feeds

On NILRT Base System Images 11.0 (2025Q1) and later, this project can be installed directly from the vendor's packaging.

This is the preferred method of installation for users.

```bash
opkg update && \
	opkg install nilrt-snac
```


### Uninstallation

```bash
opkg remove nilrt-snac
```


## Installation From Source

Install this project's build dependencies.

* `make`

Then build the project.

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


# Usage

## Runtime Dependencies

* `bash`
* `python3`


## CLI

After installation, the tool should be available in your PATH.

The tool has two primary modes of operation: `configure` and `verify`.


### Configure

In 'configure' mode, the tool will **apply** the SNAC configuration to the NILRT system. This is a destructive operation that should only be run by a system maintainer during deployment.

```bash
nilrt-snac configure
```

After the script completes successfully, you will be instructed to reboot your system. Reboot into runmode and login using `root` with no password.


### Verify

In 'verify' mode, the tool will **check** that the NILRT system is in the SNAC configuration, without modifying the system state. The operation will fail if any of the checks fail.

```bash
nilrt-snac verify
```
