"""Bridge between the unmodified mtkclient GUI and the Android WebView front-end.

The Qt widget tree created by ``mtk_gui.MainWindow`` is kept intact.  It is
serialized to mobile HTML/CSS, and user events from the WebView are dispatched
back into the original Qt signals.  No upstream GUI code is rewritten.
"""
import html
import json
import logging
import os
import sys
import threading

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QAbstractButton, QCheckBox,
    QLineEdit, QPlainTextEdit, QTextEdit, QLabel, QComboBox, QSpinBox,
    QDoubleSpinBox, QSlider, QProgressBar, QTabWidget, QTableWidget,
    QListWidget, QTreeWidget, QMenu, QMenuBar,
    QStackedWidget, QScrollArea, QDialog, QSplitter,
)
from PySide6.QtGui import QAction


# Chaquopy does not always provide stdout/stderr on the Python worker thread.
# mtkclient's logging config and many except blocks call print(), which would
# otherwise raise: AttributeError: 'NoneType' object has no attribute 'write'.
class _SafeStream:
    def write(self, text):
        try:
            from java import jclass
            jclass("android.util.Log").d("MTKClientPython", str(text).rstrip())
        except Exception:
            pass
        return len(str(text))

    def flush(self): pass
    def isatty(self): return False
    def writable(self): return True
    def writelines(self, lines):
        for line in lines:
            self.write(line)


if sys.stdout is None:
    sys.stdout = _SafeStream()
if sys.stderr is None:
    sys.stderr = _SafeStream()

# mtkclient's UsbClass only initialises `self.backend` for linux/win32/darwin.
# Chaquopy reports 'android', which leaves the attribute unset and crashes
# DeviceHandler construction.  Android uses the same /dev + libusb-style paths
# as Linux here, and our usb.backend.libusb1 shim returns None safely.
if sys.platform == "android":
    sys.platform = "linux"


class _State:
    def __init__(self):
        self.app = None
        self.win = None
        self.devhandler = None
        self.thread = None
        self.by_id = {}
        self.ids = {}
        self.dialogs = {}
        self.lock = threading.RLock()
        self.ready = False
        self.last_html = ""


state = _State()


# ---------------------------------------------------------------------------
# Java bridge access
# ---------------------------------------------------------------------------
def _java():
    from java import jclass
    return jclass("com.mtkclient.android.AndroidBridge")


def ui_thread(fn):
    """Run a Python callable on Android's main/UI thread."""
    return _java().runOnUiThread(fn)


def open_url(url):
    _java().openUrl(str(url))


def show_message(kind, title, text):
    return _java().showMessage(str(kind), str(title), str(text))


def prompt(title, label, default=""):
    return _java().prompt(str(title), str(label), str(default)) or ""


def pick_file(mode, caption="", directory="", filter=""):
    return _java().pickFile(str(mode), str(caption), str(directory), str(filter)) or ""


def hasRoot():
    try:
        return bool(_java().hasRoot())
    except Exception:
        return False


def list_usb_devices():
    return json.loads(_java().listUsbDevices() or "[]")


def list_serial_ports():
    return json.loads(_java().listSerialPorts() or "[]")


def serial_open(port, baudrate, bytesize, parity, stopbits):
    return _java().serialOpen(str(port), int(baudrate), int(bytesize), str(parity), float(stopbits))


def serial_close(handle): return _java().serialClose(str(handle))
def serial_write(handle, data): return _java().serialWrite(str(handle), bytes(data))
def serial_read(handle, size, timeout=100): return bytes(_java().serialRead(str(handle), int(size), int(timeout)) or b"")
def serial_available(handle): return _java().serialAvailable(str(handle)) or 0
def serial_discard_input(handle): return _java().serialDiscardInput(str(handle))
def serial_send_break(handle, duration): return _java().serialSendBreak(str(handle), float(duration))
def serial_set_signals(handle, rts, dtr): return _java().serialSetSignals(str(handle), bool(rts), bool(dtr))


def bulk_write(device_id, endpoint, data, timeout=1000):
    return _java().usbBulkWrite(str(device_id), int(endpoint), bytes(data), int(timeout))


def bulk_read(device_id, endpoint, size, timeout=1000):
    return bytes(_java().usbBulkRead(str(device_id), int(endpoint), int(size), int(timeout)) or b"")


