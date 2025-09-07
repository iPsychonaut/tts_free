# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('piper/en_GB-cori-high.onnx', 'piper'), ('piper/en_GB-cori-high.onnx.json', 'piper'), ('piper/en_GB-semaine-medium.onnx', 'piper'), ('piper/en_GB-semaine-medium.onnx.json', 'piper'), ('piper/en_GB-southern_english_female-low.onnx', 'piper'), ('piper/en_GB-southern_english_female-low.onnx.json', 'piper')]
hiddenimports = []
datas += collect_data_files('PyQt5')
hiddenimports += collect_submodules('PyQt5.QtMultimedia')


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[('piper/piper', 'piper')],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='app',
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
)
