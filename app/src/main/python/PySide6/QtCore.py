"""Minimal QtCore surface needed by upstream mtk_gui.py."""
import os
import sys
import threading
import time as _time
from types import SimpleNamespace


_NOOP = lambda *a, **kw: None


class _EnumMeta(type):
    """Let enum namespaces be accessed on both the class and its instances."""
    def __getattr__(cls, name):
        if name.startswith("_"):
            raise AttributeError(name)
        values = cls.__dict__.get("__values__", {})
        value = values.get(name, 0)
        setattr(cls, name, value)
        return value


class _EnumNS(metaclass=_EnumMeta):
    """Any Qt enum value is accepted; unknown members resolve to 0."""
    def __init__(self, values=None):
        if values:
            self.__dict__.update(values)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = self.__dict__.get("__values__", {}).get(name, 0)
        setattr(self, name, value)
        return value


class _AlignmentNS(_EnumNS):
    __values__ = {
        "AlignLeft": 1, "AlignRight": 2, "AlignTop": 4, "AlignBottom": 8,
        "AlignCenter": 4 | 2, "AlignHCenter": 2, "AlignVCenter": 4,
        "AlignLeading": 1, "AlignTrailing": 2, "AlignJustify": 16,
    }


class _ItemFlagNS(_EnumNS):
    __values__ = {"NoItemFlags": 0, "ItemIsEnabled": 1, "ItemIsSelectable": 2,
                  "ItemIsUserCheckable": 4, "ItemIsEditable": 8}


class _ItemDataRoleNS(_EnumNS):
    __values__ = {"DisplayRole": 0, "DecorationRole": 1, "EditRole": 2,
                  "ToolTipRole": 3, "StatusTipRole": 4, "UserRole": 256,
                  "CheckStateRole": 10}


class _OrientationNS(_EnumNS):
    __values__ = {"Horizontal": 1, "Vertical": 2}


class _WindowModalityNS(_EnumNS):
    __values__ = {"NonModal": 0, "WindowModal": 1, "ApplicationModal": 2}


class _ColorSchemeNS(_EnumNS):
    __values__ = {"Light": 0, "Dark": 1, "Unknown": 2}


class _ScrollBarNS(_EnumNS):
    __values__ = {"ScrollBarAsNeeded": 0, "ScrollBarAlwaysOff": 1,
                  "ScrollBarAlwaysOn": 2}


class _AspectNS(_EnumNS):
    __values__ = {"IgnoreAspectRatio": 0, "KeepAspectRatio": 1,
                  "KeepAspectRatioByExpanding": 2}


class _TransformNS(_EnumNS):
    __values__ = {"SmoothTransformation": 3, "FastTransformation": 0}


class Qt(_EnumNS):
    TextFormat = _EnumNS({"PlainText": 0, "RichText": 1, "AutoText": 2, "MarkdownText": 3})
    ItemFlags = _ItemFlagNS()
    WindowFlags = _EnumNS()
    WindowType = _EnumNS()
    KeyboardModifiers = _EnumNS()
    MouseButton = _EnumNS()
    DropActions = _EnumNS()
    DockWidgetAreas = _EnumNS()
    ToolBarAreas = _EnumNS()
    Alignment = _AlignmentNS()
    WindowModality = _WindowModalityNS()
    Orientation = _OrientationNS()
    AlignmentFlag = _AlignmentNS()
    ItemFlag = _ItemFlagNS()
    ItemDataRole = _ItemDataRoleNS()
    ColorScheme = _ColorSchemeNS()
    ScrollBarPolicy = _ScrollBarNS()
    AspectRatioMode = _AspectNS()
    TransformationMode = _TransformNS()
    WindowType = _EnumNS()
    KeyboardModifier = _EnumNS()
    FocusPolicy = _EnumNS()
    ContextMenuPolicy = _EnumNS()
    DropAction = _EnumNS()
    DockWidgetArea = _EnumNS()
    ToolBarArea = _EnumNS()
    TimerType = _EnumNS()
    ApplicationState = _EnumNS()

    ScrollBarAlwaysOn = 2
    ScrollBarAlwaysOff = 1
    SmoothTransformation = 3
    FastTransformation = 0
    KeepAspectRatio = 1
    WA_DeleteOnClose = 1
    align = AlignmentFlag
    UserRole = 256
    dark = ColorScheme.Dark
    light = ColorScheme.Light


class QtCore(object):
    pass


