"""Android has no loadable libusb1 through ctypes; UsbManager is used instead."""
def get_backend(*args, **kwargs):
    return None
