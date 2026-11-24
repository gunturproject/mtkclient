"""Android compatibility layer for the PySide6 API used by mtkclient's GUI.

The upstream GUI (``mtk_gui.py`` + ``mtkclient/gui/main_gui.py``) is imported and
executed unmodified.  Qt widgets are kept as a real object tree; the Android
front-end renders that tree into a touch-friendly WebView and forwards user
events back into the original Qt signals/slots.
"""

__version__ = "6.10.1-android-compat"
