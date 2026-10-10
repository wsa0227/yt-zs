# PyInstaller build skeleton. Verify Qt plugin collection on the target Windows build host.
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules("PySide6")
datas = collect_data_files("PySide6")

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
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="LumbarRehabAssistant", console=False)
