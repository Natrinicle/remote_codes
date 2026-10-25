# Installable CUPS driver for Nelko P21 (RFCOMM TSPL2).
# Package install is root once. Queue add is lpadmin. Jobs are lp/lpr.
#
#   make check
#   make deb
#   sudo make install          # only when the operator names it
#   sudo dpkg -i printer-driver-nelko_*_all.deb

PREFIX ?= /usr
DESTDIR ?=
NAME := printer-driver-nelko
VERSION := $(shell sed -n 's/^Version: //p' debian/control)
BACKENDDIR := $(PREFIX)/lib/cups/backend
FILTERDIR := $(PREFIX)/lib/cups/filter
DRVDIR := $(PREFIX)/share/cups/drv
PPDDIR := $(PREFIX)/share/ppd/nelko
UPDATERDIR := $(PREFIX)/share/cups/ppd-updaters
SHAREDIR := $(PREFIX)/share/printer-driver-nelko
BINDIR := $(PREFIX)/bin
DOCDIR := $(PREFIX)/share/doc/$(NAME)
DEB_ROOT := $(CURDIR)/.deb-root
DEB := $(CURDIR)/$(NAME)_$(VERSION)_all.deb

.PHONY: all check ppd install uninstall deb clean

all: check

ppd: nelko.drv
	@if command -v ppdc >/dev/null 2>&1; then \
	  tmp=$$(mktemp -d); \
	  ppdc -d "$$tmp" nelko.drv; \
	  cp "$$tmp/nelkop21.ppd" Nelko_P21.ppd; \
	  rm -rf "$$tmp"; \
	else \
	  echo "ppdc missing; keeping committed Nelko_P21.ppd"; \
	fi

check:
	./nelko_bt.py self-test
	./backend-nelko self-test
	./rastertonelko.py self-test
	../encode_nelko.py self-test
	@rm -rf "$(CURDIR)/.check-root"
	$(MAKE) install DESTDIR="$(CURDIR)/.check-root" PREFIX=/usr
	test -x "$(CURDIR)/.check-root/usr/lib/cups/backend/nelko"
	test $$(stat -c '%a' $(CURDIR)/.check-root/usr/lib/cups/backend/nelko) = 700
	test -x "$(CURDIR)/.check-root/usr/lib/cups/filter/rastertonelko"
	test -f "$(CURDIR)/.check-root/usr/share/cups/drv/nelko.drv"
	test -f "$(CURDIR)/.check-root/usr/share/ppd/nelko/Nelko_P21.ppd"
	rm -rf "$(CURDIR)/.check-root"
	@echo "check ok"

install:
	install -d "$(DESTDIR)$(BACKENDDIR)"
	install -d "$(DESTDIR)$(FILTERDIR)"
	install -d "$(DESTDIR)$(DRVDIR)"
	install -d "$(DESTDIR)$(PPDDIR)"
	install -d "$(DESTDIR)$(UPDATERDIR)"
	install -d "$(DESTDIR)$(SHAREDIR)"
	install -d "$(DESTDIR)$(BINDIR)"
	install -d "$(DESTDIR)$(DOCDIR)"
	install -m 0700 backend-nelko "$(DESTDIR)$(BACKENDDIR)/nelko"
	install -m 0755 rastertonelko.py "$(DESTDIR)$(FILTERDIR)/rastertonelko"
	install -m 0755 nelko-setup-printer "$(DESTDIR)$(BINDIR)/nelko-setup-printer"
	install -m 0644 nelko_bt.py "$(DESTDIR)$(SHAREDIR)/nelko_bt.py"
	install -m 0644 nelko.drv "$(DESTDIR)$(DRVDIR)/nelko.drv"
	install -m 0644 Nelko_P21.ppd "$(DESTDIR)$(PPDDIR)/Nelko_P21.ppd"
	install -m 0644 printer-driver-nelko.ppd-updater \
	  "$(DESTDIR)$(UPDATERDIR)/printer-driver-nelko.ppd-updater"
	install -m 0644 README.md "$(DESTDIR)$(DOCDIR)/README.md"
	install -m 0644 debian/copyright "$(DESTDIR)$(DOCDIR)/copyright"
	install -m 0644 debian/changelog "$(DESTDIR)$(DOCDIR)/changelog"

uninstall:
	rm -f "$(DESTDIR)$(BACKENDDIR)/nelko"
	rm -f "$(DESTDIR)$(FILTERDIR)/rastertonelko"
	rm -f "$(DESTDIR)$(BINDIR)/nelko-setup-printer"
	rm -f "$(DESTDIR)$(DRVDIR)/nelko.drv"
	rm -f "$(DESTDIR)$(PPDDIR)/Nelko_P21.ppd"
	rm -f "$(DESTDIR)$(UPDATERDIR)/printer-driver-nelko.ppd-updater"
	rm -rf "$(DESTDIR)$(SHAREDIR)"
	rm -rf "$(DESTDIR)$(DOCDIR)"

deb: check
	rm -rf "$(DEB_ROOT)"
	$(MAKE) install DESTDIR="$(DEB_ROOT)" PREFIX=/usr
	install -d "$(DEB_ROOT)/DEBIAN"
	install -m 0644 debian/control "$(DEB_ROOT)/DEBIAN/control"
	install -m 0755 debian/postinst "$(DEB_ROOT)/DEBIAN/postinst"
	install -m 0755 debian/prerm "$(DEB_ROOT)/DEBIAN/prerm"
	find "$(DEB_ROOT)" -type d -exec chmod 0755 {} +
	chmod 0700 "$(DEB_ROOT)$(BACKENDDIR)/nelko"
	dpkg-deb --root-owner-group --build "$(DEB_ROOT)" "$(DEB)"
	rm -rf "$(DEB_ROOT)"
	@echo "built $(DEB)"

clean:
	rm -rf "$(DEB_ROOT)" "$(CURDIR)/.check-root" "$(CURDIR)/.rpm-root"
	rm -f "$(CURDIR)/$(NAME)_"*.deb
