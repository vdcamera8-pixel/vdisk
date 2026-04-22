# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import playwright as _pw

PLAYWRIGHT_PATH = os.path.dirname(_pw.__file__)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config.json', '.'),
        (PLAYWRIGHT_PATH, 'playwright'),
    ],
    hiddenimports=[
        # Playwright
        'playwright',
        'playwright.sync_api',
        'playwright._impl._api_types',
        'playwright._impl._browser',
        'playwright._impl._browser_context',
        'playwright._impl._browser_type',
        'playwright._impl._cdp_session',
        'playwright._impl._chromium_browser_type',
        'playwright._impl._connection',
        'playwright._impl._dialog',
        'playwright._impl._download',
        'playwright._impl._element_handle',
        'playwright._impl._errors',
        'playwright._impl._event_context_manager',
        'playwright._impl._file_chooser',
        'playwright._impl._frame',
        'playwright._impl._helper',
        'playwright._impl._input',
        'playwright._impl._js_handle',
        'playwright._impl._keyboard',
        'playwright._impl._locator',
        'playwright._impl._mouse',
        'playwright._impl._network',
        'playwright._impl._page',
        'playwright._impl._playwright',
        'playwright._impl._route',
        'playwright._impl._selectors',
        'playwright._impl._touchscreen',
        'playwright._impl._tracing',
        'playwright._impl._video',
        'playwright._impl._waiter',
        'playwright._impl._web_socket',
        'playwright._impl._worker',
        # GUI / tray
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFilter',
        'tkinter',
        'tkinter.ttk',
        # System
        'winreg',
        'ctypes',
        'ctypes.wintypes',
        # App
        'dotenv',
        'clipboard',
        'browser_uploader',
        'vdisk_uploader',
        'gui_notification',
        'system_tray',
        'setup_wizard',
        'config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'IPython'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VdiskUploader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,      # No black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='VdiskUploader',
)
