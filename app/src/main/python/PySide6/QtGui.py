"""Minimal QtGui surface needed by upstream mtkclient GUI."""
import re
from .QtCore import QObject, QSize, QPoint, QRect, QUrl, Qt, _EnumNS, _NOOP


class _StandardPixmapNS(_EnumNS):
    __values__ = {}


class QIcon:
    def __init__(self, *args, **kwargs):
        self._source = args[0] if args else None

    def isNull(self): return self._source is None
    def pixmap(self, *a, **kw): return QPixmap()
    def addPixmap(self, *a, **kw): pass
    def addFile(self, *a, **kw): pass


class QPixmap:
    def __init__(self, *args, **kwargs):
        self._w = 0
        self._h = 0

    @staticmethod
    def fromImage(img): return QPixmap()
    def load(self, *a, **kw): return False
    def isNull(self): return True
    def width(self): return self._w
    def height(self): return self._h
    def size(self): return QSize(self._w, self._h)
    def scaled(self, *a, **kw): return QPixmap()
    def setDevicePixelRatio(self, ratio): self._dpr = ratio
    def devicePixelRatio(self): return getattr(self, "_dpr", 1)
    def save(self, *a, **kw): return False


class QImage:
    def __init__(self, *args, **kwargs): pass


class QColor:
    def __init__(self, value=None, *args):
        if value is None:
            self._value = "#000000"
        elif isinstance(value, QColor):
            self._value = value._value
        elif isinstance(value, str):
            self._value = value
        elif isinstance(value, (tuple, list)):
            self._value = "#%02x%02x%02x" % tuple(value[:3])
        else:
            self._value = "#000000"

    def name(self): return self._value

    @staticmethod
    def fromString(s):
        c = QColor()
        c._value = s if re.match(r"^#[0-9a-fA-F]{6}$", s) else "#000000"
        return c


class QFont:
    def __init__(self, family="sans-serif", pointSize=10, weight=400, italic=False):
        self.family = family
        self.pointSize = pointSize
        self.weight = weight
        self.italic = italic
        self.bold = weight >= 600

    def setFamily(self, f): self.family = f
    def setPointSize(self, s): self.pointSize = s
    def setPixelSize(self, s): self.pointSize = s
    def setBold(self, b): self.bold = bool(b)
    def setItalic(self, b): self.italic = bool(b)
    def setWeight(self, w): self.weight = w
    def family(self): return self.family
    def pointSize(self): return self.pointSize
    def toString(self): return "%s,%s" % (self.family, self.pointSize)

    class Weight(_EnumNS):
        __values__ = {"Normal": 400, "Bold": 700}


class QCursor:
    def __init__(self, *a, **kw): pass

    class Shape(_EnumNS):
        __values__ = {"ArrowCursor": 0, "BusyCursor": 1, "WaitCursor": 2,
                      "PointingHandCursor": 3}


class QPalette:
    def __init__(self, *a, **kw):
        self._colors = {}
        self.ColorRole = _EnumNS()

    def setColor(self, role, color): self._colors[str(role)] = color
    def color(self, role): return self._colors.get(str(role), QColor())


class QKeySequence:
    def __init__(self, *a, **kw): pass

    StandardKey = _EnumNS()


class QDesktopServices:
    @staticmethod
    def openUrl(url):
        try:
            from android_bridge import bridge
            bridge.open_url(url.toString() if hasattr(url, "toString") else str(url))
            return True
        except Exception:
            return False


class QDrag(QObject):
    pass


