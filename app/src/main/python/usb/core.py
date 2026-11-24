"""usb.core API surface implemented on top of the Android Java bridge."""
import json
import time


class USBError(Exception):
    def __init__(self, message="", errno=None, backend_error=None):
        super().__init__(message)
        self.strerror = str(message)
        self.errno = errno
        self.backend_error = backend_error


class USBTimeoutError(USBError):
    pass


class _Info:
    def __init__(self, d):
        self._d = d
        self.bLength = d.get("bLength", 0)
        self.bDescriptorType = d.get("bDescriptorType", 0)
        self.bEndpointAddress = int(d.get("endpointAddress", 0) or 0)
        self.bmAttributes = d.get("bmAttributes", 0)
        self.wMaxPacketSize = int(d.get("maxPacketSize", 512) or 512)
        self.bInterval = d.get("interval", 0)
        self.bInterfaceNumber = int(d.get("interfaceNumber", 0) or 0)
        self.bAlternateSetting = d.get("alternateSetting", 0)
        self.bNumEndpoints = len(d.get("endpoints", []))
        self.bInterfaceClass = int(d.get("interfaceClass", 0) or 0)
        self.bInterfaceSubClass = d.get("interfaceSubClass", 0)
        self.bInterfaceProtocol = d.get("interfaceProtocol", 0)
        self.iInterface = d.get("interfaceName", "")
        self.extra = b""

    def __repr__(self):
        return "<USB descriptor %s>" % getattr(self, "bInterfaceNumber", self.bEndpointAddress)


class Endpoint:
    def __init__(self, device, info, interface):
        self.device = device
        self.interface = interface
        self._info = info
        self.bEndpointAddress = info.bEndpointAddress
        self.wMaxPacketSize = info.wMaxPacketSize
        self.bmAttributes = info.bmAttributes
        self.bInterval = info.bInterval

    def write(self, data, timeout=None):
        return self.device._bridge.bulk_write(self.device.device_id,
                                              self.bEndpointAddress,
                                              bytes(data),
                                              timeout or self.device.timeout)

    def read(self, size, timeout=None):
        data = self.device._bridge.bulk_read(self.device.device_id,
                                             self.bEndpointAddress,
                                             size,
                                             timeout or self.device.timeout)
        if data is None:
            raise USBTimeoutError("bulk read timed out")
        return data

    def clear_halt(self):
        self.device._bridge.clear_halt(self.device.device_id, self.bEndpointAddress)

    def reset(self):
        self.clear_halt()


class Interface:
    def __init__(self, device, info):
        self.device = device
        self._info = info
        self.bInterfaceNumber = info.bInterfaceNumber
        self.bAlternateSetting = info.bAlternateSetting
        self.bNumEndpoints = info.bNumEndpoints
        self.bInterfaceClass = info.bInterfaceClass
        self.bInterfaceSubClass = info.bInterfaceSubClass
        self.bInterfaceProtocol = info.bInterfaceProtocol
        self.iInterface = info.iInterface
        self.extra = b""
        self.endpoints = [Endpoint(device, _Info(e), self)
                          for e in (info._d.get("endpoints") or [])]

    def __iter__(self): return iter(self.endpoints)
    def __getitem__(self, i): return self.endpoints[i]
    def __len__(self): return len(self.endpoints)
    def __repr__(self): return "<USB interface %d>" % self.bInterfaceNumber


class Configuration:
    def __init__(self, device, info):
        self.device = device
        self._info = info
        self.bLength = info.get("bLength", 0)
        self.bDescriptorType = 2
        self.wTotalLength = 0
        self.bNumInterfaces = max(1, len(info.get("interfaces", [])))
        self.bConfigurationValue = int(info.get("configurationValue", 1) or 1)
        self.iConfiguration = info.get("configurationName", "")
        self.bmAttributes = info.get("attributes", 0)
        self.MaxPower = info.get("maxPower", 0)
        self.extra = b""
        self.interfaces = [Interface(device, _Info(i)) for i in info.get("interfaces", [])]

    def __iter__(self): return iter(self.interfaces)
    def __getitem__(self, i): return self.interfaces[i]
    def __len__(self): return len(self.interfaces)
    def __repr__(self): return "<USB configuration %d>" % self.bConfigurationValue


