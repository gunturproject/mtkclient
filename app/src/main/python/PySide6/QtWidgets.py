"""Android-compatible subset of PySide6.QtWidgets used by mtkclient GUI.

Widgets remain real Python objects with real Qt-style signals.  The Android
front-end walks this object tree and renders it as a mobile HTML UI.  User
actions call back into the same signals, so upstream mtk_gui.py code runs
unchanged.
"""
import os
from .QtCore import (
    QObject, Signal, Slot, Qt, QSize, QPoint, QRect, QUrl, QEventLoop,
)


class _EnumMeta(type):
    def __getattr__(cls, name):
        if name.startswith("_"):
            raise AttributeError(name)
        values = cls.__dict__.get("__values__", {})
        value = values.get(name, 0)
        setattr(cls, name, value)
        return value


class _EnumNS(metaclass=_EnumMeta):
    def __init__(self, values=None):
        self.__values__ = values or {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = self.__values__.get(name, 0)
        setattr(self, name, value)
        return value


class QSizePolicy:
    class Policy(_EnumNS):
        __values__ = {
            "Fixed": 0, "Minimum": 1, "Maximum": 2, "Preferred": 3,
            "MinimumExpanding": 4, "Expanding": 5, "Ignored": 6,
        }

    Fixed = Policy.Fixed
    Minimum = Policy.Minimum
    Maximum = Policy.Maximum
    Preferred = Policy.Preferred
    MinimumExpanding = Policy.MinimumExpanding
    Expanding = Policy.Expanding
    Ignored = Policy.Ignored

    class ControlType(_EnumNS):
        __values__ = {"DefaultType": 0, "ButtonBox": 1, "CheckBox": 2,
                      "ComboBox": 3, "Frame": 4, "GroupBox": 5, "Label": 6,
                      "LineEdit": 7, "PushButton": 8, "RadioButton": 9,
                      "Slider": 10, "SpinBox": 11, "TabWidget": 12, "ToolButton": 13}

    def __init__(self, horizontal=None, vertical=None):
        self.horizontal = horizontal if horizontal is not None else self.Preferred
        self.vertical = vertical if vertical is not None else self.Preferred
        self.hStretch = 0
        self.vStretch = 0
        self.heightForWidth = False

    def setHorizontalStretch(self, n): self.hStretch = n
    def setVerticalStretch(self, n): self.vStretch = n
    def horizontalStretch(self): return self.hStretch
    def verticalStretch(self): return self.vStretch
    def setHeightForWidth(self, b): self.heightForWidth = bool(b)
    def hasHeightForWidth(self): return self.heightForWidth
    def setHorizontalPolicy(self, p): self.horizontal = p
    def setVerticalPolicy(self, p): self.vertical = p


class QSpacerItem:
    def __init__(self, w=0, h=0, hPolicy=None, vPolicy=None):
        self._w, self._h = w, h
        self._hp, self._vp = hPolicy, vPolicy

    def sizeHint(self): return QSize(self._w, self._h)
    def changeSize(self, w, h, *a, **kw): self._w, self._h = w, h


class QLayoutItem:
    def __init__(self, widget=None, layout=None, spacer=None, stretch=0):
        self.widget = widget
        self.layout = layout
        self.spacer = spacer
        self.stretch = stretch

    def sizeHint(self):
        if self.widget is not None:
            return self.widget.sizeHint()
        if self.spacer is not None:
            return self.spacer.sizeHint()
        return QSize()


class QLayout(QObject):
    SizeConstraint = _EnumNS({
        "SetDefaultConstraint": 0, "SetNoConstraint": 1, "SetMinimumSize": 2,
        "SetFixedSize": 3, "SetMaximumSize": 4, "SetMinAndMaxSize": 5,
    })

    def setSizeConstraint(self, c): self._props["sizeConstraint"] = c
    def sizeConstraint(self): return self._props.get("sizeConstraint", 0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._margin = 0
        self._spacing = -1
        if parent is not None and hasattr(parent, "setLayout"):
            parent.setLayout(self)

    def addWidget(self, widget, *args, **kwargs):
        stretch = args[0] if args and isinstance(args[0], int) else 0
        self._items.append(QLayoutItem(widget=widget, stretch=stretch))
        return None

    def addLayout(self, layout, *args, **kwargs):
        stretch = args[0] if args and isinstance(args[0], int) else 0
        self._items.append(QLayoutItem(layout=layout, stretch=stretch))
        return None

    def addItem(self, item):
        self._items.append(item if isinstance(item, QLayoutItem) else QLayoutItem(spacer=item))

    def addStretch(self, stretch=0):
        self._items.append(QLayoutItem(spacer=QSpacerItem(), stretch=stretch))

    def addSpacing(self, size):
        self._items.append(QLayoutItem(spacer=QSpacerItem(size, size)))

    def insertWidget(self, index, widget, *args, **kwargs):
        self._items.insert(index, QLayoutItem(widget=widget))

    def insertLayout(self, index, layout, *args, **kwargs):
        self._items.insert(index, QLayoutItem(layout=layout))

    def setContentsMargins(self, l, t, r, b): self._margin = (l, t, r, b)
    def getContentsMargins(self): return self._margin if isinstance(self._margin, tuple) else (0, 0, 0, 0)
    def contentsMargins(self): return self.getContentsMargins()
    def setSpacing(self, s): self._spacing = s
    def spacing(self): return self._spacing
    def count(self): return len(self._items)
    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None
    def indexOf(self, widget):
        for i, item in enumerate(self._items):
            if item.widget is widget:
                return i
        return -1
    def removeWidget(self, widget):
        i = self.indexOf(widget)
        if i >= 0:
            self._items.pop(i)
    def activate(self): pass
    def invalidate(self): pass
    def sizeHint(self): return QSize()


class QBoxLayout(QLayout):
    Direction = _EnumNS({"LeftToRight": 0, "RightToLeft": 1, "TopToBottom": 2, "BottomToTop": 3})

    def __init__(self, direction=None, parent=None):
        super().__init__(parent)
        self.direction = direction or self.Direction.TopToBottom


class QVBoxLayout(QBoxLayout):
    def __init__(self, parent=None):
        super().__init__(self.Direction.TopToBottom, parent)


class QHBoxLayout(QBoxLayout):
    def __init__(self, parent=None):
        super().__init__(self.Direction.LeftToRight, parent)


class QGridLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = []

    def addWidget(self, widget, row=0, col=0, rowSpan=1, colSpan=1, *a, **kw):
        self._grid.append((widget, row, col, rowSpan, colSpan))
        super().addWidget(widget)

    def addLayout(self, layout, row=0, col=0, rowSpan=1, colSpan=1, *a, **kw):
        self._grid.append((layout, row, col, rowSpan, colSpan))
        super().addLayout(layout)

    def setColumnStretch(self, col, stretch): self._props["columnStretch-%s" % col] = stretch
    def setRowStretch(self, row, stretch): self._props["rowStretch-%s" % row] = stretch
    def setColumnMinimumWidth(self, col, w): self._props["columnMin-%s" % col] = w
    def setRowMinimumHeight(self, row, h): self._props["rowMin-%s" % row] = h


class QFormLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def addRow(self, label, field=None):
        if field is None:
            self._rows.append((None, label))
            self._items.append(QLayoutItem(widget=label))
        else:
            self._rows.append((label, field))
            self._items.append(QLayoutItem(widget=field))
        return len(self._rows) - 1

    def setLabelAlignment(self, *a, **kw): pass


class QWidget(QObject):
    # Generic signals shared by all widget types.  Only the ones a widget
    # actually uses will ever be emitted by the mobile renderer.
    clicked = Signal(bool)
    toggled = Signal(bool)
    stateChanged = Signal(int)
    textChanged = Signal(str)
    textEdited = Signal(str)
    currentIndexChanged = Signal(int)
    currentTextChanged = Signal(str)
    valueChanged = Signal(object)
    editingFinished = Signal()
    returnPressed = Signal()
    itemSelectionChanged = Signal()
    itemClicked = Signal(object)
    itemDoubleClicked = Signal(object)
    itemChanged = Signal(object)
    triggered = Signal(bool)
    accepted = Signal()
    rejected = Signal()
    customContextMenuRequested = Signal(object)
    destroyed = Signal()
    pressed = Signal()
    released = Signal()

    class SelectionMode(_EnumNS):
        __values__ = {"NoSelection": 0, "SingleSelection": 1, "MultiSelection": 2,
                      "ExtendedSelection": 3, "ContiguousSelection": 4}

    class ContextMenuPolicy(_EnumNS):
        __values__ = {"NoContextMenu": 0, "DefaultContextMenu": 1,
                      "ActionsContextMenu": 2, "CustomContextMenu": 3}

    class FocusPolicy(_EnumNS):
        __values__ = {"NoFocus": 0, "TabFocus": 1, "ClickFocus": 2, "StrongFocus": 3, "WheelFocus": 4}

    def __init__(self, parent=None, *args, **kwargs):
        if parent is not None and not isinstance(parent, QObject):
            args = (parent,) + args
            parent = kwargs.get("parent")
            if parent is not None and not isinstance(parent, QObject):
                parent = None
        super().__init__(parent)
        self._layout = None
        self._enabled = True
        self._visible = True
        self._geometry = QRect()
        self._size_hint = QSize()
        self._minimum_size = QSize()
        self._maximum_size = QSize(16777215, 16777215)
        self._size_policy = QSizePolicy()
        self._stylesheet = ""
        self._tool_tip = ""
        self._status_tip = ""
        self._window_title = ""
        self._cursor = None
        self._accept_drops = False
        self._context_menu_policy = self.ContextMenuPolicy.DefaultContextMenu
        self._focus_policy = self.FocusPolicy.StrongFocus
        self._checkable = False
        self._checked = False
        self._text = ""
        self._value = None
        self._minimum = 0
        self._maximum = 99
        self._single_step = 1
        self._read_only = False
        self._placeholder = ""
        self._echo_mode = 0
        self._items = []
        self._current_index = -1
        self._current_row = -1
        self._selected_rows = []
        self._orientation = Qt.Orientation.Vertical
        self._tabs = []
        self._columns = 0
        self._rows_count = 0
        self._headers = []
        self._cell_widgets = {}
        self._model = None
        self._selection_model = _SelectionModel(self)
        self._is_window = False
        for arg in args:
            if isinstance(arg, str):
                self._text = arg
                break

    # --- geometry / state --------------------------------------------------
    def setLayout(self, layout):
        self._layout = layout
        if layout is not None and layout.parent() is None:
            layout._parent = self

    def layout(self): return self._layout
    def sizePolicy(self): return self._size_policy
    def setSizePolicy(self, *a, **kw):
        if len(a) == 2 and isinstance(a[0], int):
            self._size_policy = QSizePolicy(a[0], a[1])
        elif a and isinstance(a[0], QSizePolicy):
            self._size_policy = a[0]
    def setMinimumSize(self, *a):
        if len(a) == 2: self._minimum_size = QSize(a[0], a[1])
        elif a and isinstance(a[0], QSize): self._minimum_size = a[0]
    def minimumSize(self): return self._minimum_size
    def setMaximumSize(self, *a):
        if len(a) == 2: self._maximum_size = QSize(a[0], a[1])
        elif a and isinstance(a[0], QSize): self._maximum_size = a[0]
    def maximumSize(self): return self._maximum_size
    def resize(self, w, h=None):
        if isinstance(w, QSize): self._geometry = QRect(0, 0, w.width(), w.height())
        else: self._geometry = QRect(0, 0, w, h or 0)
    def setGeometry(self, *a):
        if len(a) == 1 and isinstance(a[0], QRect): self._geometry = a[0]
        elif len(a) == 4: self._geometry = QRect(*a)
    def geometry(self): return self._geometry
    def size(self): return self._geometry.size()
    def width(self): return self._geometry.width()
    def height(self): return self._geometry.height()
    def move(self, x, y): self._geometry = QRect(x, y, self._geometry.width(), self._geometry.height())
    def setFixedSize(self, *a): self.setMinimumSize(*a); self.setMaximumSize(*a)
    def setFixedWidth(self, w): self._minimum_size = QSize(w, self._minimum_size.height()); self._maximum_size = QSize(w, self._maximum_size.height())
    def setFixedHeight(self, h): self._minimum_size = QSize(self._minimum_size.width(), h); self._maximum_size = QSize(self._maximum_size.width(), h)
    def sizeHint(self): return self._size_hint if self._size_hint.width() else QSize(120, 32)
    def setSizeHint(self, size): self._size_hint = size
    def adjustSize(self): pass
    def setEnabled(self, b):
        self._enabled = bool(b)
        self.setEnabled.__doc__ = None
    def isEnabled(self): return self._enabled
    def setDisabled(self, b): self.setEnabled(not b)
    def setVisible(self, b): self._visible = bool(b)
    def isVisible(self): return self._visible
    def show(self): self._visible = True
    def hide(self): self._visible = False
    def raise_(self): pass
    def setHidden(self, b): self.setVisible(not b)
    def close(self): self._visible = False
    def setStyleSheet(self, s): self._stylesheet = str(s)
    def styleSheet(self): return self._stylesheet
    def setToolTip(self, t): self._tool_tip = str(t)
    def toolTip(self): return self._tool_tip
    def setStatusTip(self, t): self._status_tip = str(t)
    def statusTip(self): return self._status_tip
    def setWindowTitle(self, t): self._window_title = str(t)
    def windowTitle(self): return self._window_title
    def setWindowIcon(self, i): self._props["windowIcon"] = i
    def setWindowModality(self, m): self._props["windowModality"] = m
    def setAttribute(self, *a, **kw): pass
    def setAcceptDrops(self, b): self._accept_drops = bool(b)
    def acceptDrops(self): return self._accept_drops
    def setContextMenuPolicy(self, p): self._context_menu_policy = p
    def contextMenuPolicy(self): return self._context_menu_policy
    def setFocusPolicy(self, p): self._focus_policy = p
    def setCursor(self, c): self._cursor = c
    def unsetCursor(self): self._cursor = None
    def setFocus(self): pass
    def hasFocus(self): return False
    def grabKeyboard(self): pass
    def releaseKeyboard(self): pass
    def update(self): pass
    def repaint(self): pass
    def setUpdatesEnabled(self, b): pass
    def setMouseTracking(self, b): pass
    def setAutoFillBackground(self, b): pass
    def setContentsMargins(self, l, t, r, b):
        if self._layout: self._layout.setContentsMargins(l, t, r, b)
    def mapToGlobal(self, p): return p
    def mapFromGlobal(self, p): return p
    def pos(self): return QPoint(self._geometry.x(), self._geometry.y())
    def screen(self): return None
    def logicalDpiX(self): return 160
    def logicalDpiY(self): return 160

    # --- generic widget value API -----------------------------------------
    def setText(self, t):
        old = self._text
        self._text = str(t)
        if old != self._text:
            self.textChanged.emit(self._text)

    def text(self): return self._text
    def setPlainText(self, t): self.setText(t)
    def toPlainText(self): return self._text
    def setHtml(self, t): self.setText(t)
    def toHtml(self): return self._text
    def setPlaceholderText(self, t): self._placeholder = str(t)
    def placeholderText(self): return self._placeholder
    def setEchoMode(self, m): self._echo_mode = m
    def echoMode(self): return self._echo_mode
    def setReadOnly(self, b): self._read_only = bool(b)
    def isReadOnly(self): return self._read_only
    def setEnabled(self, b): self._enabled = bool(b)
    def clear(self):
        old = self._text
        self._text = ""
        self._items = []
        self._current_index = -1
        self._current_row = -1
        if old: self.textChanged.emit("")
    def selectAll(self): pass
    def setSelection(self, *a): pass
    def append(self, t):
        self._text = (self._text + "\n" + str(t)).strip("\n")
        self.textChanged.emit(self._text)
    def appendPlainText(self, t): self.append(t)
    def insertPlainText(self, t): self.append(t)
    def ensureCursorVisible(self): pass
    def moveCursor(self, *a): pass
    def setWordWrap(self, b): pass
    def setLineWrapMode(self, m): self._props["lineWrapMode"] = m

    # --- button / check state ---------------------------------------------
    def setCheckable(self, b): self._checkable = bool(b)
    def isCheckable(self): return self._checkable
    def setChecked(self, b):
        old = self._checked
        self._checked = bool(b)
        if old != self._checked:
            self.toggled.emit(self._checked)
    def isChecked(self): return self._checked
    def checkState(self): return 2 if self._checked else 0
    def setCheckState(self, state): self.setChecked(state != 0)
    def setDown(self, b): self._props["down"] = b
    def setDefault(self, b): self._props["default"] = b
    def setFlat(self, b): self._props["flat"] = b
    def click(self):
        if self._checkable:
            self.setChecked(not self._checked)
        self.clicked.emit(False)
    def animateClick(self): self.click()
    def toggle(self): self.setChecked(not self._checked)

    # --- ranges ------------------------------------------------------------
    def setMinimum(self, v): self._minimum = v
    def minimum(self): return self._minimum
    def setMaximum(self, v): self._maximum = v
    def maximum(self): return self._maximum
    def setRange(self, lo, hi): self._minimum, self._maximum = lo, hi
    def setValue(self, v):
        try: v = int(v)
        except Exception: v = 0
        v = max(self._minimum, min(self._maximum, v))
        old = self._value
        self._value = v
        if old != v: self.valueChanged.emit(v)
    def value(self): return self._value if self._value is not None else self._minimum
    def setSingleStep(self, s): self._single_step = s
    def singleStep(self): return self._single_step
    def setPageStep(self, s): self._props["pageStep"] = s
    def setOrientation(self, o): self._orientation = o
    def orientation(self): return self._orientation
    def setInvertedAppearance(self, b): pass
    def setTextVisible(self, b): pass
    def setFormat(self, f): self._props["format"] = f
    def reset(self): self.setValue(self._minimum)

    # --- item views --------------------------------------------------------
    def addItem(self, item):
        if isinstance(item, str):
            item = QListWidgetItem(item)
        self._items.append(item)
        return item
    def addItems(self, items):
        for it in items: self.addItem(it)
    def insertItem(self, row, item):
        self._items.insert(row, item if not isinstance(item, str) else QListWidgetItem(item))
    def takeItem(self, row):
        return self._items.pop(row) if 0 <= row < len(self._items) else None
    def item(self, row):
        return self._items[row] if 0 <= row < len(self._items) else None
    def count(self): return len(self._items)
    def currentItem(self):
        return self._items[self._current_row] if 0 <= self._current_row < len(self._items) else None
    def setCurrentItem(self, item):
        if item in self._items:
            self._current_row = self._items.index(item)
            self.itemSelectionChanged.emit()
    def currentRow(self): return self._current_row
    def setCurrentRow(self, row):
        self._current_row = row
        self.itemSelectionChanged.emit()
    def selectedItems(self):
        return [self._items[r] for r in self._selected_rows if 0 <= r < len(self._items)]
    def setSelectionMode(self, m): self._props["selectionMode"] = m
    def selectionMode(self): return self._props.get("selectionMode", self.SelectionMode.SingleSelection)
    def setSortingEnabled(self, b): pass
    def sortItems(self, *a): pass
    def clearSelection(self): self._selected_rows = []
    def selectionModel(self): return self._selection_model
    def setMouseTracking(self, b): pass
    def setAlternatingRowColors(self, b): pass

    # --- table -------------------------------------------------------------
    def setColumnCount(self, n): self._columns = n
    def columnCount(self): return self._columns
    def setRowCount(self, n): self._rows_count = n
    def rowCount(self): return self._rows_count
    def setHorizontalHeaderLabels(self, labels): self._headers = list(labels)
    def setVerticalHeaderLabels(self, labels): self._props["vHeaders"] = list(labels)
    def horizontalHeader(self): return QHeaderView(self)
    def verticalHeader(self): return QHeaderView(self, Qt.Orientation.Vertical)
    def horizontalHeaderItem(self, col):
        key = ("h", col)
        if key not in self._cell_widgets:
            self._cell_widgets[key] = QTableWidgetItem("")
        return self._cell_widgets[key]
    def verticalHeaderItem(self, row):
        key = ("v", row)
        if key not in self._cell_widgets:
            self._cell_widgets[key] = QTableWidgetItem("")
        return self._cell_widgets[key]
    def setHorizontalHeaderItem(self, col, item): self._cell_widgets[("h", col)] = item
    def setVerticalHeaderItem(self, row, item): self._cell_widgets[("v", row)] = item
    def setItem(self, row, col, item):
        self._cell_widgets[(row, col)] = item
    def item(self, row, col=None):
        if col is None:
            return self._items[row] if 0 <= row < len(self._items) else None
        return self._cell_widgets.get((row, col))
    def setCellWidget(self, row, col, widget): self._cell_widgets[(row, col)] = widget
    def cellWidget(self, row, col): return self._cell_widgets.get((row, col))
    def setColumnWidth(self, col, w): self._props["colWidth-%s" % col] = w
    def setRowHeight(self, row, h): self._props["rowHeight-%s" % row] = h
    def resizeColumnsToContents(self): pass
    def resizeRowsToContents(self): pass
    def setEditTriggers(self, t): pass
    def setSelectionBehavior(self, b): pass
    def setShowGrid(self, b): pass
    def setIconSize(self, s): pass
    def scrollToBottom(self): pass
    def setCornerButtonEnabled(self, b): pass

    # --- combo -------------------------------------------------------------
    def addItems(self, items):
        for it in items: self.addItem(it)
    def setCurrentIndex(self, i):
        old = self._current_index
        self._current_index = i
        if old != i:
            self.currentIndexChanged.emit(i)
            if 0 <= i < len(self._items):
                self.currentTextChanged.emit(str(self._items[i]))
    def currentIndex(self): return self._current_index
    def currentText(self):
        if 0 <= self._current_index < len(self._items):
            return str(self._items[self._current_index])
        return ""
    def findText(self, text, *a):
        for i, it in enumerate(self._items):
            if str(it) == text: return i
        return -1
    def setEditable(self, b): pass

    # --- tabs / stack ------------------------------------------------------
    def addTab(self, widget, label):
        self._tabs.append((widget, str(label)))
        return len(self._tabs) - 1
    def insertTab(self, index, widget, label):
        self._tabs.insert(index, (widget, str(label)))
        return index
    def setTabText(self, index, text):
        if 0 <= index < len(self._tabs): self._tabs[index] = (self._tabs[index][0], str(text))
    def tabText(self, index): return self._tabs[index][1] if 0 <= index < len(self._tabs) else ""
    def count(self): return len(self._tabs) if self._tabs else len(self._items)
    def tabBar(self): return QWidget(self)
    def setCurrentIndex(self, i):
        old = self._current_index
        self._current_index = i
        if old != i: self.currentIndexChanged.emit(i)
    def currentWidget(self):
        return self._tabs[self._current_index][0] if 0 <= self._current_index < len(self._tabs) else None
    def setCurrentWidget(self, w):
        for i, (widget, _) in enumerate(self._tabs):
            if widget is w:
                self.setCurrentIndex(i); return
    def indexOf(self, widget):
        for i, (w, _) in enumerate(getattr(self, "_tabs", [])):
            if w is widget: return i
        for i, child in enumerate(self._children):
            if child is widget: return i
        return -1

    # --- menu --------------------------------------------------------------
    def addMenu(self, title):
        menu = QMenu(str(title), self)
        self._children.append(menu)
        return menu
    def addAction(self, action, *a, **kw):
        if isinstance(action, str):
            from .QtGui import QAction
            action = QAction(action, self)
        self._children.append(action)
        return action
    def addSeparator(self): pass
    def menuBar(self): return getattr(self, "_menubar", None)
    def setMenuBar(self, mb): self._menubar = mb; mb._parent = self
    def statusBar(self): return getattr(self, "_statusbar", None)
    def setStatusBar(self, sb): self._statusbar = sb; sb._parent = self
    def setCentralWidget(self, w):
        self._central = w
        if w is not None: w._parent = self
    def centralWidget(self): return getattr(self, "_central", None)
    def toolBar(self, name=None): return getattr(self, "_toolbar", None)
    def setToolBar(self, tb): self._toolbar = tb
    def setWindowMenu(self, m): pass

    # --- scroll / splitter -------------------------------------------------
    def setWidget(self, w): self._inner = w; w._parent = self
    def widget(self): return getattr(self, "_inner", None)
    def setWidgetResizable(self, b): pass
    def setFrameShape(self, s): pass
    def setFrameShadow(self, s): pass
    def setLineWidth(self, w): pass
    def setMidLineWidth(self, w): pass
    def setHorizontalScrollBarPolicy(self, p): pass
    def setVerticalScrollBarPolicy(self, p): pass
    def horizontalScrollBar(self): return QWidget(self)
    def verticalScrollBar(self): return QWidget(self)
    def setContentsMargins(self, *a): pass
    def addWidget(self, w, *a, **kw):
        if self._layout: self._layout.addWidget(w, *a, **kw)
        else: self._children.append(w)
    def insertWidget(self, i, w, *a, **kw): self._children.insert(i, w)
    def setCollapsible(self, i, b): pass
    def setStretchFactor(self, i, s): pass
    def handle(self, i): return QSplitterHandle(self._orientation, self)
    def setHandleWidth(self, w): pass
    def setChildrenCollapsible(self, b): pass
    def setOpaqueResize(self, b): pass
    def setSizes(self, sizes): pass
    def sizes(self): return []
    def setTitle(self, t): self.setText(t)

    # --- dialog ------------------------------------------------------------
    def exec(self): return 1
    exec_ = exec
    def accept(self): self.accepted.emit()
    def reject(self): self.rejected.emit()
    def done(self, r): (self.accepted if r else self.rejected).emit()
    def result(self): return 1
    def setModal(self, b): pass
    def setWindowFlags(self, f): pass
    def windowFlags(self): return 0

    # --- render helper -----------------------------------------------------
    def widget_type(self): return type(self).__name__


class _SelectionModel:
    def __init__(self, owner): self.owner = owner
    def selectedRows(self): return [self.owner._current_row] if self.owner._current_row >= 0 else []
    def currentIndex(self): return _ModelIndex(self.owner._current_row)
    def hasSelection(self): return self.owner._current_row >= 0
    def clearSelection(self): self.owner._selected_rows = []


class _ModelIndex:
    def __init__(self, row=0, col=0): self._row, self._col = row, col
    def row(self): return self._row
    def column(self): return self._col
    def isValid(self): return self._row >= 0
    def data(self, role=0): return None


class QFrame(QWidget):
    class Shape(_EnumNS):
        __values__ = {"NoFrame": 0, "Box": 1, "Panel": 2, "StyledPanel": 3, "HLine": 4, "VLine": 5}
    class Shadow(_EnumNS):
        __values__ = {"Plain": 0, "Raised": 1, "Sunken": 2}


class QAbstractScrollArea(QFrame):
    SizeAdjustPolicy = _EnumNS({
        "AdjustIgnored": 0, "AdjustToContents": 1, "AdjustToContentsOnFirstShow": 2,
    })
class QAbstractItemView(QAbstractScrollArea): pass
class QAbstractButton(QWidget): pass


class QLabel(QFrame):
    class TextFormat(_EnumNS):
        __values__ = {"PlainText": 0, "RichText": 1, "AutoText": 2, "MarkdownText": 3}
    def setPixmap(self, p): self._props["pixmap"] = p
    def pixmap(self): return self._props.get("pixmap")
    def setWordWrap(self, b): self._props["wordWrap"] = b
    def setScaledContents(self, b): pass
    def setAlignment(self, a): self._props["alignment"] = a
    def setBuddy(self, b): self._props["buddy"] = b
    def sizeHint(self): return QSize(max(40, len(self._text) * 7), 24)


class QPushButton(QAbstractButton): pass
class QToolButton(QAbstractButton): pass
class QRadioButton(QAbstractButton): pass
class QCheckBox(QAbstractButton): pass


class QLineEdit(QWidget):
    class EchoMode(_EnumNS):
        __values__ = {"Normal": 0, "NoEcho": 1, "Password": 2, "PasswordEchoOnEdit": 3}
    def setInputMask(self, m): pass
    def setMaxLength(self, n): pass
    def home(self): pass
    def end(self): pass


class QTextEdit(QAbstractScrollArea):
    def setAcceptRichText(self, b): pass
    def setUndoRedoEnabled(self, b): pass


class QPlainTextEdit(QAbstractScrollArea):
    class LineWrapMode(_EnumNS):
        __values__ = {"NoWrap": 0, "WidgetWidth": 1, "PixelWidth": 2}
    def setMaximumBlockCount(self, n): pass
    def blockCount(self): return len(self._text.split("\n"))


class QTextBrowser(QTextEdit):
    def setOpenExternalLinks(self, b): pass


class QComboBox(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._editable = False


class QSpinBox(QAbstractButton): pass
class QDoubleSpinBox(QSpinBox):
    def setDecimals(self, n): pass
    def setSuffix(self, s): pass
    def setPrefix(self, s): pass


class QSlider(QAbstractButton): pass
class QDial(QAbstractButton): pass
class QProgressBar(QWidget):
    def setTextVisible(self, b): pass
    def setAlignment(self, a): pass


class QListWidgetItem:
    def __init__(self, text="", parent=None):
        self._text = str(text)
        self._flags = 0
        self._data = {}
        self._icon = None
        self._tool_tip = ""
        self._hidden = False
        self._selected = False
        self._parent = parent
    def text(self): return self._text
    def setText(self, t): self._text = str(t)
    def setFlags(self, f): self._flags = f
    def flags(self): return self._flags
    def setData(self, role, value): self._data[role] = value
    def data(self, role): return self._data.get(role)
    def setIcon(self, icon): self._icon = icon
    def icon(self): return self._icon
    def setToolTip(self, t): self._tool_tip = str(t)
    def toolTip(self): return self._tool_tip
    def setHidden(self, b): self._hidden = b
    def isHidden(self): return self._hidden
    def setSelected(self, b): self._selected = b
    def isSelected(self): return self._selected
    def setCheckState(self, s): self._data[10] = s
    def checkState(self): return self._data.get(10, 0)
    def setBackground(self, b): pass
    def setForeground(self, b): pass
    def setSizeHint(self, s): pass
    def __str__(self): return self._text


class QListWidget(QAbstractItemView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
    def setIconSize(self, s): pass
    def setResizeMode(self, m): pass
    def setUniformItemSizes(self, b): pass
    def scrollToItem(self, item, *a): pass
    def itemAt(self, *a): return None


class QTableWidgetItem:
    def __init__(self, text="", type=0):
        self._text = str(text)
        self._type = type
        self._data = {}
        self._flags = 0
        self._icon = None
        self._tool_tip = ""
        self._background = None
        self._foreground = None
        self._font = None
        self._alignment = None
        self._check_state = 0
    def text(self): return self._text
    def setText(self, t): self._text = str(t)
    def setData(self, role, value): self._data[role] = value
    def data(self, role): return self._data.get(role)
    def setFlags(self, f): self._flags = f
    def flags(self): return self._flags
    def setIcon(self, i): self._icon = i
    def icon(self): return self._icon
    def setToolTip(self, t): self._tool_tip = str(t)
    def toolTip(self): return self._tool_tip
    def setBackground(self, b): self._background = b
    def background(self): return self._background
    def setForeground(self, b): self._foreground = b
    def foreground(self): return self._foreground
    def setFont(self, f): self._font = f
    def setTextAlignment(self, a): self._alignment = a
    def setCheckState(self, s): self._check_state = s
    def checkState(self): return self._check_state
    def setSelected(self, b): pass
    def isSelected(self): return False
    def setSizeHint(self, s): pass
    def __str__(self): return self._text


class QHeaderView(QAbstractItemView):
    class ResizeMode(_EnumNS):
        __values__ = {"Fixed": 0, "Interactive": 1, "Stretch": 2, "ResizeToContents": 3}
    def __init__(self, parent=None, orientation=None):
        super().__init__(parent)
        self._orientation = orientation or Qt.Orientation.Horizontal
    def setSectionResizeMode(self, *a): pass
    def setSectionsClickable(self, b): pass
    def setSectionsMovable(self, b): pass
    def setHighlightSections(self, b): pass
    def setDefaultSectionSize(self, n): pass
    def setMinimumSectionSize(self, n): pass
    def stretchLastSection(self): return False
    def setStretchLastSection(self, b): pass
    def setSortIndicator(self, *a): pass
    def setVisible(self, b): pass


class QTableWidget(QTableView if False else QAbstractItemView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cell_widgets = {}
    def setItem(self, row, col, item): self._cell_widgets[(row, col)] = item
    def item(self, row, col): return self._cell_widgets.get((row, col))
    def itemAt(self, p): return None
    def setCellWidget(self, row, col, widget): self._cell_widgets[(row, col)] = widget
    def cellWidget(self, row, col): return self._cell_widgets.get((row, col))
    def removeCellWidget(self, row, col): self._cell_widgets.pop((row, col), None)
    def currentRow(self): return self._current_row
    def currentColumn(self): return self._current_index
    def currentCell(self): return (self._current_row, self._current_index)
    def setCurrentCell(self, row, col): self._current_row, self._current_index = row, col
    def selectRow(self, row): self._current_row = row
    def selectedRanges(self): return []


class QTreeWidgetItem:
    def __init__(self, texts=None, parent=None):
        self._texts = list(texts or [])
        self._children = []
        self._data = {}
        self._parent = parent
        if parent is not None: parent._children.append(self)
    def text(self, col=0): return self._texts[col] if 0 <= col < len(self._texts) else ""
    def setText(self, col, t):
        while len(self._texts) <= col: self._texts.append("")
        self._texts[col] = str(t)
    def addChild(self, child): child._parent = self; self._children.append(child)
    def childCount(self): return len(self._children)
    def child(self, i): return self._children[i]
    def setData(self, col, role, value): self._data[(col, role)] = value
    def data(self, col, role): return self._data.get((col, role))
    def setFlags(self, f): pass
    def setExpanded(self, b): pass
    def setSelected(self, b): pass
    def __str__(self): return " / ".join(self._texts)


class QTreeWidget(QAbstractItemView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._top = []
    def setColumnCount(self, n): self._columns = n
    def setHeaderLabels(self, labels): self._headers = list(labels)
    def addTopLevelItem(self, item): self._top.append(item); return item
    def topLevelItemCount(self): return len(self._top)
    def topLevelItem(self, i): return self._top[i]
    def invisibleRootItem(self): return QTreeWidgetItem()
    def expandAll(self): pass
    def collapseAll(self): pass
    def currentItem(self): return None


class QListView(QAbstractItemView): pass
class QTableView(QAbstractItemView): pass
class QTreeView(QAbstractItemView): pass


class QTabWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs = []
        self._current_index = -1
    def addTab(self, widget, label):
        self._tabs.append((widget, str(label)))
        return len(self._tabs) - 1
    def insertTab(self, i, widget, label): self._tabs.insert(i, (widget, str(label))); return i
    def setTabText(self, i, t):
        if 0 <= i < len(self._tabs): self._tabs[i] = (self._tabs[i][0], str(t))
    def tabText(self, i): return self._tabs[i][1] if 0 <= i < len(self._tabs) else ""
    def setCurrentIndex(self, i):
        old = self._current_index
        self._current_index = i
        if old != i: self.currentIndexChanged.emit(i)
    def currentIndex(self): return self._current_index
    def currentWidget(self): return self._tabs[self._current_index][0] if 0 <= self._current_index < len(self._tabs) else None
    def setCurrentWidget(self, w):
        for i, (widget, _) in enumerate(self._tabs):
            if widget is w: self.setCurrentIndex(i); return
    def count(self): return len(self._tabs)
    def widget(self, i): return self._tabs[i][0] if 0 <= i < len(self._tabs) else None
    def setTabsClosable(self, b): pass
    def setMovable(self, b): pass
    def tabBar(self): return QWidget(self)


class QStackedWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs = []
        self._current_index = -1
    def addWidget(self, w): self._tabs.append((w, "")); return len(self._tabs) - 1
    def insertWidget(self, i, w): self._tabs.insert(i, (w, "")); return i
    def setCurrentIndex(self, i): self._current_index = i; self.currentIndexChanged.emit(i)
    def currentIndex(self): return self._current_index
    def currentWidget(self): return self._tabs[self._current_index][0] if 0 <= self._current_index < len(self._tabs) else None
    def setCurrentWidget(self, w):
        for i, (widget, _) in enumerate(self._tabs):
            if widget is w: self.setCurrentIndex(i); return
    def count(self): return len(self._tabs)


class QGroupBox(QFrame):
    def setTitle(self, t): self.setText(t)
    def title(self): return self.text()
    def setCheckable(self, b): self._checkable = b
    def isCheckable(self): return self._checkable
    def setChecked(self, b): self._checked = b
    def isChecked(self): return self._checked


class QScrollArea(QAbstractScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._inner = None
    def setWidget(self, w): self._inner = w; w._parent = self
    def widget(self): return self._inner
    def setWidgetResizable(self, b): pass


class QSplitter(QFrame):
    def __init__(self, orientation=None, parent=None):
        super().__init__(parent)
        self._orientation = orientation or Qt.Orientation.Horizontal
        self._collapsible = []
    def addWidget(self, w, *a, **kw): self._children.append(w); w._parent = self
    def insertWidget(self, i, w, *a, **kw): self._children.insert(i, w); w._parent = self
    def setCollapsible(self, i, b): self._collapsible.append(b)
    def setStretchFactor(self, i, s): pass
    def setSizes(self, sizes): pass
    def sizes(self): return []
    def handle(self, i): return QSplitterHandle(self._orientation, self)
    def count(self): return len(self._children)
    def setOrientation(self, o): self._orientation = o
    def orientation(self): return self._orientation
    def setChildrenCollapsible(self, b): pass
    def setOpaqueResize(self, b): pass
    def setHandleWidth(self, w): pass


class QSplitterHandle(QWidget):
    def __init__(self, orientation=None, parent=None):
        super().__init__(parent)
        self._orientation = orientation
    def splitter(self): return self._parent


class QMenu(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._title = str(title)
        self._actions = []
    def setTitle(self, t): self._title = str(t)
    def title(self): return self._title
    def addAction(self, action, *a, **kw):
        from .QtGui import QAction
        if isinstance(action, str): action = QAction(action, self)
        self._actions.append(action)
        return action
    def addMenu(self, title):
        m = QMenu(title, self); self._children.append(m); return m
    def addSeparator(self): pass
    def actions(self): return list(self._actions)
    def menuAction(self):
        from .QtGui import QAction
        if not hasattr(self, "_menu_action"):
            self._menu_action = QAction(self._title, self)
        return self._menu_action
    def exec(self, *a): return None
    popup = exec
    def setIcon(self, i): pass


class QMenuBar(QFrame):
    def addMenu(self, title): return QWidget.addMenu(self, title)
    def setNativeMenuBar(self, b): pass


class QToolBar(QFrame):
    def addAction(self, action, *a, **kw): return QWidget.addAction(self, action, *a, **kw)
    def addSeparator(self): pass
    def addWidget(self, w): self._children.append(w)
    def setAllowedAreas(self, a): pass
    def setOrientation(self, o): self._orientation = o
    def setToolButtonStyle(self, s): pass
    def setIconSize(self, s): pass
    def clear(self): self._children = []


class QDialog(QWidget):
    DialogCode = _EnumNS({"Rejected": 0, "Accepted": 1})

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        self._result = 0

    def exec(self):
        try:
            from android_bridge import bridge
            return bridge.run_modal(self)
        except Exception:
            self.show()
            return 1
    exec_ = exec
    def accept(self):
        self._result = 1
        self.accepted.emit()
    def reject(self):
        self._result = 0
        self.rejected.emit()
    def result(self): return self._result
    def setResult(self, r): self._result = r


class QFileDialog(QDialog):
    Options = _EnumNS({"DontResolveSymlinks": 1, "ShowDirsOnly": 2})

    def __init__(self, parent=None, *a, **kw):
        super().__init__(parent)
        self._directory = ""
        self._selected_file = ""

    def setDirectory(self, path): self._directory = str(path)
    def directory(self): return self._directory
    def selectFile(self, path): self._selected_file = str(path)
    def selectedFiles(self): return [self._selected_file] if self._selected_file else []
    def setAcceptMode(self, m): pass
    def setFileMode(self, m): pass
    def setOption(self, o, on=True): pass
    def getNameFilters(self): return []

    class AcceptMode(_EnumNS):
        __values__ = {"AcceptOpen": 0, "AcceptSave": 1}
    class FileMode(_EnumNS):
        __values__ = {"AnyFile": 0, "ExistingFile": 1, "Directory": 2, "ExistingFiles": 3}
    class Option(_EnumNS):
        __values__ = {"ShowDirsOnly": 1}

    @staticmethod
    def _pick(mode, parent=None, caption="", directory="", filter="", *a, **kw):
        try:
            from android_bridge import bridge
            path = bridge.pick_file(mode, caption, directory, filter)
        except Exception as exc:
            print("QFileDialog fallback:", exc)
            path = ""
        return (path, "" if not path else filter.split(";;")[0] if filter else "")

    @staticmethod
    def getOpenFileName(parent=None, caption="", directory="", filter="", *a, **kw):
        return QFileDialog._pick("open", parent, caption, directory, filter)

    @staticmethod
    def getSaveFileName(parent=None, caption="", directory="", filter="", *a, **kw):
        return QFileDialog._pick("save", parent, caption, directory, filter)

    @staticmethod
    def getExistingDirectory(parent=None, caption="", directory="", *a, **kw):
        return QFileDialog._pick("dir", parent, caption, directory, "")[0]

    @staticmethod
    def getOpenFileNames(parent=None, caption="", directory="", filter="", *a, **kw):
        path = QFileDialog._pick("open", parent, caption, directory, filter)[0]
        return ([path] if path else [], "")


class QMessageBox(QDialog):
    Ok = 1
    Yes = 2
    No = 4
    Cancel = 8
    Information = 4
    Warning = 3
    Critical = 2
    Question = 1

    @staticmethod
    def _message(method, parent, title, text, *a, **kw):
        try:
            from android_bridge import bridge
            return bridge.show_message(method, str(title), str(text))
        except Exception:
            print("[%s] %s" % (title, text))
            return QMessageBox.Ok

    @staticmethod
    def information(parent, title, text, *a, **kw):
        return QMessageBox._message("info", parent, title, text)
    @staticmethod
    def warning(parent, title, text, *a, **kw):
        return QMessageBox._message("warn", parent, title, text)
    @staticmethod
    def critical(parent, title, text, *a, **kw):
        return QMessageBox._message("error", parent, title, text)
    @staticmethod
    def question(parent, title, text, *a, **kw):
        return QMessageBox._message("confirm", parent, title, text)
    @staticmethod
    def about(parent, title, text): return QMessageBox._message("info", parent, title, text)
    def setIcon(self, i): pass
    def setStandardButtons(self, b): pass
    def setDefaultButton(self, b): pass
    def setDetailedText(self, t): pass
    def setInformativeText(self, t): pass
    def text(self): return self._text


class QInputDialog(QDialog):
    @staticmethod
    def getText(parent, title, label, mode=0, text="", *a, **kw):
        try:
            from android_bridge import bridge
            value = bridge.prompt(str(title), str(label), str(text))
        except Exception:
            value = ""
        return (value, bool(value))
    @staticmethod
    def getInt(parent, title, label, value=0, *a, **kw):
        text, ok = QInputDialog.getText(parent, title, label, 0, str(value))
        try: value = int(text)
        except Exception: pass
        return (value, ok)
    @staticmethod
    def getItem(parent, title, label, items, current=0, editable=True, *a, **kw):
        try:
            from android_bridge import bridge
            value = bridge.prompt(title, label, "")
        except Exception:
            value = ""
        return (value or (items[current] if items else ""), bool(value) or bool(items))


class QProgressDialog(QDialog):
    def setRange(self, lo, hi): self.setMinimum(lo); self.setMaximum(hi)
    def setLabelText(self, t): self.setText(t)
    def setCancelButtonText(self, t): pass
    def wasCanceled(self): return False
    def setAutoClose(self, b): pass
    def setAutoReset(self, b): pass


class QErrorMessage(QDialog):
    def showMessage(self, msg): print(msg)


class QMainWindow(QWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        self._menubar = QMenuBar(self)
        self._statusbar = QFrame(self)
        self._central = None
        self._is_window = True
        self._toolbar = QToolBar(self)

    def menuBar(self): return self._menubar
    def setMenuBar(self, mb): self._menubar = mb; mb._parent = self
    def statusBar(self): return self._statusbar
    def setStatusBar(self, sb): self._statusbar = sb; sb._parent = self
    def setCentralWidget(self, w): self._central = w; w._parent = self
    def centralWidget(self): return self._central
    def toolBar(self, name=None): return self._toolbar
    def setWindowMenu(self, m): pass
    def saveState(self): return b""
    def restoreState(self, s): return True
    def saveGeometry(self): return b""
    def restoreGeometry(self, g): return True


class QApplication(QObject):
    _instance = None

    def __init__(self, argv=None):
        super().__init__()
        QApplication._instance = self
        self._argv = list(argv or [])
        self._windows = []
        self._quit = False
        self._style = "Fusion"

    @staticmethod
    def instance(): return QApplication._instance
    @staticmethod
    def activeWindow():
        inst = QApplication._instance
        return inst._windows[-1] if inst and inst._windows else None
    @staticmethod
    def topLevelWidgets():
        inst = QApplication._instance
        return list(inst._windows) if inst else []
    @staticmethod
    def allWidgets():
        inst = QApplication._instance
        if inst is None: return []
        out = []
        def walk(w):
            out.append(w)
            for c in getattr(w, "_children", []):
                if isinstance(c, QWidget): walk(c)
            lay = getattr(w, "layout", lambda: None)()
            if lay:
                for item in lay._items:
                    if item.widget: walk(item.widget)
                    elif item.layout:
                        for sub in item.layout._items:
                            if sub.widget: walk(sub.widget)
        for w in inst._windows: walk(w)
        return out
    @staticmethod
    def processEvents(*a, **kw): pass
    @staticmethod
    def setStyle(s):
        if QApplication._instance: QApplication._instance._style = s
    @staticmethod
    def style(): return QApplication._instance._style if QApplication._instance else "Fusion"
    @staticmethod
    def setStyleSheet(s):
        if QApplication._instance: QApplication._instance._props["styleSheet"] = s
    @staticmethod
    def styleSheet(): return ""
    @staticmethod
    def setWindowIcon(icon):
        if QApplication._instance: QApplication._instance._props["windowIcon"] = icon
    @staticmethod
    def setFont(f): pass
    @staticmethod
    def font(): return None
    @staticmethod
    def setQuitOnLastWindowClosed(b): pass
    @staticmethod
    def setOverrideCursor(c): pass
    @staticmethod
    def restoreOverrideCursor(): pass
    @staticmethod
    def translate(*a, **kw): return ""
    @staticmethod
    def quit():
        if QApplication._instance: QApplication._instance._quit = True
    def exec(self):
        # On Android there is no blocking Qt event loop: the WebView owns the
        # main loop and calls back into Python.  Rendering starts in
        # android_bridge after setupUi() completes.
        return 0
    exec_ = exec


# Backwards-compatible aliases sometimes used by generated code.
QWidgetItem = QLayoutItem
QButtonGroup = QWidget
QCalendarWidget = QWidget
QDateEdit = QSpinBox
QTimeEdit = QSpinBox
QDateTimeEdit = QSpinBox
QDockWidget = QWidget
QGraphicsView = QAbstractScrollArea
QKeyEdit = QLineEdit
QWizard = QDialog
QWizardPage = QWidget
QSystemTrayIcon = QObject

# Expose enum aliases used directly (e.g. QListWidget.SelectionMode).
QListWidget.SelectionMode = QWidget.SelectionMode
QTableWidget.SelectionMode = QWidget.SelectionMode
QTreeWidget.SelectionMode = QWidget.SelectionMode
QListView.SelectionMode = QWidget.SelectionMode