class QObject:
    def __init__(self, parent=None, *args, **kwargs):
        self._parent = parent
        self._children = []
        self._object_name = ""
        self._props = {}
        if parent is not None and hasattr(parent, "_children"):
            parent._children.append(self)

    # --- object identity -------------------------------------------------
    def setObjectName(self, name):
        self._object_name = str(name)

    def objectName(self):
        return self._object_name

    def setProperty(self, name, value):
        self._props[str(name)] = value

    def property(self, name, default=None):
        return self._props.get(str(name), default)

    def children(self):
        return list(self._children)

    def parent(self):
        return self._parent

    def findChild(self, typ, name="", options=None):
        for child in self.iter_widgets():
            if name and child.objectName() != name:
                continue
            if typ is None or (isinstance(typ, tuple) and isinstance(child, typ)) \
                    or (not isinstance(typ, tuple) and isinstance(child, typ)):
                return child
        return None

    def findChildren(self, typ, name="", options=None):
        out = []
        for child in self.iter_widgets():
            if name and child.objectName() != name:
                continue
            if typ is None or (isinstance(typ, tuple) and isinstance(child, typ)) \
                    or (not isinstance(typ, tuple) and isinstance(child, typ)):
                out.append(child)
        return out

    def iter_widgets(self):
        for child in self._children:
            yield child
            if hasattr(child, "iter_widgets"):
                yield from child.iter_widgets()

    def tr(self, source, *args, **kwargs):
        return str(source)

    trStatic = tr
    deleteLater = lambda self: None

    def destroy(self):
        pass

    def __getattr__(self, name):
        # Generated setupUi() calls hundreds of harmless setters (setSizePolicy,
        # setAutoFillBackground, setMouseTracking, ...).  Record them so the
        # renderer can read them back, but never fail the upstream GUI code.
        if name.startswith("set") and len(name) > 3:
            def _setter(value=None, *a, **kw):
                self._props[name[3:4].lower() + name[4:]] = value
                return None
            return _setter
        raise AttributeError("%s has no Qt attribute %r" % (type(self).__name__, name))


class BoundSignal:
    def __init__(self, obj, name):
        self.obj = obj
        self.name = name
        self.slots = []

    def connect(self, slot, *args, **kwargs):
        if slot not in self.slots:
            self.slots.append(slot)
        return self

    def disconnect(self, slot=None):
        if slot is None:
            self.slots.clear()
        elif slot in self.slots:
            self.slots.remove(slot)

    def emit(self, *args):
        for slot in list(self.slots):
            try:
                slot(*args)
            except Exception:
                # A broken slot must not kill the device I/O thread.
                import traceback
                try:
                    if sys.stderr is not None:
                        traceback.print_exc()
                except Exception:
                    pass
        return self

    def __call__(self, *args):
        self.emit(*args)

    def count(self):
        return len(self.slots)


class Signal:
    def __init__(self, *types, **kwargs):
        self.types = types
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        cache = obj.__dict__
        key = "_signal_" + (self.name or "anonymous")
        if key not in cache:
            cache[key] = BoundSignal(obj, self.name)
        return cache[key]


class Slot:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, func):
        return func


def slot(*args, **kwargs):
    return Slot(*args, **kwargs)


class Property:
    def __init__(self, typ, fget=None, fset=None, *args, **kwargs):
        self.typ = typ
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return self.fget(obj) if self.fget else None

    def __set__(self, obj, value):
        if self.fset:
            self.fset(obj, value)


class QThread(QObject):
    started = Signal()
    finished = Signal()

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        self._thread = None
        self._running = False
        self._stop = threading.Event()
        self.function = None
        self.parameters = None

    def start(self, priority=None):
        if self._running:
            return
        self._running = True
        self._stop.clear()

        def _run():
            try:
                self.started.emit()
                self.run()
            finally:
                self._running = False
                self.finished.emit()

        self._thread = threading.Thread(target=_run, daemon=True,
                                        name="qt-thread-%s" % type(self).__name__)
        self._thread.start()

    def run(self):
        pass

    def quit(self):
        self._stop.set()

    def isRunning(self):
        return self._running and self._thread is not None and self._thread.is_alive()

    def wait(self, msecs=-1):
        if self._thread is None:
            return True
        self._thread.join(None if msecs < 0 else msecs / 1000.0)
        return not self._thread.is_alive()

    def terminate(self):
        pass

    def exec(self):
        while not self._stop.is_set():
            _time.sleep(0.01)
        return 0

    exec_ = exec

    @staticmethod
    def msleep(msecs):
        _time.sleep(msecs / 1000.0)

    @staticmethod
    def sleep(secs):
        _time.sleep(secs)

    def msleep自(self, msecs):  # pragma: no cover - typos in downstream code
        self.msleep(msecs)


