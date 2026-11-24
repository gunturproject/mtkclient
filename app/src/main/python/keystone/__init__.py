"""Import-compatible Keystone shim for Android.

The native Keystone engine has no Android wheel.  All constants and the Ks API
are preserved so upstream modules import unchanged.  When an assembly operation
is actually requested, the shim tries (in order):

  1. a Java-side assembler exposed through android_bridge.asm(), and
  2. `llvm-mc` / `clang` available on a rooted device.

If none is present it raises KsError with an explanatory message instead of
crashing the application at import time.
"""
import shutil
import subprocess

KS_ARCH_ARM = 1
KS_ARCH_ARM64 = 2
KS_ARCH_MIPS = 3
KS_ARCH_X86 = 4
KS_ARCH_PPC = 5
KS_ARCH_SPARC = 6
KS_ARCH_SYSTEMZ = 7
KS_ARCH_HEXAGON = 8

KS_MODE_LITTLE_ENDIAN = 0
KS_MODE_BIG_ENDIAN = 1 << 30
KS_MODE_ARM = 0
KS_MODE_THUMB = 1
KS_MODE_V8 = 2
KS_MODE_MCLASS = 4
KS_MODE_MICRO = 8
KS_MODE_MIPS3 = 16
KS_MODE_MIPS32R6 = 32
KS_MODE_MIPS32 = 64
KS_MODE_MIPS64 = 128
KS_MODE_16 = 256
KS_MODE_32 = 512
KS_MODE_64 = 1024
KS_MODE_PPC32 = 512
KS_MODE_PPC64 = 1024
KS_MODE_QPX = 2048
KS_MODE_SPARC32 = 512
KS_MODE_SPARC64 = 1024
KS_MODE_V9 = 4096

KS_ERR_ARCH = 1
KS_ERR_MODE = 2


class KsError(Exception):
    pass


_ARCH_TRIPLE = {
    KS_ARCH_ARM: "arm",
    KS_ARCH_ARM64: "aarch64",
    KS_ARCH_MIPS: "mips",
    KS_ARCH_X86: "x86",
    KS_ARCH_PPC: "powerpc",
    KS_ARCH_SPARC: "sparc",
    KS_ARCH_SYSTEMZ: "systemz",
    KS_ARCH_HEXAGON: "hexagon",
}


class Ks:
    def __init__(self, arch, mode):
        self.arch = arch
        self.mode = mode
        self.syntax = 0

    def asm(self, code, address=0):
        if isinstance(code, str):
            code_lines = code.replace(";", "\n").splitlines()
        else:
            code_lines = [code.decode("utf-8", "replace")]

        try:
            from android_bridge import bridge
            encoded = bridge.asm(self.arch, self.mode, code_lines)
            if encoded:
                return list(encoded), len(code_lines)
        except Exception:
            pass

        triple = _ARCH_TRIPLE.get(self.arch)
        tool = shutil.which("llvm-mc") or shutil.which("clang")
        if tool and triple:
            try:
                out = subprocess.run(
                    [tool, "-triple=%s-none-none-eabi" % triple, "-assemble", "-show-encoding"],
                    input=("\n".join(code_lines) + "\n").encode(),
                    capture_output=True, timeout=20)
                data = bytearray()
                for line in out.stdout.decode("utf-8", "replace").splitlines():
                    if "encoding:" not in line:
                        continue
                    for token in line.split("encoding:")[-1].replace("[", " ").replace("]", " ").split(","):
                        token = token.strip().replace("0x", "")
                        if token:
                            data.append(int(token.split()[0], 16))
                if data:
                    return list(data), len(code_lines)
            except Exception:
                pass
        raise KsError("No assembler backend on Android for architecture %s. "
                      "Install an assembler provider or use a desktop build for this tool." % triple)

    def option(self, *a): pass
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def version():
    return (0, 0)
