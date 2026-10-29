Name:           printer-driver-aimotech
Version:        0.3.7
Release:        1%{?dist}
Summary:        CUPS driver for Aimotech D30 Print Master label printers
License:        CC0
BuildArch:      noarch
Requires:       cups, python3, python3-pillow
Recommends:     bluez, poppler-utils

%description
Userspace CUPS backend (aimotech://), filter (rastertoaimotech), and
PPD/drv for Aimotech / Quin / Phomemo D30 ESC/POS GS v 0 over RFCOMM
channel 1 (Print Master app family).

Install as root once. An lpadmin user creates the queue. Users allowed
by the CUPS print policy then lp/lpr without root. Backend mode 0700
runs as root so job submitters do not need the bluetooth group.

Framing is recovered from Print Master 5.23.1. Live D30 eject is
unproven in this pack revision.

%install
make -C %{_sourcedir} install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%post
if [ -e %{_prefix}/lib/cups/backend/aimotech ]; then
  chmod 0700 %{_prefix}/lib/cups/backend/aimotech
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl try-reload-or-restart cups.service >/dev/null 2>&1 || :
fi

%files
%attr(0700,root,root) %{_prefix}/lib/cups/backend/aimotech
%attr(0755,root,root) %{_prefix}/lib/cups/filter/rastertoaimotech
%attr(0755,root,root) %{_bindir}/aimotech-setup-printer
%{_prefix}/share/printer-driver-aimotech/aimotech_bt.py
%{_prefix}/share/printer-driver-aimotech/encode_aimotech.py
%{_prefix}/share/cups/drv/aimotech.drv
%{_prefix}/share/ppd/aimotech/Aimotech_D30.ppd
%{_prefix}/share/cups/ppd-updaters/printer-driver-aimotech.ppd-updater
%doc %{_prefix}/share/doc/printer-driver-aimotech/README.md
%license %{_prefix}/share/doc/printer-driver-aimotech/copyright

%changelog
* Tue Oct 27 2026 remote_codes pack <remote-codes@example.com> - 0.3.7-1
- Last-seen BlueZ cache so Get-Devices still lists the D30 when it is off
- setup helper sets Description and retry-job so the KDE queue persists
* Sun Oct 25 2026 remote_codes pack <remote-codes@example.com> - 0.3.6-1
- Rebuild so installed PPD FileVersion matches git
* Sun Oct 25 2026 remote_codes pack <remote-codes@example.com> - 0.3.5-1
- Dash-separated MAC hosts so CUPS lpadmin does not treat colons as a port
* Sat Oct 25 2026 remote_codes pack <remote-codes@example.com> - 0.3.4-1
- Initial CUPS driver package for Aimotech D30 Print Master GS v 0
