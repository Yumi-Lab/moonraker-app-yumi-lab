"""Lightweight device identification helpers.

No heavy dependencies — safe to import from anywhere.
"""

import io


def read(path):
    try:
        with io.open(path, 'rt', encoding='utf8') as f:
            return f.readline().strip('\0').strip()
    except Exception:
        return ''


def get_mac_address():
    """Read MAC address from /sys/class/net, prioritizing end0.

    Tries end0 (Trixie), then eth0, then wlan0.
    Returns empty string if none available.
    """
    for iface in ('end0', 'eth0', 'wlan0'):
        path = f'/sys/class/net/{iface}/address'
        mac = read(path)
        if mac and mac != '00:00:00:00:00:00':
            return mac
    return ''


def mac_to_hexid(mac_address):
    """Convert MAC address to YUMI hexid (same format as YUMI_SYNC).

    Example: dc:a6:32:xx:yy:zz -> DCA632XXYYZZ
    """
    if not mac_address:
        return ''
    return mac_address.replace(':', '').upper()
