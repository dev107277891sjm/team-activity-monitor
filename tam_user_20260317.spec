# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['client\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('client/activity_tracker.py', '.'), ('client/alert_sender.py', '.'), ('client/buffer.py', '.'), ('client/capturer.py', '.'), ('client/config.py', '.'), ('client/connection.py', '.'), ('client/identity.py', '.'), ('client/keylogger.py', '.'), ('client/process_monitor.py', '.'), ('client/tray.py', '.'), ('client/uploader.py', '.')],
    hiddenimports=['pynput.keyboard._win32', 'pynput.mouse._win32', 'PIL._tkinter_finder', 'pystray', 'pystray._win32', 'mss', 'mss.windows', 'psutil', 'requests', 'requests.adapters', 'urllib3', 'cryptography', 'cryptography.fernet', 'zoneinfo', 'sqlite3', 'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'activity_tracker', 'alert_sender', 'buffer', 'capturer', 'config', 'connection', 'identity', 'keylogger', 'process_monitor', 'tray', 'uploader'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='tam_user_20260317',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icons\\tam_user.ico'],
)