def control_transfer(device_id, bm_request_type, b_request, w_value, w_index, data_or_length, timeout=1000):
    if isinstance(data_or_length, (bytes, bytearray, memoryview)):
        result = _java().usbControlOut(str(device_id), int(bm_request_type), int(b_request),
                                       int(w_value), int(w_index), bytes(data_or_length), int(timeout))
        return result
    return _java().usbControlIn(str(device_id), int(bm_request_type), int(b_request),
                                int(w_value), int(w_index), int(data_or_length or 0), int(timeout))


def set_configuration(device_id, value): return _java().usbSetConfiguration(str(device_id), int(value))
def clear_halt(device_id, endpoint): return _java().usbClearHalt(str(device_id), int(endpoint))
def reset_device(device_id): return _java().usbReset(str(device_id))
def asm(arch, mode, code_lines): return _java().asm(int(arch), int(mode), json.dumps(code_lines))
def disasm(arch, mode, code, address): return _java().disasm(int(arch), int(mode), bytes(code), int(address))
def uc_mem_map(*a): return None
def uc_mem_write(*a): return None
def uc_mem_read(*a): return None
def uc_reg_write(*a): return None
def uc_reg_read(*a): return None
def uc_emu_start(*a): return None


# ---------------------------------------------------------------------------
# GUI lifecycle — this mirrors mtk_gui.main() without starting a blocking loop
# ---------------------------------------------------------------------------
def bootstrap():
    """Build the real mtkclient GUI. Safe to call only once."""
    with state.lock:
        if state.ready:
            return render_html()

        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
        import mtk_gui
        from mtkclient.gui.toolkit import asyncThread
        from mtkclient.gui.themes import DARK_THEME, LIGHT_THEME

        app = QApplication([sys.argv[0], "-platform", "android"])
        app.setStyle("Fusion")
        try:
            mtk_gui.load_translations(app)
        except Exception as exc:
            print("load_translations:", exc)

        is_dark = bool(_java().isDarkMode())
        app.setStyleSheet(DARK_THEME if is_dark else LIGHT_THEME)

        loglevel = logging.INFO
        devhandler = mtk_gui.DeviceHandler(parent=app, preloader=None, loader=None,
                                          loglevel=loglevel)
        phone_info = {"chipset": "", "bootMode": "", "daInit": False,
                      "cdcInit": False, "cantConnect": False}
        thread = asyncThread(parent=app, n=0, function=mtk_gui.getDevInfo,
                             parameters=[loglevel, phone_info, devhandler])
        win = mtk_gui.MainWindow(thread=thread, app=app, devhandler=devhandler,
                                 phoneInfo=phone_info, loglevel=loglevel,
                                 is_dark=is_dark)
        win.setWindowTitle("MTKClient - Version 2.1.4")
        win.show()

        devhandler.sendToLogSignal.connect(win.sendToLog)
        thread.sendToLogSignal.connect(win.sendToLog)
        thread.sendUpdateSignal.connect(win.updateGui)
        thread.sendToProgressSignal.connect(win.sendToProgress)
        win.setdevhandler(devhandler)
        thread.start()

        state.app = app
        state.win = win
        state.devhandler = devhandler
        state.thread = thread
        state.ready = True
        state.last_html = render_html()
        return state.last_html


def shutdown():
    with state.lock:
        thread = state.thread
        state.ready = False
    if thread is not None:
        try:
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)
                if thread.isRunning():
                    thread.terminate()
            thread.wait()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Widget ids
# ---------------------------------------------------------------------------
def widget_id(widget):
    key = id(widget)
    wid = state.ids.get(key)
    if wid is None:
        wid = "w%d" % (len(state.ids) + 1)
        state.ids[key] = wid
        state.by_id[wid] = widget
    return wid


def resolve(wid):
    return state.by_id.get(str(wid))


def action_id(action):
    return "a:" + (action.objectName() or action.text() or str(id(action)))


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------
def _esc(text):
    return html.escape(str(text if text is not None else ""), quote=True)


def _is_visible(widget):
    return bool(getattr(widget, "_visible", True)) and bool(getattr(widget, "_enabled", True))


