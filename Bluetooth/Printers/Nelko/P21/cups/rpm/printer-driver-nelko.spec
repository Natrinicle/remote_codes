Name:           printer-driver-nelko
Version:        0.3.5
Release:        1%{?dist}
Summary:        CUPS driver for Nelko P21 Bluetooth label printers
License:        CC0
BuildArch:      noarch
Requires:       cups, python3, python3-pillow
Recommends:     bluez, poppler-utils

%description
Userspace CUPS backend (nelko://), filter (rastertonelko), and PPD/drv
for Nelko P21 TSPL2 over RFCOMM channel 1.

Install as root once. An lpadmin user creates the queue. Users allowed
by the CUPS print policy then lp/lpr without root. Backend mode 0700
runs as root so job submitters do not need the bluetooth group.

%install
make -C %{_sourcedir} install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%post
if [ -e %{_prefix}/lib/cups/backend/nelko ]; then
  chmod 0700 %{_prefix}/lib/cups/backend/nelko
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl try-reload-or-restart cups.service >/dev/null 2>&1 || :
fi

%files
%attr(0700,root,root) %{_prefix}/lib/cups/backend/nelko
%attr(0755,root,root) %{_prefix}/lib/cups/filter/rastertonelko
%attr(0755,root,root) %{_bindir}/nelko-setup-printer
%{_prefix}/share/printer-driver-nelko/nelko_bt.py
%{_prefix}/share/cups/drv/nelko.drv
%{_prefix}/share/ppd/nelko/Nelko_P21.ppd
%{_prefix}/share/cups/ppd-updaters/printer-driver-nelko.ppd-updater
%doc %{_prefix}/share/doc/printer-driver-nelko/README.md
%license %{_prefix}/share/doc/printer-driver-nelko/copyright

%changelog
* Sun Oct 25 2026 remote_codes pack <remote-codes@example.com> - 0.3.5-1
- Dash-separated MAC hosts so CUPS lpadmin does not treat colons as a port
* Sat Oct 25 2026 remote_codes pack <remote-codes@example.com> - 0.3.3-1
- Initial CUPS driver package for Nelko P21 RFCOMM TSPL2
