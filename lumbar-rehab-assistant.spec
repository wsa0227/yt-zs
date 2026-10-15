"""PyInstaller configuration for the Windows desktop executable.

The spec intentionally keeps the technical executable name stable.  The
installer exposes the product as ``宇安`` while the executable remains a
stable build artifact for login-startup registration and upgrades.
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules("PySide6")
datas = collect_data_files("PySide6")
datas += collect_data_files("rehab_assistant", includes=["ui/assets/*.svg"])

a = Analysis(
    ["src/rehab_assistant/__main__.py"],
    pathex=["src"],
    binaries=[],
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
    name="LumbarRehabAssistant",
    console=False,
    disable_windowed_traceback=False,
)