class USBDevice:
    def __init__(self, info):
        self._bridge = _bridge()
        self._info = info
        self.device_id = info.get("deviceId", "")
        self.idVendor = int(info.get("vendorId", 0) or 0)
        self.idProduct = int(info.get("productId", 0) or 0)
        self.bDeviceClass = int(info.get("deviceClass", 0) or 0)
        self.bDeviceSubClass = int(info.get("deviceSubClass", 0) or 0)
        self.bDeviceProtocol = int(info.get("deviceProtocol", 0) or 0)
        self.bMaxPacketSize0 = int(info.get("maxPacketSize", 64) or 64)
        self.idbcdDevice = int(info.get("deviceVersion", 0) or 0)
        self.iManufacturer = info.get("manufacturerName", "")
        self.iProduct = info.get("productName", "")
        self.iSerialNumber = info.get("serialNumber", "")
        self.bus = int(info.get("busNumber", 1) or 1)
        self.address = int(info.get("deviceAddress", 1) or 1)
        self.port_numbers = info.get("portNumbers", [])
        self.timeout = 1000
        self._configuration = None
        self._claimed = set()

    def _config_info(self):
        cfg = self._info.get("configuration") or {}
        if not cfg.get("interfaces"):
            # Synthesize one interface with bulk endpoints when the Java
            # bridge didn't provide a full descriptor tree.
            cfg = {"configurationValue": 1,
                   "interfaces": [{"interfaceNumber": 0, "interfaceClass": 255,
                                   "endpoints": [
                                       {"endpointAddress": 0x81, "maxPacketSize": 512},
                                       {"endpointAddress": 0x01, "maxPacketSize": 512},
                                   ]}]}
        return cfg

    def get_active_configuration(self):
        if self._configuration is None:
            self.set_configuration()
        return self._configuration

    def set_configuration(self, configuration=None):
        self._bridge.set_configuration(self.device_id, configuration or 1)
        self._configuration = Configuration(self, self._config_info())
        return self._configuration

    def ctrl_transfer(self, bmRequestType, bRequest, wValue=0, wIndex=0,
                      data_or_wLength=None, timeout=None):
        result = self._bridge.control_transfer(
            self.device_id, int(bmRequestType), int(bRequest), int(wValue),
            int(wIndex), data_or_wLength, timeout or self.timeout)
        if result is None:
            raise USBError("control transfer failed")
        return result

    # Kernel-driver APIs are no-ops on Android (UsbManager handles claiming).
    def is_kernel_driver_active(self, interface): return False
    def detach_kernel_driver(self, interface): pass
    def attach_kernel_driver(self, interface): pass
    def reset(self): self._bridge.reset_device(self.device_id)
    def set_interface_altsetting(self, interface=0, alternate_setting=0): pass
    def clear_halt(self, endpoint): self._bridge.clear_halt(self.device_id, endpoint)

    def __iter__(self): return iter(self.get_active_configuration().interfaces)
    def __repr__(self):
        return "<USB device %04x:%04x>" % (self.idVendor, self.idProduct)


def _bridge():
    from android_bridge import bridge
    return bridge


def find(find_all=False, idVendor=None, idProduct=None, bDeviceClass=None,
         backend=None, **kwargs):
    try:
        infos = _bridge().list_usb_devices()
    except Exception as exc:
        print("usb.core.find:", exc)
        return [] if find_all else None

    devices = []
    for info in infos:
        if idVendor is not None and int(info.get("vendorId", 0)) != idVendor:
            continue
        if idProduct is not None and int(info.get("productId", 0)) != idProduct:
            continue
        if bDeviceClass is not None and int(info.get("deviceClass", 0)) != bDeviceClass:
            continue
        devices.append(USBDevice(info))
    return devices if find_all else (devices[0] if devices else None)


def enumerate_devices(**kwargs):
    return find(find_all=True, **kwargs)
