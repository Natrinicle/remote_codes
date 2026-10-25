# Installable CUPS driver for Aimotech D30 / Print Master (RFCOMM ESC/POS).
# Package install is root once. Queue add is lpadmin. Jobs are lp/lpr.
#
#   make check
#   make deb
#   sudo make install          # only when the operator names it
#   sudo dpkg -i printer-driver-aimotech_*_all.deb

PREFIX ?= /usr
DESTDIR ?=
NAME := printer-driver-aimotech
VERSION := $(shell sed -n 's/^Version: //p' debian/control)
BACKENDDIR := $(PREFIX)/lib/cups/backend
FILTERDIR := $(PREFIX)/lib/cups/filter
DRVDIR := $(PREFIX)/share/cups/drv
PPDDIR := $(PREFIX)/share/ppd/aimotech
UPDATERDIR := $(PREFIX)/share/cups/ppd-updaters
SHAREDIR := $(PREFIX)/share/printer-driver-aimotech
BINDIR := $(PREFIX)/bin
DOCDIR := $(PREFIX)/share/doc/$(NAME)
DEB_ROOT := $(CURDIR)/.deb-root
DEB := $(CURDIR)/$(NAME)_$(VERSION)_all.deb

.PHONY: all check ppd install uninstall deb clean

all: check

ppd: aimotech.drv
	@if command -v ppdc >/dev/null 2>&1; then \
	  tmp=$$(mktemp -d); \
	  ppdc -d "$$tmp" aimotech.drv; \
	  cp "$$tmp/aimotechd30.ppd" Aimotech_D30.ppd; \
	  rm -rf "$$tmp"; \
	else \
	  echo "ppdc missing; keeping committed Aimotech_D30.ppd"; \
	fi

check:
	./aimotech_bt.py self-test
	./backend-aimotech self-test
	./rastertoaimotech.py self-test
	../encode_aimotech.py self-test
	@rm -rf "$(CURDIR)/.check-root"
	$(MAKE) install DESTDIR="$(CURDIR)/.check-root" PREFIX=/usr
	test -x "$(CURDIR)/.check-root/usr/lib/cups/backend/aimotech"
	test $$(stat -c '%a' $(CURDIR)/.check-root/usr/lib/cups/backend/aimotech) = 700
	test -x "$(CURDIR)/.check-root/usr/lib/cups/filter/rastertoaimotech"
	test -f "$(CURDIR)/.check-root/usr/share/cups/drv/aimotech.drv"
	test -f "$(CURDIR)/.check-root/usr/share/ppd/aimotech/Aimotech_D30.ppd"
	test -f "$(CURDIR)/.check-root/usr/share/printer-driver-aimotech/encode_aimotech.py"
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
	install -m 0700 backend-aimotech "$(DESTDIR)$(BACKENDDIR)/aimotech"
	install -m 0755 rastertoaimotech.py "$(DESTDIR)$(FILTERDIR)/rastertoaimotech"
	install -m 0755 aimotech-setup-printer "$(DESTDIR)$(BINDIR)/aimotech-setup-printer"
	install -m 0644 aimotech_bt.py "$(DESTDIR)$(SHAREDIR)/aimotech_bt.py"
	install -m 0644 ../encode_aimotech.py "$(DESTDIR)$(SHAREDIR)/encode_aimotech.py"
	install -m 0644 aimotech.drv "$(DESTDIR)$(DRVDIR)/aimotech.drv"
	install -m 0644 Aimotech_D30.ppd "$(DESTDIR)$(PPDDIR)/Aimotech_D30.ppd"
	install -m 0644 printer-driver-aimotech.ppd-updater \
	  "$(DESTDIR)$(UPDATERDIR)/printer-driver-aimotech.ppd-updater"
	install -m 0644 README.md "$(DESTDIR)$(DOCDIR)/README.md"
	install -m 0644 debian/copyright "$(DESTDIR)$(DOCDIR)/copyright"
	install -m 0644 debian/changelog "$(DESTDIR)$(DOCDIR)/changelog"

uninstall:
	rm -f "$(DESTDIR)$(BACKENDDIR)/aimotech"
	rm -f "$(DESTDIR)$(FILTERDIR)/rastertoaimotech"
	rm -f "$(DESTDIR)$(BINDIR)/aimotech-setup-printer"
	rm -f "$(DESTDIR)$(DRVDIR)/aimotech.drv"
	rm -f "$(DESTDIR)$(PPDDIR)/Aimotech_D30.ppd"
	rm -f "$(DESTDIR)$(UPDATERDIR)/printer-driver-aimotech.ppd-updater"
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
	chmod 0700 "$(DEB_ROOT)$(BACKENDDIR)/aimotech"
	dpkg-deb --root-owner-group --build "$(DEB_ROOT)" "$(DEB)"
	rm -rf "$(DEB_ROOT)"
	@echo "built $(DEB)"

clean:
	rm -rf "$(DEB_ROOT)" "$(CURDIR)/.check-root" "$(CURDIR)/.rpm-root"
	rm -f "$(CURDIR)/$(NAME)_"*.deb