def _layout_nodes(widget, depth=0):
    """Return (widget, depth) pairs in display order."""
    out = []
    layout = getattr(widget, "layout", lambda: None)()
    if layout is not None:
        for item in getattr(layout, "_items", []):
            if item.widget is not None:
                out.append((item.widget, depth + 1))
            elif item.layout is not None:
                out.extend(_layout_nodes_from_layout(item.layout, depth + 1))
            elif item.spacer is not None:
                out.append((item.spacer, depth + 1))
    # Widgets added directly (QSplitter/QScrollArea/QMainWindow central widget)
    if not out:
        for child in getattr(widget, "_children", []):
            if isinstance(child, QWidget) and not isinstance(child, (QMenu, QMenuBar)):
                out.append((child, depth + 1))
        central = getattr(widget, "_central", None)
        if central is not None:
            out.append((central, depth + 1))
        inner = getattr(widget, "_inner", None)
        if inner is not None:
            out.append((inner, depth + 1))
    return out


def _layout_nodes_from_layout(layout, depth):
    out = []
    for item in getattr(layout, "_items", []):
        if item.widget is not None:
            out.append((item.widget, depth))
        elif item.layout is not None:
            out.extend(_layout_nodes_from_layout(item.layout, depth))
        elif item.spacer is not None:
            out.append((item.spacer, depth))
    return out


def _render_menus(win):
    menus = []
    containers = [getattr(win, "_menubar", None), getattr(win, "_toolbar", None)]
    for container in containers:
        for child in getattr(container, "_children", []) or []:
            if isinstance(child, QMenu):
                menus.append({"title": child.title(),
                              "actions": [{"id": action_id(a), "text": a.text(),
                                           "checked": a.isChecked()}
                                          for a in child.actions()]})
    return menus


