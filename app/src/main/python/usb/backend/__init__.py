"""No native libusb backend exists on Android; UsbManager is used instead."""


class _BackendModule:
    @staticmethod
    def get_backend(*a, **kw):
        return None


class _LibUSB0(_BackendModule):
    pass


class _LibUSB1(_BackendModule):
    pass


libusb0 = _LibUSB0()
libusb1 = _LibUSB1()
