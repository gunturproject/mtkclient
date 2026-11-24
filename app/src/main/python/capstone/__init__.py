"""Import-compatible Capstone shim for Android.

Native Capstone has no Chaquopy wheel.  The shim keeps every constant and the
Cs API used by mtkclient.  Disassembly is delegated to an optional Java bridge
provider or to `llvm-objdump` / `objdump` on a rooted device.  Importing the
GUI always succeeds; only calling disasm() without a backend raises CsError.
"""
import re
import shutil
import subprocess

CS_ARCH_ARM = 0
CS_ARCH_ARM64 = 1
CS_ARCH_MIPS = 2
CS_ARCH_X86 = 3
CS_ARCH_PPC = 4
CS_ARCH_SPARC = 5
CS_ARCH_SYSZ = 6
CS_ARCH_XCORE = 7
CS_ARCH_RISCV = 8

CS_MODE_LITTLE_ENDIAN = 0
CS_MODE_BIG_ENDIAN = 1 << 30
CS_MODE_ARM = 0
CS_MODE_THUMB = 1
CS_MODE_V8 = 2
CS_MODE_MCLASS = 4
CS_MODE_MICRO = 8
CS_MODE_MIPS32 = 16
CS_MODE_MIPS64 = 32
CS_MODE_MIPS32R6 = 64
CS_MODE_16 = 128
CS_MODE_32 = 256
CS_MODE_64 = 512
CS_MODE_V9 = 1024

CS_OPT_SYNTAX_INTEL = 1
CS_OPT_SYNTAX_ATT = 2


class CsError(Exception):
    pass


class CsInsn:
    def __init__(self, address, mnemonic, op_str, size=4):
        self.address = address
        self.mnemonic = mnemonic
        self.op_str = op_str
        self.size = size
        self.bytes = b""

    def __str__(self):
        return "%s %s" % (self.mnemonic, self.op_str)
    __repr__ = __str__


_ARCH_TRIPLE = {
    CS_ARCH_ARM: "arm",
    CS_ARCH_ARM64: "aarch64",
    CS_ARCH_MIPS: "mips",
    CS_ARCH_X86: "x86",
    CS_ARCH_PPC: "powerpc",
    CS_ARCH_SPARC: "sparc",
    CS_ARCH_SYSZ: "systemz",
    CS_ARCH_XCORE: "xcore",
}


class Cs:
    def __init__(self, arch, mode=0):
        self.arch = arch
        self.mode = mode
        self.syntax = CS_OPT_SYNTAX_INTEL
        self.detail = False

    def option(self, *a): pass

    def disasm(self, code, address=0, count=0):
        if isinstance(code, (bytearray, memoryview)):
            code = bytes(code)
        if not isinstance(code, bytes):
            raise CsError("disasm expects bytes")

        try:
            from android_bridge import bridge
            rows = bridge.disasm(self.arch, self.mode, code, address)
            if rows:
                return [CsInsn(int(r[0]), r[1], r[2], int(r[3])) for r in rows]
        except Exception:
            pass

        triple = _ARCH_TRIPLE.get(self.arch)
        tool = shutil.which("llvm-objdump") or shutil.which("objdump")
        if tool and triple:
            try:
                path = "/data/data/com.opencode.android/cache/tmp/capstone-input.bin"
                with open(path, "wb") as f:
                    f.write(code)
                args = [tool, "-d", "--triple=%s-none-none-eabi" % triple, path] \
                    if "llvm" in tool else [tool, "-D", "-b", "binary", "-m",
                                            "i386:x86-64" if self.arch == CS_ARCH_X86 else "arm", path]
                out = subprocess.run(args, capture_output=True, timeout=20)
                result = []
                for line in out.stdout.decode("utf-8", "replace").splitlines():
                    m = re.match(r"\s*([0-9a-fA-F]+):\s*((?:[0-9a-fA-F]{2}\s+)+)\s*([a-z][a-z0-9.]*)\s*(.*)", line)
                    if not m:
                        continue
                    result.append(CsInsn(int(m.group(1), 16), m.group(3), m.group(4).strip(),
                                         len(m.group(2).split())))
                if result:
                    return result
            except Exception:
                pass
        raise CsError("No disassembler backend on Android for architecture %s. "
                      "Install a disassembler provider or use a desktop build for this tool." % triple)

    def disasm_lite(self, code, address=0, count=0):
        return [(i.address, i.mnemonic, i.op_str, i.size) for i in self.disasm(code, address)]

    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def version():
    return (5, 0)