def _render_widget(widget, depth=0):
    if widget is None:
        return ""
    if not isinstance(widget, QWidget) and not hasattr(widget, "_items"):
        return ""

    wid = widget_id(widget)
    name = widget.objectName() or ""
    typ = type(widget).__name__
    hidden = not _is_visible(widget)
    style = ' style="display:none"' if hidden else ""

    if isinstance(widget, QMenuBar) or isinstance(widget, QMenu) or typ == "QMenuBar":
        return ""

    if isinstance(widget, QTabWidget) or typ == "QTabWidget":
        tabs = []
        for i, (child, label) in enumerate(getattr(widget, "_tabs", [])):
            body = "".join(_render_widget(w, depth + 1) for w, _ in _layout_nodes(child, depth))
            tabs.append('<section class="tabpanel" data-tab="%s" data-parent="%s"%s>'
                        '<h3>%s</h3>%s</section>' %
                        (i, wid, "" if i == getattr(widget, "_current_index", 0) else " hidden",
                         _esc(label), body))
        tabbar = '<nav class="tabs">' + "".join(
            '<button class="tabbtn%s" data-widget="%s" data-action="tab" data-value="%d">%s</button>' %
            (" active" if i == getattr(widget, "_current_index", 0) else "", wid, i, _esc(label))
            for i, (_, label) in enumerate(getattr(widget, "_tabs", []))) + "</nav>"
        return '<div class="tabs-wrap" id="%s">%s%s</div>' % (wid, tabbar, "".join(tabs))

    if isinstance(widget, QTableWidget):
        rows, cols = widget.rowCount(), widget.columnCount()
        head = "".join("<th>%s</th>" % _esc(widget._headers[i] if i < len(widget._headers) else i)
                       for i in range(cols))
        body = []
        for r in range(rows):
            cells = []
            for c in range(cols):
                item = widget.item(r, c)
                cells.append("<td>%s</td>" % _esc(item.text() if item else ""))
            body.append("<tr>%s</tr>" % "".join(cells))
        return '<div class="table-wrap" id="%s"%s><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
            wid, style, head, "".join(body))

    if isinstance(widget, QListWidget):
        items = []
        for i, item in enumerate(getattr(widget, "_items", [])):
            try:
                items.append('<li class="listitem%s" data-widget="%s" data-action="row" data-value="%d">%s</li>' % (
                    " selected" if i == getattr(widget, "_current_row", -1) else "",
                    wid, i, _esc(item.text() if hasattr(item, "text") else item)))
            except Exception:
                pass
        return '<ul class="list" id="%s"%s>%s</ul>' % (wid, style, "".join(items))

    if isinstance(widget, QTreeWidget):
        def tree_items(items, level=0):
            out = []
            for it in items:
                out.append('<li class="treeitem">%s%s</li>' % (
                    "&nbsp;" * level, _esc(it.text(0) if hasattr(it, "text") else it)))
                if hasattr(it, "_children"):
                    out.extend(tree_items(it._children, level + 1))
            return out
        return '<ul class="tree" id="%s"%s>%s</ul>' % (wid, style, "".join(tree_items(widget._top)))

    if isinstance(widget, (QCheckBox,)):
        return ('<label class="check" id="%s"%s><input type="checkbox" data-widget="%s" '
                'data-action="check"%s><span>%s</span></label>' %
                (wid, style, wid, " checked" if widget.isChecked() else "", _esc(widget.text() or name)))

    if isinstance(widget, QProgressBar):
        return ('<div class="progress" id="%s"%s><div class="bar" style="width:%d%%"></div>'
                '<span>%d%%</span></div>' % (wid, style, widget.value(), widget.value()))

    if isinstance(widget, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
        if isinstance(widget, QComboBox):
            options = "".join('<option%s>%s</option>' %
                              (" selected" if i == widget.currentIndex() else "", _esc(str(o)))
                              for i, o in enumerate(widget._items))
            return ('<select id="%s"%s data-widget="%s" data-action="index">%s</select>' %
                    (wid, style, wid, options))
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return ('<input type="number" id="%s"%s data-widget="%s" data-action="value" '
                    'min="%s" max="%s" value="%s">' %
                    (wid, style, wid, widget.minimum(), widget.maximum(), widget.value()))
        return ('<input type="text" id="%s"%s data-widget="%s" data-action="text" '
                'value="%s" placeholder="%s">' %
                (wid, style, wid, _esc(widget.text()), _esc(widget.placeholderText())))

    if isinstance(widget, (QPlainTextEdit, QTextEdit)):
        return ('<textarea id="%s"%s data-widget="%s" data-action="text" rows="6" readonly>%s</textarea>' %
                (wid, style, wid, _esc(widget.toPlainText())))

    if isinstance(widget, QLabel):
        return '<div class="label" id="%s"%s>%s</div>' % (wid, style, _esc(widget.text()))

    if isinstance(widget, QAbstractButton):
        return ('<button id="%s"%s data-widget="%s" data-action="click">%s</button>' %
                (wid, style, wid, _esc(widget.text() or name)))

    if isinstance(widget, QDialog):
        return ""

    children = _layout_nodes(widget, depth)
    body = "".join(_render_widget(w, d) for w, d in children)
    tag = "div"
    cls = "group"
    if isinstance(widget, QScrollArea):
        cls = "scrollarea"
    elif isinstance(widget, QSplitter):
        cls = "splitter"
    elif widget is state.win:
        cls = "window"
    return '<%s class="%s" id="%s"%s>%s</%s>' % (tag, cls, wid, style, body, tag)


CSS = """
:root{color-scheme:light dark;--bg:#12161c;--panel:#1d242e;--text:#e8edf4;--accent:#4a86c8;--border:#334154}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--panel);padding:10px 12px;border-bottom:1px solid var(--border)}
h1{font-size:17px;margin:0 0 8px}.tabs{display:flex;gap:4px;overflow-x:auto;padding-bottom:4px}
.tabbtn,button,select,input,textarea{background:#243044;color:var(--text);border:1px solid var(--border);border-radius:8px;padding:8px 10px;font:inherit}
button:active{background:var(--accent)}.tabbtn.active{border-color:var(--accent);color:#fff}
.tabpanel{padding:10px}.tabpanel h3{font-size:14px;margin:12px 0 6px;color:#9fc2ea}
.group,.window,.scrollarea,.splitter{display:block;padding:2px 0}
.label{padding:6px 8px;white-space:pre-wrap;word-break:break-word}
.check{display:flex;gap:8px;align-items:center;padding:8px 6px}.check input{width:20px;height:20px}
input[type=text],input[type=number],select,textarea{width:100%}
textarea{resize:vertical;font-family:monospace;min-height:90px}
.list,.tree{list-style:none;margin:0;padding:0}.listitem,.treeitem{padding:8px;border-bottom:1px solid var(--border)}
.listitem.selected{background:#29405a}.progress{position:relative;background:#243044;border-radius:8px;height:24px;margin:8px 0;overflow:hidden}
.progress .bar{position:absolute;inset:0 auto 0 0;background:var(--accent)}.progress span{position:relative;padding-left:8px}
.table-wrap{overflow:auto}.table-wrap table{width:100%;border-collapse:collapse}th,td{padding:6px;border:1px solid var(--border);text-align:left}
.menus{display:flex;gap:6px;flex-wrap:wrap}.menus details{position:relative}.menus summary{cursor:pointer;padding:6px 8px}
.menus .menu{position:absolute;background:var(--panel);border:1px solid var(--border);border-radius:8px;min-width:180px;z-index:10}
.menus button{display:block;width:100%;border:0;text-align:left}
"""


def render_html():
    if not state.ready or state.win is None:
        return "<html><body>MTKClient is starting…</body></html>"
    menus = _render_menus(state.win)
    menu_html = "".join(
        '<details><summary>%s</summary><div class="menu">%s</div></details>' %
        (_esc(m["title"]), "".join(
            '<button data-action="menu" data-value="%s">%s</button>' %
            (_esc(a["id"]), _esc(a["text"])) for a in m["actions"]))
        for m in menus)
    body = _render_widget(state.win)
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<style>%s</style></head><body><header><h1>MTKClient</h1>"
            "<div class='menus'>%s</div></header><main>%s</main>"
            "<script>%s</script></body></html>" % (CSS, menu_html, body, JS))


