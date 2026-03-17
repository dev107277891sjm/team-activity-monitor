# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['server\\app.py'],
    pathex=[],
    binaries=[],
    datas=[('server/static', 'server/static'), ('server/database.py', '.')],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.loops.asyncio', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.http.httptools_impl', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.protocols.websockets.wsproto_impl', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'uvicorn.lifespan.off', 'fastapi', 'fastapi.staticfiles', 'starlette.responses', 'starlette.routing', 'starlette.middleware', 'starlette.middleware.cors', 'starlette.staticfiles', 'anyio._backends._asyncio', 'multipart', 'multipart.multipart', 'database', 'bcrypt', 'bcrypt._bcrypt', 'email.mime.text', 'email.mime.multipart', 'email.mime.base', 'sqlite3', 'json'],
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
    name='tam_admin_20260317',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icons\\tam_admin.ico'],
)
