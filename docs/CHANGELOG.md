# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

## [3.0.0] - 2025-09-18

Release corresponding to the LV 2025Q4 / NILRT 11.3 release.

### Added
* When `usbguard` is installed to the NILRT system, `nilrt-snac verify` will now verify that it is enabled and has a valid configuration. (#68)

### Changed
* ni-logos-xt outbound traffic is now permitted on the firewall's 'work' zone. (#66)


## [2.1.0] - 2025-06-12

Release corresponding to the LV 2025Q3 / NILRT 11.2 release.

### Changed
* Syslog outbound traffic is now permitted on the firewall's 'work' zone. (#64)

### Fixed
* Fixed a bug in the auditd configuration where the service's initscript would not be registered with update-rc.d. (#63)
* Fixed a bug in the auditd configuration that would cause an internal python error when trying to verify a system where the `auditd.conf` file does not exist. (#65)


## [2.0.0] - 2025-03-21

Release corresponding to the LV 2025Q2 / NILRT 11.1 release.

### Added
* Install and configure `auditd` in order to log system activites.
* Install and configure `syslog-ng` in order to log system activites.
* Added service definitons for SNAC-supported NI services to the firewalld configuration. (#50)
* Added a `nilrt-snac verify` task for `ni-labview-realtime`. (#53)
* Auditd is now installed and configured by `nilrt-snac configure`. (#57)
* syslog-ng is now configured by `nilrt-snac configure`. (#59)

### Changed
* Restricted write access to system logs in `/var/log` to System Maintainers (root) and Auditors via the `adm` group.
* Restricted write access to `auditd.conf` to System Maintainers and Admins via the `sudo` group.
* NTP traffic is now permitted on the public network, by default. (#50)
* niroco traffic is now permitted on the work firewall zone. (#52)

### Fixed
* Corrected the `verify` operation to ensure it accurately detects configuration changes.
* Corrected the opkg config file permissions so that unprivileged users can perform read-only opkg operations. (#55)
* Fixed a bug in the `verify` operation that could cause it to return a sucess, if config values have been changed to super-strings of their current value. (#61)


## [1.0.0] - 2024-12-16

Release corresponding to the NILRT 11.0 (2025Q1) distribution release.


### Added
* Added a `verify` operation to non-destructively check that the system is still SNAC-compliant. (#15)
* Added a system test fixture that sets up a wireguard tunnel between a Windows host and a SNAC device (#41).


### Changed
* The dedicated wireguard interface is now called `wglv0` (#6).
* Most of the project's logic has been reimplemented as a python module (#15).
* Many changes to the `nilrt-snac configure` actions.
	* Disable WIFI interfaces. (#2, #13)
	* Install a `nilrt-snac-conflicts` meta-package, so that the tool can forbid re-installation of non-compliant packages. (#5)
	* Install `wireguard-tools` configuration files for `wglv0`, so it can persist between reboots (#6).
	* Install `libpwquality` and enable password quality checks. (#11, #25, #30)
	* Configure `sudo`. (#19)
	* Remove `packagegroup-ni-graphical` in addition to `packagegroup-core-x11` and `packagegroup-ni-xfce` (#44).
	* Install `wireguard-tools` from the NI IPK feed (#36, #39).
	* Install and configure `tmux` as the shell, including adding a 15 minute inactivity lock (#17)
	* Install `firewalld` with explicit control over both inbound and outbound traffic. (#29, #50)
		* `firewalld` is configured to permit selected NI service traffic over wireguard. (#50)
	* Create a valid `opasswd` file. (#35)
	* Install the `ni-sysapi-cli` package, to enable sysapi communications (#43).
	* Disable the graphical UI and console output (#45).


## [0.1.1] - 2024-08-19

Release corresponding to the SNAC v0.1 beta release.


### Added

* The `configure` operation now installs a `nilrt-snac-conflicts` meta-package, so that the tool can forbid re-installation of non-compliant packages. (#5)


### Changed

* The dedicated wireguard interface is now called `wglv0` (#6).
* The `configure` operation now installs `wireguard-tools` configuration files for `wglv0`, so it can persist between reboots (#6).



## [0.1.0] - 2024-07-23

Initial draft implementation.