JS = """
function send(el, action, value){
  Android.handleWidget(el.getAttribute('data-widget')||el.id||'', action, String(value??''));
}
document.addEventListener('click', function(e){
  const el=e.target.closest('button[data-widget],li[data-widget]');
  if(!el) return;
  if(el.classList.contains('tabbtn')){send(el,'tab',el.dataset.value);return;}
  if(el.classList.contains('listitem')){send(el,'row',el.dataset.value);return;}
  send(el,'click','');
});
document.addEventListener('change', function(e){
  const el=e.target;
  if(!el.dataset||!el.dataset.widget) return;
  let action=el.dataset.action, value=el.value;
  if(el.type==='checkbox'){action='check';value=el.checked?'1':'0';}
  if(el.tagName==='SELECT'){action='index';value=el.selectedIndex;}
  send(el,action,value);
});
setInterval(function(){
  Android.sync(function(state){
    try{
      const data=JSON.parse(state);
      Object.keys(data).forEach(function(id){
        const el=document.getElementById(id);
        if(!el) return;
        const v=data[id];
        if(v.text!==undefined && (el.tagName==='TEXTAREA')) el.value=v.text;
        else if(v.text!==undefined && el.tagName==='DIV') el.textContent=v.text;
        if(v.value!==undefined && el.tagName==='INPUT') el.value=v.value;
        if(v.checked!==undefined && el.type==='checkbox') el.checked=v.checked;
        if(v.hidden!==undefined) el.style.display=v.hidden?'none':'';
      });
    }catch(e){}
  });
}, 800);
"""


def sync_state():
    """Return compact dynamic state for WebView polling."""
    out = {}
    def put(widget, **values):
        wid = state.ids.get(id(widget))
        if wid:
            out[wid] = values

    for key, widget in list(state.by_id.items()):
        try:
            if isinstance(widget, (QPlainTextEdit, QTextEdit)):
                put(widget, text=widget.toPlainText())
            elif isinstance(widget, QLabel):
                put(widget, text=widget.text(), hidden=not _is_visible(widget))
            elif isinstance(widget, QCheckBox):
                put(widget, checked=widget.isChecked(), hidden=not _is_visible(widget))
            elif isinstance(widget, (QLineEdit, QSpinBox, QDoubleSpinBox)):
                put(widget, value=widget.text() if isinstance(widget, QLineEdit) else widget.value())
            elif isinstance(widget, QProgressBar):
                put(widget, value=widget.value(), hidden=not _is_visible(widget))
        except Exception:
            continue
    return json.dumps(out)