class QTimer(QObject):
    timeout = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._interval = 0
        self._active = False

    def setInterval(self, ms):
        self._interval = ms

    def interval(self):
        return self._interval

    def start(self, ms=None):
        if ms is not None:
            self._interval = ms
        self._active = True

    def stop(self):
        self._active = False

    def isActive(self):
        return self._active

    @staticmethod
    def singleShot(msecs, receiver, member=None):
        if callable(member) or (member is None and callable(receiver)):
            fn = member or receiver
            threading.Timer(msecs / 1000.0, fn).start()


class QSize:
    def __init__(self, w=0, h=0):
        self._w, self._h = w, h

    def width(self): return self._w
    def height(self): return self._h
    def isValid(self): return self._w >= 0 and self._h >= 0
    def __repr__(self): return "QSize(%r, %r)" % (self._w, self._h)


class QPoint:
    def __init__(self, x=0, y=0):
        self._x, self._y = x, y

    def x(self): return self._x
    def y(self): return self._y


class QRect:
    def __init__(self, x=0, y=0, w=0, h=0):
        self._x, self._y, self._w, self._h = x, y, w, h

    def x(self): return self._x
    def y(self): return self._y
    def width(self): return self._w
    def height(self): return self._h
    def size(self): return QSize(self._w, self._h)


class QDate:
    def __init__(self, y=1970, m=1, d=1): self._y, self._m, self._d = y, m, d
    @staticmethod
    def currentDate(): return QDate()
    def toString(self, fmt=None): return "%04d-%02d-%02d" % (self._y, self._m, self._d)


class QTime:
    def __init__(self, h=0, m=0, s=0): self._h, self._m, self._s = h, m, s
    @staticmethod
    def currentTime(): return QTime()
    def toString(self, fmt=None): return "%02d:%02d:%02d" % (self._h, self._m, self._s)


class QDateTime:
    def __init__(self, *args): self._date = QDate(); self._time = QTime()
    @staticmethod
    def currentDateTime(): return QDateTime()
    def date(self): return self._date
    def time(self): return self._time
    def toString(self, fmt=None): return self._date.toString() + " " + self._time.toString()


class QUrl:
    def __init__(self, url=""):
        self._url = str(url)

    def toString(self): return self._url
    def url(self): return self._url
    def isValid(self): return bool(self._url)
    @staticmethod
    def fromUserInput(s): return QUrl(s)


class QLocale:
    def __init__(self, name="id_ID"):
        self._name = name

    @staticmethod
    def system(): return QLocale()

    def name(self): return self._name
    def bcp47Name(self): return self._name.split("_")[0]


class QTranslator(QObject):
    def load(self, *args, **kwargs): return False
    def isEmpty(self): return True


class QLibraryInfo:
    TranslationsPath = "translations"
    LibraryPath = "libs"
    @staticmethod
    def location(which): return ""
    @staticmethod
    def path(which): return ""


class QCoreApplication(QObject):
    _instance = None

    def __init__(self, argv=None):
        super().__init__()
        QCoreApplication._instance = self
        self._argv = list(argv or [])

    @staticmethod
    def translate(context, source, disambiguation=None, n=-1):
        return source

    tr = translate

    @staticmethod
    def applicationDirPath():
        return os.environ.get("HOME", ".")

    @staticmethod
    def applicationFilePath():
        return os.path.join(os.environ.get("HOME", "."), "mtkclient")

    @staticmethod
    def arguments():
        return QCoreApplication._instance._argv if QCoreApplication._instance else []

    def exec(self):
        return 0

    exec_ = exec

    @staticmethod
    def quit():
        pass

    @staticmethod
    def setOrganizationName(name): pass
    @staticmethod
    def setApplicationName(name): pass
    @staticmethod
    def setApplicationVersion(v): pass


class QEventLoop(QObject):
    def exec(self): return 0
    def quit(self): pass


class QVariantAnimation(QObject):
    valueChanged = Signal(object)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start = None
        self._end = None
        self._value = None

    def setStartValue(self, v): self._start = v
    def setEndValue(self, v): self._end = v
    def setDuration(self, ms): pass
    def value(self): return self._value
    def start(self):
        self._value = self._end
        self.valueChanged.emit(self._value)
        self.finished.emit()


class QMetaObject:
    @staticmethod
    def connectSlotsByName(obj): pass

    @staticmethod
    def invokeMethod(obj, member, *args):
        fn = getattr(obj, member, None)
        if callable(fn):
            return fn(*args)
        return False


QEvent = SimpleNamespace(Type=SimpleNamespace())
