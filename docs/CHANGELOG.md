# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

* The `configure` operation now disables WIFI interfaces. (#2, #13)
* The `configure` operation now installs a `nilrt-snac-conflicts` meta-package, so that the tool can forbid re-installation of non-compliant packages. (#5)
* The `configure` operation now installs `libpwquality` and enables password quality checks. (#11)
* The `configure` operation now installs and configures `tmux` as the shell, including adding a 15 minute inactivity lock (#17)
* Added a `verify` operation to non-destructively check that the system is still SNAC-compliant. (#15)
* The `configure` operation installs `firewalld` with explicit control over both inbound and outbound
  traffic. (#29)
* `firewalld` is configured to permit selected NI service traffic over wireguard. (#50)

### Changed

* The dedicated wireguard interface is now called `wglv0` (#6).
* The `configure` operation now installs `wireguard-tools` configuration files for `wglv0`, so it can persist between reboots (#6).
* Most of the project's logic has been reimplemented as a python module. (#15).
* The `configure` operation now removes `packagegroup-ni-graphical` in addition to `packagegroup-core-x11` and `packagegroup-ni-xfce`.


## [0.1.1] - 2024-08-19

Release corresponding to the SNAC v0.1 beta release.


### Added

* The `configure` operation now installs a `nilrt-snac-conflicts` meta-package, so that the tool can forbid re-installation of non-compliant packages. (#5)


### Changed

* The dedicated wireguard interface is now called `wglv0` (#6).
* The `configure` operation now installs `wireguard-tools` configuration files for `wglv0`, so it can persist between reboots (#6).



## [0.1.0] - 2024-07-23

Initial draft implementation.