# ---------------------------------------------------------------------------
# Event dispatch from WebView
# ---------------------------------------------------------------------------
def handle_widget(wid, action, value=""):
    widget = resolve(wid)
    if widget is None and str(wid).startswith("a:"):
        menu_action = _find_action(str(wid)[2:])
        if menu_action is not None:
            menu_action.trigger()
            return "ok"
        return "missing"
    if widget is None:
        return "missing"

    try:
        if action == "click":
            if hasattr(widget, "click"):
                widget.click()
            elif hasattr(widget, "trigger"):
                widget.trigger()
        elif action == "check":
            widget.setChecked(str(value).lower() in ("1", "true", "on"))
        elif action == "text":
            widget.setText(str(value))
        elif action == "value":
            if hasattr(widget, "setValue"):
                widget.setValue(str(value))
            else:
                widget.setText(str(value))
        elif action == "index":
            widget.setCurrentIndex(int(value))
        elif action == "row":
            widget.setCurrentRow(int(value))
        elif action == "menu":
            menu_action = _find_action(str(value))
            if menu_action is not None:
                menu_action.trigger()
        elif action == "dialog-accept":
            dialog = state.dialogs.get(str(wid))
            if dialog is not None:
                dialog.accept()
            _java().dialogResolved(True)
        elif action == "dialog-reject":
            dialog = state.dialogs.get(str(wid))
            if dialog is not None:
                dialog.reject()
            _java().dialogResolved(False)
        return "ok"
    except Exception as exc:
        print("handle_widget error:", type(widget).__name__, action, exc)
        return "error:%s" % exc


def _find_action(identifier):
    roots = [state.win] if state.win else []
    for root in roots:
        for obj in root.iter_widgets():
            if isinstance(obj, QAction) and (obj.objectName() == identifier or obj.text() == identifier):
                return obj
            for act in getattr(obj, "_actions", []) or []:
                if isinstance(act, QAction) and (act.objectName() == identifier or act.text() == identifier):
                    return act
        for act in getattr(root, "_actions", []) or []:
            if isinstance(act, QAction) and (act.objectName() == identifier or act.text() == identifier):
                return act
    return None


def run_modal(dialog):
    """Render a Qt dialog in the WebView and block until it is accepted."""
    from PySide6.QtWidgets import QListWidget
    wid = widget_id(dialog)
    with state.lock:
        state.dialogs[wid] = dialog
    body = _render_widget(dialog)
    buttons = ("<button data-action='dialog-accept' data-widget='%s'>OK</button>"
               "<button data-action='dialog-reject' data-widget='%s'>Cancel</button>" % (wid, wid))
    _java().showDialog("<h2>%s</h2>%s<div class='dialog-actions'>%s</div>" %
                       (_esc(dialog.windowTitle()), body, buttons))
    result = _java().waitForDialog(str(wid))
    with state.lock:
        state.dialogs.pop(wid, None)
    _java().closeDialog()
    return 1 if result else 0


def api(method, *args):
    """Generic entry point used by MainActivity for auxiliary Python things."""
    if method == "render":
        return render_html()
    if method == "sync":
        return sync_state()
    if method == "handle":
        return handle_widget(*args)
    if method == "shutdown":
        shutdown()
        return "ok"
    if method == "root_check":
        return "yes" if _java().hasRoot() else "no"
    return "unknown:" + method


# ---------------------------------------------------------------------------
# Compatibility façade used by the shim modules (`from android_bridge import bridge`).
# ---------------------------------------------------------------------------
class _Bridge:
    # UI
    open_url = staticmethod(open_url)
    show_message = staticmethod(show_message)
    prompt = staticmethod(prompt)
    pick_file = staticmethod(pick_file)
    run_modal = staticmethod(run_modal)
    # Device discovery
    list_usb_devices = staticmethod(list_usb_devices)
    list_serial_ports = staticmethod(list_serial_ports)
    # USB host I/O
    bulk_write = staticmethod(bulk_write)
    bulk_read = staticmethod(bulk_read)
    control_transfer = staticmethod(control_transfer)
    set_configuration = staticmethod(set_configuration)
    clear_halt = staticmethod(clear_halt)
    reset_device = staticmethod(reset_device)
    # Root serial I/O
    serial_open = staticmethod(serial_open)
    serial_close = staticmethod(serial_close)
    serial_write = staticmethod(serial_write)
    serial_read = staticmethod(serial_read)
    serial_available = staticmethod(serial_available)
    serial_discard_input = staticmethod(serial_discard_input)
    serial_send_break = staticmethod(serial_send_break)
    serial_set_signals = staticmethod(serial_set_signals)
    # Optional native-tool providers
    asm = staticmethod(asm)
    disasm = staticmethod(disasm)
    uc_mem_map = staticmethod(uc_mem_map)
    uc_mem_write = staticmethod(uc_mem_write)
    uc_mem_read = staticmethod(uc_mem_read)
    uc_reg_write = staticmethod(uc_reg_write)
    uc_reg_read = staticmethod(uc_reg_read)
    uc_emu_start = staticmethod(uc_emu_start)


bridge = _Bridge()
