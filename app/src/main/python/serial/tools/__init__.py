"""serial.tools.list_ports compatibility on Android."""
import sys
import types


class ListPortInfo:
    def __init__(self, info):
        self.device = info.get("device", "")
        self.name = info.get("name") or self.device.rsplit("/", 1)[-1]
        self.description = info.get("description") or self.name
        self.manufacturer = info.get("manufacturer", "")
        self.product = info.get("product", "")
        self.serial_number = info.get("serialNumber", "")
        self.vid = int(info.get("vendorId", 0) or 0)
        self.pid = int(info.get("productId", 0) or 0)
        self.location = info.get("location", "")
        self.interface = info.get("interface")

    def __str__(self):
        return self.device
    __repr__ = __str__


def comports(include_links=False):
    try:
        from android_bridge import bridge
        return [ListPortInfo(x) for x in bridge.list_serial_ports()]
    except Exception as exc:
        print("serial.tools.list_ports.comports:", exc)
        return []


list_ports = sys.modules[__name__]
sys.modules.setdefault("serial.tools.list_ports", sys.modules[__name__])
