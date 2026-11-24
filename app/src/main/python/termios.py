"""termios constants/no-ops for Android (serial lines are handled by UsbManager)."""
TCSANOW = 0
TCSADRAIN = 1
TCSAFLUSH = 2
TCIFLUSH = 0
TCOFLUSH = 1
TCIOFLUSH = 2
TCOOFF = 0
TCOON = 1
TCIOFF = 2
TCION = 3

IGNBRK = 0
BRKINT = 0
IGNPAR = 0
PARMRK = 0
INPCK = 0
ISTRIP = 0
INLCR = 0
IGNCR = 0
ICRNL = 0
IXON = 0
OPOST = 0
ECHO = 0
ECHONL = 0
ICANON = 0
ISIG = 0
IEXTEN = 0
CSIZE = 0
PARENB = 0
PARODD = 0
CS5 = 0
CS6 = 0
CS7 = 0
CS8 = 0
CLOCAL = 0
CREAD = 0
VMIN = 6
VTIME = 5


def tcgetattr(fd):
    return [0] * 32


def tcsetattr(fd, when, attrs):
    return None


def tcflush(fd, queue):
    if hasattr(fd, "reset_input_buffer") and queue in (TCIFLUSH, TCIOFLUSH):
        fd.reset_input_buffer()
    return None


def tcdrain(fd): return None


def tcsendbreak(fd, duration): return None


def cfsetispeed(attrs, speed): return None


def cfsetospeed(attrs, speed): return None


def cfmakeraw(attrs): return attrs
