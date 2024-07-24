# SPDX-License-Identifier: MIT

.DEFAULT_GOAL := all

SHELL = /bin/sh

## VARIABLES

PACKAGE = nilrt-snac
VERSION := $(shell git describe)

# GNU directories
prefix ?= /usr/local
exec_prefix ?= $(prefix)
bindir ?= $(exec_prefix)/bin

datarootdir ?= $(prefix)/share

datadir ?= $(datarootdir)
docdir ?= $(datarootdir)/doc
libdir ?= $(exec_prefix)/lib
sbindir ?= $(exec_prefix)/sbin

SRC_FILES = \
	src/configure-nilrt-snac \
	src/nilrt-snac-conflicts/control \
	src/nilrt-snac \
	src/util.sh \

DIST_FILES = \
	$(SRC_FILES) \
	LICENSE \
	README.md \
	Makefile \



# REAL TARGETS #
################

$(PACKAGE)-$(VERSION).tar.gz : $(DIST_FILES)
	tar -czf $@ $(DIST_FILES)


src/nilrt-snac-conflicts/nilrt-snac-conflicts.ipk :
	make -C src/nilrt-snac-conflicts $(@F)


# PHONY TARGETS #
#################

.PHONY : all clean dist install uninstall

all : nilrt-snac-conflicts


clean :
	rm -f ./$(PACKAGE)-*.tar.gz
	make -C src/nilrt-snac-conflicts clean


dist : $(PACKAGE)-$(VERSION).tar.gz


install : $(DIST_FILES) src/nilrt-snac-conflicts/nilrt-snac-conflicts.ipk
	mkdir -p $(DESTDIR)$(sbindir)
	install -o 0 -g 0 --mode=0755 -t "$(DESTDIR)$(sbindir)" \
		src/nilrt-snac

	mkdir -p $(DESTDIR)$(libdir)/$(PACKAGE)
	install --mode=0444 -t "$(DESTDIR)$(libdir)/$(PACKAGE)" \
		src/configure-nilrt-snac \
		src/util.sh \

	mkdir -p $(DESTDIR)$(docdir)/$(PACKAGE)
	install --mode=0444 -t "$(DESTDIR)$(docdir)/$(PACKAGE)" \
		LICENSE \
		README.md

	# install conflicts IPK
	mkdir -p $(DESTDIR)$(datarootdir)/$(PACKAGE)
	install --mode=0644 -t "$(DESTDIR)$(datarootdir)/$(PACKAGE)" \
		src/nilrt-snac-conflicts/nilrt-snac-conflicts.ipk


uninstall :
	rm -vf $(DESTDIR)$(sbindir)/nilrt-snac
	rm -rvf $(DESTDIR)$(libdir)/$(PACKAGE)
	rm -rvf $(DESTDIR)$(docdir)/$(PACKAGE)
