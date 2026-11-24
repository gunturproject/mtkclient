"""Android has no libusb0; return None so mtkclient falls back to UsbManager."""
def get_backend(*args, **kwargs):
    return None
