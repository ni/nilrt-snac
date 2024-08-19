# Maintenance

This document contains information about project governance and maintenance processes.


## Maintainers

The following individuals have generously donated their time to maintaining this project.

* Alex Stewart <alex.stewart@ni.com> - Active. Lead Maintainer.
* Alex Hearn <alex.hearn@ni.com> - Active. Cooperating Maintainer.


## Versioning Policy

This project uses [semantic versioning](https://semver.org/spec/v2.0.0.html), without release candidates. "Release" commits are tagged like `v${major}.${minor}.${patch}`


## Release Process

This process should only be performed by a repo maintainer.

1. Create a PGP key associated with your identity.
2. Register your PGP key for use when signing tags.
	```bash
	gpg --list-keys \<$(git config --get user.email)\>  # Copy public key ID from output
	git config user.signingkey=$pubkey
	```
3. Review PRs since the last release. Ensure that all notable changes are represented in the CHANGELOG.
	1. Commit any CHANGELOG updates.
4. Tag and sign the HEAD.
	```bash
	git tag --sign v${major}.${minor}.${patch}
	```
6. Push the tag to github.
	```bash
	git push origin v0.0.0
	```
7. Create a [new release](https://github.com/ni/nilrt-snac/releases/new) in Github, attached to the tag you just pushed.
