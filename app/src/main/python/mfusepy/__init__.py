"""FUSE compatibility shim: FUSE mounts are not available on stock Android."""
class FUSE:
    def __init__(self, *a, **kw):
        raise RuntimeError("FUSE mounts are not available on Android. "
                           "Use the mtkclient file-browser actions instead.")


class Operations:
    pass


class LoggingMixIn:
    pass
