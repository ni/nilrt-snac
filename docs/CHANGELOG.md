# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]
### Added
* Install and configure `auditd` in order to log system activites.
* Install and configure `syslog-ng` in order to log system activites.

### Changed
* Restricted write access to system logs in `/var/log` to System Maintainers (root) and Auditors via the `adm` group. 
* Restricted write access to `auditd.conf` to System Maintainers and Admins via the `sudo` group.


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
