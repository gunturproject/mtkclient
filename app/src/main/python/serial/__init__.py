"""pyserial-compatible shim backed by Android USB host / root serial nodes."""
import threading
import time

EIGHTBITS = 8
SEVENBITS = 7
SIXBITS = 6
FIVEBITS = 5
PARITY_NONE = 'N'
PARITY_EVEN = 'E'
PARITY_ODD = 'O'
PARITY_MARK = 'M'
PARITY_SPACE = 'S'
STOPBITS_ONE = 1
STOPBITS_ONE_POINT_FIVE = 1.5
STOPBITS_TWO = 2

from . import tools  # noqa: E402  (exposes serial.tools.list_ports)


class SerialException(Exception):
    pass


class SerialTimeoutException(SerialException):
    pass


class Serial:
    """Minimal pyserial object.

    On Android a "serial port" is either a USB CDC-ACM device exposed through
    UsbManager (handled by the Java bridge) or a character device such as
    /dev/ttyS0 accessible as root.  The bridge abstracts both.
    """

    def __init__(self, port=None, baudrate=9600, bytesize=EIGHTBITS,
                 parity=PARITY_NONE, stopbits=STOPBITS_ONE, timeout=None,
                 xonxoff=False, rtscts=False, dsrdtr=False, **kwargs):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.xonxoff = xonxoff
        self.rtscts = rtscts
        self.dsrdtr = dsrdtr
        self.is_open = False
        self._handle = None
        self._rx = bytearray()
        self._lock = threading.RLock()
        self.fd = self
        try:
            self.open()
        except Exception:
            pass

    @property
    def name(self):
        return str(self.port)

    def open(self):
        from android_bridge import bridge
        self._handle = bridge.serial_open(str(self.port), self.baudrate,
                                          self.bytesize, self.parity,
                                          self.stopbits)
        self.is_open = bool(self._handle)
        if not self.is_open:
            raise SerialException("cannot open %s" % self.port)
        return self

    def close(self):
        if self.is_open and self._handle:
            try:
                from android_bridge import bridge
                bridge.serial_close(self._handle)
            finally:
                self._handle = None
        self.is_open = False

    def __enter__(self): return self.open()
    def __exit__(self, *a): self.close()

    def write(self, data):
        if not self.is_open or not self._handle:
            raise SerialException("port is not open")
        from android_bridge import bridge
        n = bridge.serial_write(self._handle, bytes(data))
        return n if n is not None else len(data)

    def read(self, size=1):
        if size is None or size < 0:
            size = 1
        deadline = None
        if self.timeout is not None and self.timeout > 0:
            deadline = time.monotonic() + float(self.timeout) / 1000.0 if self.timeout > 10 else time.monotonic() + float(self.timeout)
        while len(self._rx) < size:
            if deadline is not None and time.monotonic() >= deadline:
                break
            from android_bridge import bridge
            chunk = bridge.serial_read(self._handle, size - len(self._rx), 100)
            if chunk:
                self._rx.extend(chunk)
            else:
                time.sleep(0.005)
        out = bytes(self._rx[:size])
        del self._rx[:size]
        return out

    def read_all(self):
        out = bytes(self._rx)
        self._rx.clear()
        return out

    @property
    def in_waiting(self):
        from android_bridge import bridge
        return bridge.serial_available(self._handle) if self._handle else 0

    def reset_input_buffer(self):
        self._rx.clear()
        if self._handle:
            from android_bridge import bridge
            bridge.serial_discard_input(self._handle)

    def reset_output_buffer(self): pass
    def flush(self): pass
    def send_break(self, duration=0.25):
        if self._handle:
            from android_bridge import bridge
            bridge.serial_send_break(self._handle, duration)

    def setbreak(self): self.send_break()
    def clear_break(self): pass

    @property
    def rts(self): return self._props.get('rts', False) if hasattr(self, '_props') else False
    @rts.setter
    def rts(self, v):
        if not hasattr(self, '_props'): self._props = {}
        self._props['rts'] = bool(v)
        if self._handle:
            from android_bridge import bridge
            bridge.serial_set_signals(self._handle, bool(v), None)
    @property
    def dtr(self): return self._props.get('dtr', False) if hasattr(self, '_props') else False
    @dtr.setter
    def dtr(self, v):
        if not hasattr(self, '_props'): self._props = {}
        self._props['dtr'] = bool(v)
        if self._handle:
            from android_bridge import bridge
            bridge.serial_set_signals(self._handle, None, bool(v))

    @property
    def cts(self): return False
    @property
    def dsr(self): return False
    @property
    def ri(self): return False
    @property
    def cd(self): return False
