"""Import-compatible Unicorn Engine shim for Android.

Unicorn has no Android wheel.  Constants and the Uc API used by mtkclient's
optional preprocessing tools are kept so imports succeed.  Actual emulation
raises UcError with a clear message (or delegates to a Java provider when one
is installed).
"""
UC_ARCH_ARM = 1
UC_ARCH_ARM64 = 2
UC_ARCH_MIPS = 3
UC_ARCH_X86 = 4

UC_MODE_ARM = 0
UC_MODE_THUMB = 1
UC_MODE_LITTLE_ENDIAN = 0
UC_MODE_BIG_ENDIAN = 1 << 30

UC_MEM_READ = 16
UC_MEM_WRITE = 17
UC_MEM_FETCH = 18
UC_MEM_READ_UNMAPPED = 19
UC_MEM_WRITE_UNMAPPED = 20
UC_MEM_FETCH_UNMAPPED = 21
UC_MEM_WRITE_PROT = 22
UC_MEM_READ_PROT = 23
UC_MEM_FETCH_PROT = 24
UC_MEM_READ_AFTER = 25
UC_HOOK_CODE = 1
UC_HOOK_MEM_READ = 2 | UC_MEM_READ
UC_HOOK_MEM_WRITE = 4 | UC_MEM_WRITE
UC_HOOK_MEM_INVALID = 10 | UC_MEM_READ_UNMAPPED | UC_MEM_WRITE_UNMAPPED | UC_MEM_FETCH_UNMAPPED


class UcError(Exception):
    pass


class Uc:
    def __init__(self, arch, mode=0):
        self.arch = arch
        self.mode = mode
        self._hooks = []

    def mem_map(self, address, size, perms=7):
        try:
            from android_bridge import bridge
            bridge.uc_mem_map(self.arch, address, size, perms)
        except Exception as exc:
            raise UcError("Unicorn emulation is unavailable on Android: %s" % exc)

    def mem_write(self, address, data):
        try:
            from android_bridge import bridge
            bridge.uc_mem_write(self.arch, address, bytes(data))
        except Exception as exc:
            raise UcError("Unicorn emulation is unavailable on Android: %s" % exc)

    def mem_read(self, address, size):
        try:
            from android_bridge import bridge
            return bridge.uc_mem_read(self.arch, address, size)
        except Exception as exc:
            raise UcError("Unicorn emulation is unavailable on Android: %s" % exc)

    def reg_write(self, reg_id, value):
        try:
            from android_bridge import bridge
            bridge.uc_reg_write(self.arch, reg_id, value)
        except Exception as exc:
            raise UcError("Unicorn emulation is unavailable on Android: %s" % exc)

    def reg_read(self, reg_id):
        try:
            from android_bridge import bridge
            return bridge.uc_reg_read(self.arch, reg_id)
        except Exception as exc:
            raise UcError("Unicorn emulation is unavailable on Android: %s" % exc)

    def hook_add(self, *a, **kw): return 1
    def hook_del(self, handle): pass

    def emu_start(self, begin, until, timeout=0, count=0):
        try:
            from android_bridge import bridge
            return bridge.uc_emu_start(self.arch, begin, until, timeout, count)
        except Exception as exc:
            raise UcError("Unicorn emulation is unavailable on Android: %s" % exc)

    def emu_stop(self): pass
    def close(self): pass