class QMimeData(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""

    def setText(self, text): self._text = text
    def text(self): return self._text
    def hasText(self): return bool(self._text)
    def hasUrls(self): return False


class QBrush:
    def __init__(self, *a, **kw): pass


class QPen:
    def __init__(self, *a, **kw): pass


class QPainter:
    def __init__(self, *a, **kw): pass


class QPolygon:
    def __init__(self, *a, **kw): pass
    __values__ = {}


class QRegion:
    def __init__(self, *a, **kw): pass


class QTransform:
    def __init__(self, *a, **kw): pass
    def translate(self, *a, **kw): return self
    def scale(self, *a, **kw): return self
    def rotate(self, *a, **kw): return self


class QGradient:
    class Preset(_EnumNS):
        __values__ = {}
    class Spread(_EnumNS):
        __values__ = {}
    class CoordinateMode(_EnumNS):
        __values__ = {}
    class Type(_EnumNS):
        __values__ = {}
    def __init__(self, *a, **kw): pass
    def setColorAt(self, *a, **kw): pass
    def setSpread(self, *a, **kw): pass


class QLinearGradient(QGradient):
    def __init__(self, *a, **kw): super().__init__(*a, **kw)


class QRadialGradient(QGradient):
    def __init__(self, *a, **kw): super().__init__(*a, **kw)


class QConicalGradient(QGradient):
    def __init__(self, *a, **kw): super().__init__(*a, **kw)


class QFontDatabase:
    @staticmethod
    def addApplicationFont(path): return -1
    @staticmethod
    def applicationFontFamilies(id): return []
    class WritingSystem(_EnumNS):
        __values__ = {}


class QTextOption:
    def __init__(self, *a, **kw): pass
    class WrapMode(_EnumNS):
        __values__ = {"NoWrap": 0, "WordWrap": 1, "ManualWrap": 2, "WrapAnywhere": 3}



class QSyntaxHighlighter(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)


class QTextCharFormat:
    def __init__(self, *a, **kw): pass


class QFontMetrics:
    def __init__(self, font=None):
        self._font = font or QFont()

    def height(self): return int((self._font.pointSize or 10) * 1.4)
    def horizontalAdvance(self, text): return len(str(text)) * max(6, self._font.pointSize)
    def width(self, text): return self.horizontalAdvance(text)
    def elidedText(self, text, mode, width):
        text = str(text)
        return text if len(text) * 8 <= width else text[:max(0, width // 8 - 1)] + "…"


class QGuiApplication(QObject):
    _instance = None

    def __init__(self, argv=None):
        super().__init__()
        QGuiApplication._instance = self
        self._argv = list(argv or [])
        self._clipboard = None

    @staticmethod
    def primaryScreen():
        return None

    @staticmethod
    def clipboard():
        inst = QGuiApplication._instance
        if inst is None:
            return None
        if inst._clipboard is None:
            from .QtWidgets import QClipboard
            inst._clipboard = QClipboard()
        return inst._clipboard

    @staticmethod
    def styleHints():
        return _NOOP

    @staticmethod
    def setOverrideCursor(cursor): pass

    @staticmethod
    def restoreOverrideCursor(): pass

    @staticmethod
    def applicationDirPath(): return "."

    @staticmethod
    def arguments(): return []

    @staticmethod
    def quit(): pass


# Qt enums re-exported through QtGui in generated code.
Qt.GlobalColor = _EnumNS()
for _c in ("black", "white", "red", "green", "blue", "yellow", "gray", "darkGray", "lightGray"):
    setattr(Qt.GlobalColor, _c, 0)


class QAction(QObject):
    triggered = __import__("PySide6.QtCore", fromlist=["Signal"]).Signal(bool)
    toggled = __import__("PySide6.QtCore", fromlist=["Signal"]).Signal(bool)

    def __init__(self, *args, **kwargs):
        parent = kwargs.get("parent") or (args[0] if args and isinstance(args[0], QObject) else None)
        super().__init__(parent)
        self._text = ""
        self._checkable = False
        self._checked = False
        self._enabled = True
        self._icon = None
        self._shortcut = None
        self._tool_tip = ""
        self._data = None
        if kwargs.get("checkable"):
            self._checkable = True
        if kwargs.get("checked"):
            self._checked = True
        for arg in args:
            if isinstance(arg, str) and not self._text:
                self._text = arg

    def setText(self, t): self._text = str(t)
    def text(self): return self._text
    def setIcon(self, i): self._icon = i
    def icon(self): return self._icon
    def setCheckable(self, b): self._checkable = bool(b)
    def isCheckable(self): return self._checkable
    def setChecked(self, b):
        old = self._checked
        self._checked = bool(b)
        if old != self._checked:
            self.toggled.emit(self._checked)
    def isChecked(self): return self._checked
    def setEnabled(self, b): self._enabled = bool(b)
    def isEnabled(self): return self._enabled
    def setShortcut(self, s): self._shortcut = s
    def shortcut(self): return self._shortcut
    def setToolTip(self, t): self._tool_tip = str(t)
    def toolTip(self): return self._tool_tip
    def setData(self, d): self._data = d
    def data(self): return self._data
    def setStatusTip(self, t): self._tool_tip = str(t)
    def setVisible(self, b): pass
    def trigger(self): self.triggered.emit(False)
