# MTKClient for Android (root)

This fork packages [bkerler/mtkclient](https://github.com/bkerler/mtkclient) as an
installable, signed Android APK.  The original Python GUI (`mtk_gui.py` +
`mtkclient/gui/main_gui.py`) is executed unmodified; a PySide6 compatibility layer
renders the original Qt widget tree into a touch-friendly WebView and forwards
taps back into the original Qt signals.

## Layout

- `upstream/` — verbatim mtkclient source (including loaders and payloads). Nothing is deleted.
- `app/src/main/python/PySide6/` — PySide6 → WebView compatibility layer.
- `app/src/main/python/{usb,serial,termios,capstone,keystone,unicorn,mfusepy}` — Android adapters for desktop-only modules.
- `app/src/main/java/com/mtkclient/android/` — WebView activity, USB host, root serial and file picker bridge.
- `.github/workflows/setup-signing.yml` — one-time keystore generator; stores keystore + passwords in Actions secrets.
- `.github/workflows/build-apk.yml` — builds and signs the APK on every push to `main`.

## Required GitHub secrets

The signing workflow creates these automatically (run **1. Generate & store signing keystore** once):

| Secret | Purpose |
| --- | --- |
| `SIGNING_KEYSTORE_BASE64` | Release JKS keystore |
| `SIGNING_STORE_PASSWORD` | Keystore password |
| `SIGNING_KEY_ALIAS` | Key alias |
| `SIGNING_KEY_PASSWORD` | Key password |
| `GH_PAT` | Token with Actions secrets write access, used by the one-time setup workflow |

## Build

Push to `main` (or run **2. Build signed Android APK** manually). The signed APK is
uploaded as the `mtkclient-android-signed` artifact.

## Device requirements

- Android 7.0+ (API 24+), arm64-v8a or x86_64.
- Root (`su`) for direct `/dev/tty*` access and some flash operations.
- USB Host support for MediaTek preloader/DA ports. Permission is requested on attach.

## Known adapter limits

- Keystone/Capstone/Unicorn have no Android wheels. Their APIs are preserved; the shims delegate
  to an optional on-device provider or `llvm-*` tools and raise a clear error only when those
  optional assembly/emulation tools are actually invoked.
- FUSE mounts are not available on stock Android; the mtkclient file-browser actions are used instead.
