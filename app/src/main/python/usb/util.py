"""usb.util compatibility helpers."""
from .core import USBDevice

ENDPOINT_OUT = 0x00
ENDPOINT_IN = 0x80


def endpoint_direction(address):
    return address & 0x80


def find_descriptor(container, custom_match=None, **kwargs):
    candidates = []
    if hasattr(container, "interfaces"):
        for itf in container.interfaces:
            candidates.append(itf)
            candidates.extend(itf.endpoints)
    elif hasattr(container, "endpoints"):
        candidates.extend(container.endpoints)
    for candidate in candidates:
        if custom_match is not None and not custom_match(candidate):
            continue
        ok = True
        for key, value in kwargs.items():
            if getattr(candidate, key, None) != value:
                ok = False
                break
        if ok:
            return candidate
    return None


def claim_interface(device, interface):
    if hasattr(device, "_claimed"):
        device._claimed.add(interface)
    return device


def release_interface(device, interface):
    if hasattr(device, "_claimed"):
        device._claimed.discard(interface)


def dispose_resources(device):
    if hasattr(device, "_claimed"):
        device._claimed.clear()


def get_string(device, index, length=None):
    return device._info.get("serialNumber", "") if hasattr(device, "_info") else ""


def build_descriptor(*a, **kw): return b""


def parse_descriptor(data): return None


def lookup(config, interface, alternate=0):
    return find_descriptor(config, bInterfaceNumber=interface)
